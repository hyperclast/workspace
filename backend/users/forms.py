from zoneinfo import available_timezones

from allauth.account.forms import SignupForm
from django import forms

from .models import Profile


class ProfileAdminForm(forms.ModelForm):
    tz = forms.ChoiceField(
        choices=[("UTC", "UTC")] + [(tz, tz) for tz in sorted(available_timezones())],
        required=False,
    )


class UserSignupForm(SignupForm):
    # Customize signup form here
    pass
