from django.db.models import TextChoices


class OrgMemberRole(TextChoices):
    ADMIN = "admin", "Admin"
    MEMBER = "member", "Member"


class AccessTokenManagedBy(TextChoices):
    SYSTEM = "system", "System"
    USER = "user", "User"


class DeviceClientType(TextChoices):
    MOBILE = "mobile", "Mobile"
    BROWSER = "browser", "Browser"
    CLI = "cli", "CLI"
