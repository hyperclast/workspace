from allauth.account.views import LoginView, SignupView
from django.conf import settings


class UserAuthMixin:
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["prepopulated_email"] = self.request.session.get(
            settings.PAGE_INVITATION_PENDING_EMAIL_SESSION_KEY, None
        )

        # Explicitly pass the 'next' parameter to the template
        # This ensures deep linking works through the auth flow
        next_url = self.request.GET.get("next") or self.request.POST.get("next")
        if next_url:
            context["next"] = next_url

        return context


class UserSignupView(UserAuthMixin, SignupView):
    pass


class UserLoginView(UserAuthMixin, LoginView):
    pass
