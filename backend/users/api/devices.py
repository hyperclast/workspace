from secrets import token_urlsafe

from django.http import HttpRequest
from django.shortcuts import get_object_or_404
from django.utils import timezone
from ninja import Router

from core.authentication import session_auth, token_auth, x_session_token_auth
from users.constants import AccessTokenManagedBy, DeviceClientType
from users.models import AccessToken, Device
from users.schemas import (
    DeviceListItem,
    DeviceRegistrationResponse,
    DeviceRegistrationSchema,
    DeviceUpdateSchema,
)

devices_router = Router()


def _device_to_dict(device):
    return {
        "client_id": device.client_id,
        "client_type": device.client_type,
        "name": device.name,
        "os": device.os,
        "app_version": device.app_version,
        "last_active": device.last_active,
        "created": device.created,
        "details": device.details,
    }


@devices_router.post(
    "/",
    response={201: DeviceRegistrationResponse},
    auth=[token_auth, x_session_token_auth, session_auth],
)
def register_device(request: HttpRequest, payload: DeviceRegistrationSchema):
    """
    Register a device for the authenticated user.

    Creates a new Device + AccessToken, or reactivates and rotates the token
    for an existing device with the same client_id.
    """
    try:
        device = Device.objects.select_related("access_token").get(
            user=request.user,
            client_id=payload.client_id,
        )
        # Existing device — rotate token, reactivate if revoked, update metadata
        device.access_token.value = token_urlsafe()
        device.access_token.is_active = True
        device.access_token.save(update_fields=["value", "is_active", "modified"])
        device.name = payload.name or device.name
        device.os = payload.os or device.os
        device.app_version = payload.app_version or device.app_version
        if payload.details is not None:
            device.details = payload.details
        device.last_active = timezone.now()
        device.save(
            update_fields=[
                "name",
                "os",
                "app_version",
                "details",
                "last_active",
                "modified",
            ]
        )
    except Device.DoesNotExist:
        # New device — create AccessToken + Device
        access_token_obj = AccessToken.objects.create(
            user=request.user,
            managed_by=AccessTokenManagedBy.SYSTEM,
        )
        device = Device.objects.create(
            user=request.user,
            access_token=access_token_obj,
            client_id=payload.client_id,
            client_type=DeviceClientType.MOBILE,
            name=payload.name or "",
            os=payload.os or "",
            app_version=payload.app_version or "",
            details=payload.details or {},
        )

    return 201, {
        "access_token": device.access_token.value,
        "client_id": device.client_id,
    }


@devices_router.get(
    "/",
    response=list[DeviceListItem],
    auth=[token_auth, x_session_token_auth, session_auth],
)
def list_devices(request: HttpRequest):
    """
    List all devices with active tokens for the authenticated user.
    Used by the "Manage Devices" screen.
    """
    devices = Device.objects.select_related("access_token").filter(
        user=request.user,
        access_token__is_active=True,
    )
    current_token = getattr(request, "_access_token", None)
    return [
        {
            **_device_to_dict(d),
            "is_current": current_token is not None and d.access_token_id == current_token.id,
        }
        for d in devices
    ]


@devices_router.delete(
    "/{client_id}/",
    response={204: None},
    auth=[token_auth, x_session_token_auth, session_auth],
)
def revoke_device(request: HttpRequest, client_id: str):
    """
    Revoke a device by deactivating its AccessToken.
    The Device row is kept for audit / re-login dedup.
    """
    device = get_object_or_404(
        Device,
        user=request.user,
        client_id=client_id,
        access_token__is_active=True,
    )
    device.access_token.is_active = False
    device.access_token.save(update_fields=["is_active", "modified"])
    return 204, None


@devices_router.patch(
    "/{client_id}/",
    response=DeviceListItem,
    auth=[token_auth, x_session_token_auth, session_auth],
)
def update_device(request: HttpRequest, client_id: str, payload: DeviceUpdateSchema):
    """
    Update device metadata (name, os, app_version, push_token, details).
    Called on app launch to sync metadata after OS or app update.
    """
    device = get_object_or_404(
        Device,
        user=request.user,
        client_id=client_id,
        access_token__is_active=True,
    )
    updated_fields = payload.dict(exclude_unset=True)
    for field, value in updated_fields.items():
        setattr(device, field, value)
    device.save(update_fields=[*updated_fields.keys(), "modified"])

    current_token = getattr(request, "_access_token", None)
    return {
        **_device_to_dict(device),
        "is_current": current_token is not None and device.access_token_id == current_token.id,
    }
