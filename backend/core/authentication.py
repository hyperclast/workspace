from allauth.headless.contrib.ninja.security import XSessionTokenAuth
from django.contrib.auth import get_user_model
from ninja.security import SessionAuth, HttpBearer


class TokenAuth(HttpBearer):
    """Look up user with given access token."""

    def authenticate(self, request, token: str):
        from users.models import AccessToken

        token_obj = (
            AccessToken.objects.select_related("user", "user__profile").filter(value=token, is_active=True).first()
        )
        if token_obj:
            request.user = token_obj.user
            request._access_token = token_obj
            return token_obj.user

        # Fallback: check Profile.access_token for CLI/web during transition
        User = get_user_model()
        user = User.objects.select_related("profile").filter(profile__access_token=token).first()
        if user:
            request.user = user
            return user
        return None


class SessionTokenAuth(XSessionTokenAuth):
    """Wraps allauth's XSessionTokenAuth to set request.user."""

    def __call__(self, request):
        user = super().__call__(request)
        if user:
            request.user = user
        return user


session_auth = SessionAuth(csrf=True)
token_auth = TokenAuth()
x_session_token_auth = SessionTokenAuth()
