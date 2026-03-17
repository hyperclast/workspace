from django.http import HttpRequest
from django.shortcuts import get_object_or_404
from ninja import Router
from ninja.responses import Response

from core.authentication import session_auth, token_auth
from users.constants import AccessTokenManagedBy
from users.models import AccessToken
from users.schemas import AccessTokenCreateIn, AccessTokenOut, AccessTokenUpdateIn

tokens_router = Router()


@tokens_router.get("/", response=list[AccessTokenOut], auth=[token_auth, session_auth])
def list_tokens(request: HttpRequest):
    """List all user-managed tokens for the current user, newest first."""
    return AccessToken.objects.get_user_tokens(request.user.id)


@tokens_router.post("/", response={201: AccessTokenOut}, auth=[token_auth, session_auth])
def create_token(request: HttpRequest, payload: AccessTokenCreateIn):
    """Create a new user-managed access token with a custom label."""
    token_obj = AccessToken.objects.create(
        user=request.user,
        managed_by=AccessTokenManagedBy.USER,
        label=payload.label,
        is_default=False,
        is_active=True,
    )
    return 201, token_obj


@tokens_router.get("/{external_id}/", response=AccessTokenOut, auth=[token_auth, session_auth])
def retrieve_token(request: HttpRequest, external_id: str):
    """Retrieve a specific user-managed token."""
    return get_object_or_404(
        AccessToken,
        user=request.user,
        external_id=external_id,
        managed_by=AccessTokenManagedBy.USER,
    )


@tokens_router.patch("/{external_id}/", response=AccessTokenOut, auth=[token_auth, session_auth])
def update_token(request: HttpRequest, external_id: str, payload: AccessTokenUpdateIn):
    """Update a user-managed token's label or active status."""
    token_obj = get_object_or_404(
        AccessToken,
        user=request.user,
        external_id=external_id,
        managed_by=AccessTokenManagedBy.USER,
    )

    updates = payload.dict(exclude_unset=True)

    if "is_active" in updates and not updates["is_active"] and token_obj.is_default:
        return Response(
            {"detail": "Cannot deactivate the default token."},
            status=400,
        )

    update_fields = []
    for field, value in updates.items():
        setattr(token_obj, field, value)
        update_fields.append(field)

    if update_fields:
        token_obj.save(update_fields=update_fields + ["modified"])

    return token_obj
