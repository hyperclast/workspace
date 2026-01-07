from typing import List

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.contrib.auth import get_user_model
from django.http import HttpRequest
from django.shortcuts import get_object_or_404
from ninja import Router
from ninja.responses import Response

from backend.utils import log_info
from core.authentication import session_auth, token_auth
from core.throttling import AddMemberBurstThrottle, AddMemberDailyThrottle
from pages.models import Page
from users.models import Org, OrgMember
from users.schemas import (
    OrgIn,
    OrgMemberIn,
    OrgMemberOut,
    OrgMemberRoleUpdate,
    OrgOut,
    OrgUpdateIn,
)

User = get_user_model()


orgs_router = Router(auth=[token_auth, session_auth])


def notify_org_access_revoked(org: Org, user_id: int):
    """
    Send WebSocket messages to notify a user that their org access has been revoked.
    This will cause the user's editor to close for all pages in all projects in the org,
    unless they have project-level access.
    """
    try:
        channel_layer = get_channel_layer()
        if not channel_layer:
            return

        # Get all pages in this org's projects that the user might be connected to
        pages = Page.objects.filter(
            project__org=org,
            project__is_deleted=False,
            is_deleted=False,
        ).values_list("external_id", flat=True)

        for page_external_id in pages:
            room_name = f"page_{page_external_id}"
            async_to_sync(channel_layer.group_send)(
                room_name,
                {
                    "type": "access_revoked",
                    "user_id": user_id,
                },
            )
    except Exception:
        # Channel layer not available (e.g., in tests) - gracefully ignore
        pass


# ========================================
# Organization Endpoints
# ========================================


@orgs_router.get("/", response=List[OrgOut])
def list_orgs(request: HttpRequest):
    """List all organizations the user is a member of."""
    from django.conf import settings

    queryset = Org.objects.filter(members=request.user)
    if "billing" in getattr(settings, "PRIVATE_FEATURES", []):
        queryset = queryset.select_related("billing")
    return queryset


@orgs_router.get("/{external_id}/", response=OrgOut)
def get_org(request: HttpRequest, external_id: str):
    """Get organization details."""
    org = get_object_or_404(
        Org.objects.filter(members=request.user),
        external_id=external_id,
    )
    return org


@orgs_router.post("/", response={201: OrgOut})
def create_org(request: HttpRequest, payload: OrgIn):
    """Create a new organization."""
    org = Org.objects.create(name=payload.name)

    # Add creator as admin
    OrgMember.objects.create(org=org, user=request.user, role="admin")

    log_info(f"User {request.user.email} created org {org.external_id}")

    return 201, org


@orgs_router.patch("/{external_id}/", response=OrgOut)
def update_org(request: HttpRequest, external_id: str, payload: OrgUpdateIn):
    """Update organization details (admin only)."""
    org = get_object_or_404(Org, external_id=external_id)

    # Check if user is admin
    is_admin = OrgMember.objects.filter(org=org, user=request.user, role="admin").exists()

    if not is_admin:
        return Response({"message": "Only admins can update the organization"}, status=403)

    if payload.name is not None:
        org.name = payload.name
    org.save()

    log_info(f"User {request.user.email} updated org {org.external_id}")

    return org


@orgs_router.delete("/{external_id}/", response={204: None})
def delete_org(request: HttpRequest, external_id: str):
    """Delete organization (admin only)."""
    org = get_object_or_404(Org, external_id=external_id)

    # Check if user is admin
    is_admin = OrgMember.objects.filter(org=org, user=request.user, role="admin").exists()

    if not is_admin:
        return Response({"message": "Only admins can delete the organization"}, status=403)

    log_info(f"User {request.user.email} deleted org {org.external_id}")

    org.delete()
    return 204, None


# ========================================
# Organization Membership Endpoints
# ========================================


@orgs_router.get("/{external_id}/members/", response=List[OrgMemberOut])
def list_org_members(request: HttpRequest, external_id: str):
    """List all members of the organization."""
    org = get_object_or_404(
        Org.objects.filter(members=request.user),
        external_id=external_id,
    )

    members = OrgMember.objects.filter(org=org).select_related("user")
    return [
        {
            "external_id": m.user.external_id,
            "email": m.user.email,
            "role": m.role,
            "created": m.created,
        }
        for m in members
    ]


