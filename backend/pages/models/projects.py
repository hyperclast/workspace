from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import models
from django.db.models import BooleanField, Case, Q, Value, When
from django_extensions.db.models import TimeStampedModel

from core.fields import UniqueIDTextField


User = get_user_model()


class ProjectManager(models.Manager):
    def get_user_accessible_projects(self, user):
        """
        Get projects user can access via org admin, org membership, project sharing, or page sharing.

        Four-tier access model:
        - Tier 0 (Admin): User is org admin (always has access)
        - Tier 1 (Org): User is member of the project's org AND org_members_can_access=True
        - Tier 2 (Project): User is a project editor
        - Tier 3 (Page): User is an editor on at least one page in the project

        Returns:
            QuerySet of non-deleted projects the user can access
        """
        from pages.models import Page
        from users.models import OrgMember

        # Get org IDs where user is admin
        admin_org_ids = OrgMember.objects.filter(user=user, role="admin").values_list("org_id", flat=True)

        # Get project IDs where user has page-level access
        page_access_project_ids = Page.objects.filter(
            editors=user, is_deleted=False, project__is_deleted=False
        ).values_list("project_id", flat=True)

        return (
            self.get_queryset()
            .filter(
                Q(org_id__in=admin_org_ids)  # Org admins always have access
                | Q(org__members=user, org_members_can_access=True)  # Org members (if enabled)
                | Q(editors=user)  # Project editors
                | Q(id__in=page_access_project_ids),  # Page editors (NEW: Tier 3)
                is_deleted=False,
            )
            .distinct()
        )

    def create_default_project(self, user, org):
        """
        Create the default project for a new user.

        Args:
            user: The user creating the project
            org: The organization the project belongs to

        Returns:
            Project instance
        """
        email = user.email
        return self.create(
            org=org,
            name=f"First Project",
            description=f"Initial project automatically created for {email}",
            creator=user,
        )


class Project(TimeStampedModel):
    org = models.ForeignKey(
        "users.Org",
        on_delete=models.CASCADE,
        related_name="projects",
    )
    external_id = UniqueIDTextField()
    name = models.TextField(blank=True, default="")
    description = models.TextField(blank=True, default="")
    is_deleted = models.BooleanField(db_index=True, default=False)
    version = models.TextField(blank=True, default="")
    creator = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
    )
    editors = models.ManyToManyField(
        User,
        through="pages.ProjectEditor",
        related_name="editable_projects",
    )
    org_members_can_access = models.BooleanField(
        default=True,
        help_text="If True, all org members can access. If False, only project editors.",
    )

    objects = ProjectManager()

    class Meta:
        indexes = [
            models.Index(
                fields=["org", "-modified"],
                name="project_org_mod_idx",
                condition=models.Q(is_deleted=False),
            ),
        ]

    def __str__(self):
        return self.name or self.external_id

    @property
    def project_url(self):
        """Return the frontend URL for this project."""
        return f"{settings.FRONTEND_URL}/?project={self.external_id}"

    @property
    def editors_with_info(self):
        """Return all project editors with metadata.

        Returns a list of dicts with external_id, email, is_creator for each editor.
        Uses annotate to avoid N+1 queries.
        """
        editors = list(
            self.editors.annotate(
                is_creator=Case(
                    When(id=self.creator_id, then=Value(True)),
                    default=Value(False),
                    output_field=BooleanField(),
                ),
            ).values("external_id", "email", "is_creator")
        )

        for editor in editors:
            editor["external_id"] = str(editor["external_id"])

        return editors
