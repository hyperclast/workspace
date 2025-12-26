from secrets import token_urlsafe

from allauth.account.models import EmailAddress
from django.http import HttpRequest
from ninja import Router
from ninja.responses import Response

from backend.utils import log_error
from core.authentication import session_auth, token_auth
from users.schemas import (
    AccessTokenResponse,
    CurrentUserSchema,
    StripeCheckoutSchema,
    UpdateSettingsSchema,
    UpdateUserSchema,
)
from users.subscription import create_checkout_session_id


def get_email_verified(user) -> bool:
    """Check if user's primary email is verified via allauth."""
    return EmailAddress.objects.filter(user=user, email=user.email, verified=True).exists()


users_router = Router()


@users_router.get("/me/", response=CurrentUserSchema)
def get_current_user(request: HttpRequest):
    """
    Get current authenticated user information.
    Used by frontend to check authentication status.
    """
    if not request.user.is_authenticated:
        return Response(
            {"message": "Not authenticated"},
            status=401,
        )

    return {
        "external_id": request.user.external_id,
        "email": request.user.email,
        "email_verified": get_email_verified(request.user),
        "username": request.user.username,
        "first_name": request.user.first_name,
        "last_name": request.user.last_name,
        "is_authenticated": True,
        "access_token": request.user.profile.access_token,
    }


@users_router.patch("/me/", response=CurrentUserSchema, auth=[token_auth, session_auth])
def update_current_user(request: HttpRequest, payload: UpdateUserSchema):
    """
    Update current user's profile (username, first name, last name).
    """
    user = request.user
    update_fields = []

    if payload.username is not None:
        from django.contrib.auth import get_user_model

        User = get_user_model()
        if User.objects.filter(username__iexact=payload.username).exclude(pk=user.pk).exists():
            return Response({"message": "Username is already taken"}, status=400)
        user.username = payload.username
        update_fields.append("username")

    if payload.first_name is not None:
        user.first_name = payload.first_name
        update_fields.append("first_name")

    if payload.last_name is not None:
        user.last_name = payload.last_name
        update_fields.append("last_name")

    if update_fields:
        user.save(update_fields=update_fields)

    return {
        "external_id": user.external_id,
        "email": user.email,
        "email_verified": get_email_verified(user),
        "username": user.username,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "is_authenticated": True,
        "access_token": user.profile.access_token,
    }


@users_router.get("/me/token/", response=AccessTokenResponse, auth=[token_auth, session_auth])
def get_access_token(request: HttpRequest):
    """
    Get the user's API access token.
    Requires session authentication (not token auth).
    """
    return {"access_token": request.user.profile.access_token}


@users_router.post("/me/token/regenerate/", response=AccessTokenResponse, auth=[token_auth, session_auth])
def regenerate_access_token(request: HttpRequest):
    """
    Regenerate a new API access token.
    Invalidates the old token immediately.
    Requires session authentication (not token auth).
    """
    request.user.profile.access_token = token_urlsafe()
    request.user.profile.save(update_fields=["access_token", "modified"])
    return {"access_token": request.user.profile.access_token}


@users_router.post("/stripe/checkout/")
def create_stripe_checkout_session_id(request, payload: StripeCheckoutSchema):
    user = request.user
    if not user.is_authenticated:
        return Response(
            {"message": "Unauthorized"},
            status=401,
        )

    try:
        plan = payload.plan
        session_id = create_checkout_session_id(request, plan)

        return {
            "message": "ok",
            "session_id": session_id,
        }

    except Exception as e:
        log_error("Error handling Stripe checkout for %s: %s", user, e)
        return Response(
            {"message": "Unexpected error"},
            status=400,
        )


@users_router.patch("/settings/")
def update_settings(request: HttpRequest, payload: UpdateSettingsSchema):
    if not request.user.is_authenticated:
        return Response(
            {"message": "Unauthorized"},
            status=401,
        )

    update_fields = {}
    result = {
        "message": "ok",
    }

    try:
        profile = request.user.profile

        for field, value in payload.dict(exclude_unset=True).items():
            if not hasattr(profile, field):
                continue

            setattr(profile, field, value)
            update_fields[field] = value

        if update_fields:
            profile.save(update_fields=list(update_fields.keys()))
            result["details"] = (
                {
                    "updated_fields": update_fields,
                },
            )

    except Exception as e:
        log_error("Error %s while updating profile settings for %s", e, request.user)
        return Response(
            {"message": "Unexpected error"},
            status=400,
        )

    return result
