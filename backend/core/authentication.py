from typing import Optional

from django.contrib.auth import get_user_model
from ninja.security import SessionAuth, HttpBearer


class TokenAuth(HttpBearer):
    """Look up user with given access token."""

    def authenticate(self, request, token: str):
        User = get_user_model()

        user: Optional[User] = User.objects.select_related("profile").filter(profile__access_token=token).first()

        if user:
            request.user = user

            return user

        return None


session_auth = SessionAuth(csrf=True)
token_auth = TokenAuth()
