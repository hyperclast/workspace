from allauth.account.adapter import DefaultAccountAdapter
from allauth.headless.adapter import DefaultHeadlessAdapter
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.conf import settings
from django.contrib import messages
from django.shortcuts import redirect

from backend.utils import log_info, log_warning
from pages.models import PageInvitation, ProjectInvitation
from core.emailer import Emailer
from users.utils import generate_username_from_email


def _save_demo_visits_from_cookie(request, user):
    """Save demo visit timestamp from cookie to user profile."""
    demo_first_visit = request.COOKIES.get("demo_first_visit")
    if demo_first_visit:
        user.profile.demo_visits = [demo_first_visit]
        user.profile.save(update_fields=["demo_visits"])


class CustomAccountAdapter(DefaultAccountAdapter):
    """Account adapter class with custom email sending and invitation handling."""

    def populate_username(self, request, user):
        """Override allauth's username generation to use our own logic.

        Allauth's default rejects short email prefixes (like 'w' from 'w@example.com')
        because our MinLengthValidator(4) runs during clean_username. We bypass this
        by generating the username ourselves with appended digits.
        """
        from allauth.account.utils import user_email, user_username

        email = user_email(user)
        username = user_username(user)

        if not username and email:
            user_username(user, generate_username_from_email(email))

    def send_mail(self, template_prefix, email, context):
        emailer = Emailer(
            template_prefix=template_prefix,
            request=self.request,
        )
        emailer.send_mail(email, context)

    def get_login_redirect_url(self, request):
        """Get the URL to redirect to after successful login.

        This method always redirects to the frontend URL.
        The 'next' parameter from invitation links is already included in the
        full frontend URL (e.g., http://localhost:5173/pages/abc123/).
        """
        next_url = request.POST.get("next") or request.GET.get("next")

        if next_url:
            return next_url

        # Fall back to frontend URL
        return settings.FRONTEND_URL + "/"

    def get_signup_redirect_url(self, request):
        """Get the URL to redirect to after successful signup.

        This method checks for a 'next' parameter in the request and uses it
        if present, falling back to the frontend URL.
        """
        # Check for 'next' parameter in POST or GET
        next_url = request.POST.get("next") or request.GET.get("next")

        if next_url:
            # Validate the URL to ensure it's safe
            return next_url

        # Fall back to frontend URL
        return settings.FRONTEND_URL + "/"

    def save_user(self, request, user, form, commit=True):
        """Saves user and handle pending invitation acceptance.

        This is called during signup (both email/password and social auth).
        If there's a pending invitation in the session that matches the user's email,
        automatically accept it.
        """
        # Generate username from email before saving
        if user.email and not user.username:
            user.username = generate_username_from_email(user.email)

        # Call parent to save the user
        user = super().save_user(request, user, form, commit)

        # Check for pending page invitation in session
        pending_token = request.session.get(settings.PAGE_INVITATION_PENDING_TOKEN_SESSION_KEY)
        pending_email = request.session.get(settings.PAGE_INVITATION_PENDING_EMAIL_SESSION_KEY)

        if pending_token and pending_email:
            # Get the invitation
            invitation = PageInvitation.objects.get_valid_invitation(pending_token)

            if invitation and invitation.email.lower() == user.email.lower():
                try:
                    # Accept the invitation
                    invitation.accept(user)
                    log_info(
                        "Auto-accepted invitation after signup: user=%s, page=%s, invitation=%s",
                        user.email,
                        invitation.page.external_id,
                        invitation.external_id,
                    )

                    # Clear the session
                    del request.session[settings.PAGE_INVITATION_PENDING_TOKEN_SESSION_KEY]
                    del request.session[settings.PAGE_INVITATION_PENDING_EMAIL_SESSION_KEY]

                    # Add success message
                    messages.success(request, f"You now have access to '{invitation.page.title}'")

                except ValueError as e:
                    log_warning("Failed to auto-accept invitation after signup: %s", e)
            else:
                # Invitation invalid or email mismatch - clear session
                if settings.PAGE_INVITATION_PENDING_TOKEN_SESSION_KEY in request.session:
                    del request.session[settings.PAGE_INVITATION_PENDING_TOKEN_SESSION_KEY]
                if settings.PAGE_INVITATION_PENDING_EMAIL_SESSION_KEY in request.session:
                    del request.session[settings.PAGE_INVITATION_PENDING_EMAIL_SESSION_KEY]

        # Check for pending project invitation in session
        pending_project_token = request.session.get(settings.PROJECT_INVITATION_PENDING_TOKEN_SESSION_KEY)
        pending_project_email = request.session.get(settings.PROJECT_INVITATION_PENDING_EMAIL_SESSION_KEY)

        if pending_project_token and pending_project_email:
            # Get the invitation
            invitation = ProjectInvitation.objects.get_valid_invitation(pending_project_token)

            if invitation and invitation.email.lower() == user.email.lower():
                try:
                    # Accept the invitation
                    invitation.accept(user)
                    project_name = invitation.project.name or "the project"
                    log_info(
                        "Auto-accepted project invitation after signup: user=%s, project=%s, invitation=%s",
                        user.email,
                        invitation.project.external_id,
                        invitation.external_id,
                    )

                    # Clear the session
                    del request.session[settings.PROJECT_INVITATION_PENDING_TOKEN_SESSION_KEY]
                    del request.session[settings.PROJECT_INVITATION_PENDING_EMAIL_SESSION_KEY]

                    # Add success message
                    messages.success(request, f"You now have access to '{project_name}'")

                except ValueError as e:
                    log_warning("Failed to auto-accept project invitation after signup: %s", e)
            else:
                # Invitation invalid or email mismatch - clear session
                if settings.PROJECT_INVITATION_PENDING_TOKEN_SESSION_KEY in request.session:
                    del request.session[settings.PROJECT_INVITATION_PENDING_TOKEN_SESSION_KEY]
                if settings.PROJECT_INVITATION_PENDING_EMAIL_SESSION_KEY in request.session:
                    del request.session[settings.PROJECT_INVITATION_PENDING_EMAIL_SESSION_KEY]

        # Save demo visit timestamp if present
        _save_demo_visits_from_cookie(request, user)

        return user

    def login(self, request, user):
        """Handles post-login invitation acceptance.

        This is called after successful login (both email/password and social auth).
        Only checks for pending invitations if session has a token - no extra queries otherwise.
        """
        # Call parent login first
        ret = super().login(request, user)

        # Only check for page invitation if there's a pending token in session
        # This avoids unnecessary DB queries for most logins
        pending_token = request.session.get(settings.PAGE_INVITATION_PENDING_TOKEN_SESSION_KEY)
        pending_email = request.session.get(settings.PAGE_INVITATION_PENDING_EMAIL_SESSION_KEY)

        if pending_token and pending_email:
            # Get the invitation
            invitation = PageInvitation.objects.get_valid_invitation(pending_token)

            if invitation and invitation.email.lower() == user.email.lower():
                try:
                    # Accept the invitation
                    invitation.accept(user)
                    log_info(
                        "Auto-accepted invitation after login: user=%s, page=%s, invitation=%s",
                        user.email,
                        invitation.page.external_id,
                        invitation.external_id,
                    )

                    # Clear the session
                    del request.session[settings.PAGE_INVITATION_PENDING_TOKEN_SESSION_KEY]
                    del request.session[settings.PAGE_INVITATION_PENDING_EMAIL_SESSION_KEY]

                    # Add success message
                    messages.success(request, f"You now have access to '{invitation.page.title}'")

                except ValueError as e:
                    log_warning("Failed to auto-accept invitation after login: %s", e)
            else:
                # Invitation invalid or email mismatch - clear session
                if settings.PAGE_INVITATION_PENDING_TOKEN_SESSION_KEY in request.session:
                    del request.session[settings.PAGE_INVITATION_PENDING_TOKEN_SESSION_KEY]
                if settings.PAGE_INVITATION_PENDING_EMAIL_SESSION_KEY in request.session:
                    del request.session[settings.PAGE_INVITATION_PENDING_EMAIL_SESSION_KEY]

        # Check for pending project invitation in session
        pending_project_token = request.session.get(settings.PROJECT_INVITATION_PENDING_TOKEN_SESSION_KEY)
        pending_project_email = request.session.get(settings.PROJECT_INVITATION_PENDING_EMAIL_SESSION_KEY)

        if pending_project_token and pending_project_email:
            # Get the invitation
            invitation = ProjectInvitation.objects.get_valid_invitation(pending_project_token)

            if invitation and invitation.email.lower() == user.email.lower():
                try:
                    # Accept the invitation
                    invitation.accept(user)
                    project_name = invitation.project.name or "the project"
                    log_info(
                        "Auto-accepted project invitation after login: user=%s, project=%s, invitation=%s",
                        user.email,
                        invitation.project.external_id,
                        invitation.external_id,
                    )

                    # Clear the session
                    del request.session[settings.PROJECT_INVITATION_PENDING_TOKEN_SESSION_KEY]
                    del request.session[settings.PROJECT_INVITATION_PENDING_EMAIL_SESSION_KEY]

                    # Add success message
                    messages.success(request, f"You now have access to '{project_name}'")

                except ValueError as e:
                    log_warning("Failed to auto-accept project invitation after login: %s", e)
            else:
                # Invitation invalid or email mismatch - clear session
                if settings.PROJECT_INVITATION_PENDING_TOKEN_SESSION_KEY in request.session:
                    del request.session[settings.PROJECT_INVITATION_PENDING_TOKEN_SESSION_KEY]
                if settings.PROJECT_INVITATION_PENDING_EMAIL_SESSION_KEY in request.session:
                    del request.session[settings.PROJECT_INVITATION_PENDING_EMAIL_SESSION_KEY]

        return ret


class CustomSocialAccountAdapter(DefaultSocialAccountAdapter):
    """Social account adapter with custom methods."""

    def authentication_error(self, request, provider, error=None, exception=None, extra_context=None):
        messages.error(request, "An error occurred while signing in with Google. Please try again.")

        return redirect("/")

    def save_user(self, request, sociallogin, form=None):
        user = sociallogin.user
        if user.email and not user.username:
            user.username = generate_username_from_email(user.email)

        user = super().save_user(request, sociallogin, form)
        account = sociallogin.account
        picture_url = None

        if account.provider == "google":
            extra_data = account.extra_data
            picture_url = extra_data.get("picture")

        if picture_url:
            user.profile.picture = picture_url
            user.profile.save(update_fields=["picture"])

        # Save demo visit timestamp if present
        _save_demo_visits_from_cookie(request, user)

        return user


class CustomHeadlessAdapter(DefaultHeadlessAdapter):
    """Headless adapter with custom user fields."""

    def serialize_user(self, user):
        """Serialize user with external_id instead of internal id."""
        return {
            "external_id": str(user.external_id),
            "email": user.email,
            "has_usable_password": user.has_usable_password(),
        }
