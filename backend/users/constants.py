from django.db.models import TextChoices


class OrgMemberRole(TextChoices):
    ADMIN = "admin", "Admin"
    MEMBER = "member", "Member"
