from typing import List, Optional

from django.http import HttpRequest
from ninja import Query, Router, Schema

from core.authentication import session_auth, token_auth
from pages.models import Page, PageMention


mentions_router = Router(auth=[token_auth, session_auth])


class MentionItem(Schema):
    page_external_id: str
    page_title: str
    project_name: str
    modified: str

    class Config:
        from_attributes = True


class MentionsOut(Schema):
    mentions: List[MentionItem]
    total: int
    has_more: bool


class MentionsQueryParams(Schema):
    limit: int = 50
    offset: int = 0
    # When set, restrict the mentions list to pages in this org. The
    # frontend passes the current sidenav org so the command palette
    # only surfaces mentions for the workspace the user is currently in
    # — matching how recent-pages and link autocomplete already behave.
    # Omitted = legacy cross-org behaviour.
    org_id: Optional[str] = None


@mentions_router.get("/", response=MentionsOut)
def get_my_mentions(request: HttpRequest, query: MentionsQueryParams = Query(...)):
    """Get pages where current user is @mentioned.

    Only returns mentions from pages the user currently has access to.
    When `org_id` is set, results are further restricted to pages whose
    project lives in that org — keeps the command-palette mention list
    consistent with the rest of the per-org reference surfaces. An
    `org_id` the user isn't a member of yields an empty list (no
    membership-existence leak).

    Results are paginated and ordered by page modified date (most recent first).
    """
    # Get IDs of pages user can access
    accessible_page_ids = Page.objects.get_user_accessible_pages(request.user).values_list("id", flat=True)

    # Filter mentions to only accessible, non-deleted pages
    mentions_qs = (
        PageMention.objects.filter(
            mentioned_user=request.user,
            source_page_id__in=accessible_page_ids,
            source_page__is_deleted=False,
            source_page__project__is_deleted=False,
        )
        .select_related("source_page", "source_page__project")
        .order_by("-source_page__modified")
    )

    if query.org_id:
        # Align with the three-tier access model used by Ask and link
        # autocomplete: filter by the page's org alone, with no separate
        # OrgMember gate. The boundary is already enforced by
        # `accessible_page_ids` above — a project-editor or page-editor
        # who isn't an OrgMember has accessible page rows in this org
        # and should see their mentions on those pages. A true outsider
        # has no accessible pages there and gets an empty result by
        # construction (the inner join filters the queryset to nothing),
        # so we don't need a separate membership-existence check.
        mentions_qs = mentions_qs.filter(source_page__project__org__external_id=query.org_id)

    # Get total count before pagination
    total = mentions_qs.count()

    # Apply pagination
    mentions = mentions_qs[query.offset : query.offset + query.limit]

    return MentionsOut(
        mentions=[
            MentionItem(
                page_external_id=m.source_page.external_id,
                page_title=m.source_page.title or "Untitled",
                project_name=m.source_page.project.name if m.source_page.project else "",
                modified=m.source_page.modified.isoformat(),
            )
            for m in mentions
        ],
        total=total,
        has_more=query.offset + query.limit < total,
    )
