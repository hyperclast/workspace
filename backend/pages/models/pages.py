from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.serializers.json import DjangoJSONEncoder
from django.db import models, transaction
from django.db.models import BooleanField, Case, Q, Value, When
from django.utils import timezone
from django_extensions.db.models import TimeStampedModel

from collab.models import YUpdate, YSnapshot
from core.fields import UniqueIDTextField
from core.helpers import hashify

User = get_user_model()


class PageManager(models.Manager):
    @transaction.atomic
    def create_with_owner(self, user, **page_details):
        page = self.create(creator=user, **page_details)
        page.editors.add(user)

        return page

    def create_default_page(self, user, project):
        """
        Create the default page in the user's default project.

        Args:
            user: The user creating the page
            project: The project the page belongs to

        Returns:
            Page instance
        """
        return self.create_with_owner(
            user=user,
            project=project,
            title="Untitled",
            details={"content": "", "filetype": "md", "schema_version": 1},
        )

    def get_editable_pages(self):
        return self.get_queryset().filter(is_deleted=False)

    def get_user_editable_pages(self, user):
        """
        Get all pages the user can access via org membership, project sharing, or page sharing.

        Three-tier access model:
        - Tier 1 (Org): User is member of page's project's org (when org_members_can_access=True)
        - Tier 2 (Project): User is a project editor
        - Tier 3 (Page): User is a page editor

        Access is granted if ANY condition is true.
        Excludes pages from soft-deleted projects.
        """
        from users.models import OrgMember

        # Get org IDs where user is admin (admins always have access)
        admin_org_ids = OrgMember.objects.filter(user=user, role="admin").values_list("org_id", flat=True)

        page_ids = (
            self.get_editable_pages()
            .filter(project__is_deleted=False)
            .filter(
                Q(project__org_id__in=admin_org_ids)  # Tier 0: Org admins always have access
                | Q(
                    project__org__members=user, project__org_members_can_access=True
                )  # Tier 1: Org members (if enabled)
                | Q(project__editors=user)  # Tier 2: Project editors
                | Q(editors=user)  # Tier 3: Page editors (NEW)
            )
            .values_list("id", flat=True)
            .distinct()
        )
        qs = (
            self.get_editable_pages()
            .filter(id__in=page_ids)
            .annotate(
                is_owner=Case(
                    When(creator_id=user.id, then=Value(True)),
                    default=Value(False),
                    output_field=BooleanField(),
                ),
            )
        )
        return qs


class Page(TimeStampedModel):
    # TODO:
    # - Temporarily make nullable
    project = models.ForeignKey(
        "pages.Project",
        on_delete=models.CASCADE,
        related_name="pages",
        null=True,
        default=None,
    )
    creator = models.ForeignKey(
        User,
        related_name="created_pages",
        on_delete=models.PROTECT,
    )
    external_id = UniqueIDTextField()
    title = models.TextField(
        blank=True,
        default="",
        db_index=True,  # Index for autocomplete search performance
    )
    details = models.JSONField(
        encoder=DjangoJSONEncoder,
        default=dict,
    )
    editors = models.ManyToManyField(
        User,
        through="pages.PageEditor",
        related_name="editable_pages",
    )
    updated = models.DateTimeField(
        db_index=True,
        default=timezone.now,
    )
    is_deleted = models.BooleanField(db_index=True, default=False)
    version = models.TextField(blank=True, default="")
    access_code = models.CharField(
        max_length=43,  # secrets.token_urlsafe(32) produces 43 chars
        unique=True,
        null=True,
        blank=True,
        db_index=True,
        help_text="Token for read-only public access",
    )

    objects = PageManager()

    class Meta:
        indexes = [
            models.Index(
                fields=["project", "-updated"],
                name="page_project_updated_idx",
                condition=models.Q(is_deleted=False),
            ),
        ]

    def __str__(self):
        return self.title

    def has_access(self, user):
        """
        Check if user can access this page.

        Two-tier access check:
        - Tier 1: User is member of page's project's org
        - Tier 2: User is in page's editors

        Returns True if user has org-based OR page-level access.
        This is a convenience method that wraps the permission helper.

        Args:
            user: User instance

        Returns:
            bool: True if user has access to this page
        """
        from pages.permissions import user_can_access_page

        return user_can_access_page(user, self)

    def get_access_source(self, user):
        """
        Get how user has access to this page.

        Args:
            user: User instance

        Returns:
            str or None: "org", "direct", "both", or None
        """
        from pages.permissions import get_page_access_source

        return get_page_access_source(user, self)

    @property
    def page_url(self):
        """Return the frontend URL for this page."""
        return f"{settings.FRONTEND_URL}/pages/{self.external_id}/"

    @property
    def org_members_with_info(self):
        """
        Return all org members who have access to this page via org membership.

        Only returns members if the page belongs to a project with an org.
        Returns empty list for pages without a project.
        """
        if not self.project or not self.project.org:
            return []

        from users.models import OrgMember

        # Get all org members with their role info
        org_members = OrgMember.objects.filter(org=self.project.org).select_related("user")

        members_list = []
        for membership in org_members:
            user = membership.user
            members_list.append(
                {
                    "external_id": str(user.external_id),
                    "email": user.email,
                    "is_creator": user.id == self.creator_id,
                    "role": membership.role,
                }
            )

        return members_list

    @property
    def editors_with_info(self):
        """Return all editors AND pending invitations."""
        # Get confirmed editors
        editors = list(
            self.editors.annotate(
                is_owner=Case(
                    When(id=self.creator_id, then=Value(True)),
                    default=Value(False),
                    output_field=BooleanField(),
                ),
            ).values("external_id", "email", "is_owner")
        )

        # Add is_pending=False to all confirmed editors and convert external_id to string
        for editor in editors:
            editor["external_id"] = str(editor["external_id"])
            editor["is_pending"] = False

        # Get pending invitations (valid, not accepted)
        pending_invitations = self.invitations.filter(accepted=False, expires_at__gt=timezone.now()).values(
            "external_id", "email"
        )

        # Add pending invitations with is_pending=True and is_owner=False
        for invitation in pending_invitations:
            editors.append(
                {
                    "external_id": str(invitation["external_id"]),
                    "email": invitation["email"],
                    "is_owner": False,
                    "is_pending": True,
                }
            )

        return editors

    @property
    def content_for_embedding(self) -> str:
        title = self.title or ""
        content = self.details.get("content", "")

        if not title and not content:
            return ""

        result = f"{title}\n\n{content}"

        return result.strip()

    def update_details_from_snapshot(self, snapshot):
        # Update page details with timestamp and content
        content = snapshot.content
        self.updated = snapshot.timestamp
        self.details["content"] = content
        self.details["content_hash"] = hashify(content)
        self.save(update_fields=["updated", "details"])

    @transaction.atomic
    def mark_as_deleted(self):
        # Clean up CRDT data
        room_id = f"page_{self.external_id}"
        YUpdate.objects.filter(room_id=room_id).delete()
        YSnapshot.objects.filter(room_id=room_id).delete()
        self.is_deleted = True
        self.save(update_fields=["is_deleted"])
