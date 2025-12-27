from django.contrib.auth import get_user_model
from django.db import models
from django_extensions.db.models import TimeStampedModel

from users.constants import OrgMemberRole

from core.fields import UniqueIDTextField


User = get_user_model()


class OrgManager(models.Manager):
    def get_or_create_org_for_user(self, user):
        """
        Get existing org by domain or create new one.

        For company emails: Match by domain, first user becomes admin
        For personal emails: Create personal org with null domain

        Returns:
            Tuple of (Org, is_admin: bool) where is_admin indicates if user is admin
        """
        from users.utils import compute_org_name_for_email, extract_domain_from_email

        email = user.email
        domain = extract_domain_from_email(email)

        if domain:
            existing_org = self.filter(domain=domain).first()

            if existing_org:
                OrgMember.objects.create(
                    org=existing_org,
                    user=user,
                    role=OrgMemberRole.MEMBER.value,
                )
                return existing_org, False
            else:
                org_name = compute_org_name_for_email(email)
                org = self.create(name=org_name, domain=domain)
                OrgMember.objects.create(
                    org=org,
                    user=user,
                    role=OrgMemberRole.ADMIN.value,
                )
                return org, True
        else:
            org_name = compute_org_name_for_email(email)
            org = self.create(name=org_name, domain=None)
            OrgMember.objects.create(
                org=org,
                user=user,
                role=OrgMemberRole.ADMIN.value,
            )
            return org, True


class Org(TimeStampedModel):
    external_id = UniqueIDTextField()
    name = models.TextField(blank=True, default="")
    domain = models.TextField(
        unique=True,
        null=True,
        default=None,
    )
    members = models.ManyToManyField(
        User,
        through="users.OrgMember",
        related_name="orgs",
    )

    objects = OrgManager()

    def __str__(self):
        return self.name or self.external_id


class OrgMember(TimeStampedModel):
    org = models.ForeignKey(
        "users.Org",
        on_delete=models.CASCADE,
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
    )
    role = models.TextField(
        choices=OrgMemberRole.choices,
        default=OrgMemberRole.MEMBER.value,
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["org_id", "user_id"],
                name="org_user_uniq",
            ),
        ]

    def __str__(self):
        return f"{self.org}: {self.user}"