@orgs_router.post(
    "/{external_id}/members/",
    response={201: OrgMemberOut},
    throttle=[AddMemberBurstThrottle(), AddMemberDailyThrottle()],
)
def add_org_member(request: HttpRequest, external_id: str, payload: OrgMemberIn):
    """Add a member to the organization. Any org member can invite.

    Rate limited: 1 request per 10 seconds, max 100 per day.
    """
    org = get_object_or_404(
        Org.objects.filter(members=request.user),
        external_id=external_id,
    )

    try:
        user_to_add = User.objects.get(email=payload.email)
    except User.DoesNotExist:
        return Response({"message": f"User with email {payload.email} not found"}, status=404)

    # Check if already a member
    if OrgMember.objects.filter(org=org, user=user_to_add).exists():
        return Response({"message": f"{payload.email} is already a member"}, status=400)

    # Add member (default to 'member' role if not specified)
    membership = OrgMember.objects.create(org=org, user=user_to_add, role=payload.role or "member")

    log_info(f"User {request.user.email} added {user_to_add.email} to org {org.external_id}")

    return 201, {
        "external_id": user_to_add.external_id,
        "email": user_to_add.email,
        "role": membership.role,
        "created": membership.created,
    }


@orgs_router.delete("/{external_id}/members/{user_external_id}/", response={204: None})
def remove_org_member(request: HttpRequest, external_id: str, user_external_id: str):
    """Remove a member from the organization. Any member can remove others."""
    org = get_object_or_404(
        Org.objects.filter(members=request.user),
        external_id=external_id,
    )

    user_to_remove = get_object_or_404(User, external_id=user_external_id)

    # Prevent removing yourself if you're the only admin
    if user_to_remove == request.user:
        admin_count = OrgMember.objects.filter(org=org, role="admin").count()
        if admin_count == 1:
            is_admin = OrgMember.objects.filter(org=org, user=request.user, role="admin").exists()
            if is_admin:
                return Response({"message": "Cannot remove the only admin"}, status=400)

    # Remove membership
    deleted, _ = OrgMember.objects.filter(org=org, user=user_to_remove).delete()

    if not deleted:
        return Response({"message": "User is not a member of this organization"}, status=404)

    log_info(f"User {request.user.email} removed {user_to_remove.email} from org {org.external_id}")

    # Revoke WebSocket access for pages in this org
    # Note: If user has project-level access, the WebSocket consumer will re-check
    # and only kick them if they truly lost all access
    notify_org_access_revoked(org, user_to_remove.id)

    return 204, None


@orgs_router.patch("/{external_id}/members/{user_external_id}/", response=OrgMemberOut)
def update_org_member_role(request: HttpRequest, external_id: str, user_external_id: str, payload: OrgMemberRoleUpdate):
    """Update member role (admin only)."""
    org = get_object_or_404(Org, external_id=external_id)

    # Check if requester is admin
    is_admin = OrgMember.objects.filter(org=org, user=request.user, role="admin").exists()
    if not is_admin:
        return Response({"message": "Only admins can change member roles"}, status=403)

    user_to_update = get_object_or_404(User, external_id=user_external_id)

    membership = get_object_or_404(OrgMember, org=org, user=user_to_update)

    # Prevent demoting yourself if you're the only admin
    if user_to_update == request.user and payload.role != "admin":
        admin_count = OrgMember.objects.filter(org=org, role="admin").count()
        if admin_count == 1:
            return Response({"message": "Cannot demote the only admin"}, status=400)

    membership.role = payload.role
    membership.save()

    log_info(
        f"User {request.user.email} changed {user_to_update.email} role to {payload.role} in org {org.external_id}"
    )

    return {
        "external_id": user_to_update.external_id,
        "email": user_to_update.email,
        "role": membership.role,
        "created": membership.created,
    }
