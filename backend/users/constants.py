from django.db.models import TextChoices


class SubscriptionPlan(TextChoices):
    FREE = "free", "Free"
    PRO = "pro", "Placeholder premium plan"

    # Add/Modify plans here


class OrgMemberRole(TextChoices):
    ADMIN = "admin", "Admin"
    MEMBER = "member", "Member"
