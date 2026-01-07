from typing import List, Optional

from django.http import HttpRequest
from django.shortcuts import get_object_or_404
from ninja import Router, Schema

from backend.utils import log_info
from collab.models import YSnapshot
from collab.tasks import broadcast_links_updated
from core.authentication import session_auth, token_auth
from pages.models import Page, PageLink


links_router = Router(auth=[token_auth, session_auth])


class LinkItem(Schema):
    external_id: str
    title: str
    link_text: str

    class Config:
        from_attributes = True


class PageLinksOut(Schema):
    outgoing: List[LinkItem]
    incoming: List[LinkItem]


class SyncLinksIn(Schema):
    content: Optional[str] = None


class SyncLinksOut(Schema):
    synced: bool
    outgoing: List[LinkItem]
    incoming: List[LinkItem]


@links_router.get("/{external_id}/links/", response=PageLinksOut)
def get_page_links(request: HttpRequest, external_id: str):
    """Get outgoing and incoming links for a page."""
    page = get_object_or_404(
        Page.objects.get_user_editable_pages(request.user),
        external_id=external_id,
    )

    outgoing = [
        LinkItem(
            external_id=link.target_page.external_id,
            title=link.target_page.title,
            link_text=link.link_text,
        )
        for link in page.outgoing_links.select_related("target_page", "target_page__project").filter(
            target_page__is_deleted=False,
            target_page__project__is_deleted=False,
        )
    ]

    incoming = [
        LinkItem(
            external_id=link.source_page.external_id,
            title=link.source_page.title,
            link_text=link.link_text,
        )
        for link in page.incoming_links.select_related("source_page", "source_page__project").filter(
            source_page__is_deleted=False,
            source_page__project__is_deleted=False,
        )
    ]

    return PageLinksOut(outgoing=outgoing, incoming=incoming)


@links_router.post("/{external_id}/links/sync/", response=SyncLinksOut)
def sync_page_links(request: HttpRequest, external_id: str, payload: SyncLinksIn):
    """
    Trigger immediate link sync using provided content.
    Called by frontend when user presses Enter or after significant edits.
    Returns the updated link lists.
    """
    page = get_object_or_404(
        Page.objects.get_user_editable_pages(request.user),
        external_id=external_id,
    )

    room_id = f"page_{external_id}"
    synced = False

    if payload.content is not None:
        _, links_changed = PageLink.objects.sync_links_for_page(page, payload.content)
        log_info("Immediate link sync for %s (from request content), changed=%s", external_id, links_changed)
        if links_changed:
            broadcast_links_updated(room_id, external_id)
        synced = True
    else:
        try:
            snapshot = YSnapshot.objects.get(room_id=room_id)
            content = snapshot.content or ""
            _, links_changed = PageLink.objects.sync_links_for_page(page, content)
            log_info("Immediate link sync for %s (from snapshot), changed=%s", external_id, links_changed)
            if links_changed:
                broadcast_links_updated(room_id, external_id)
            synced = True
        except YSnapshot.DoesNotExist:
            log_info("No snapshot found for %s, skipping link sync", external_id)
            synced = False

    outgoing = [
        LinkItem(
            external_id=link.target_page.external_id,
            title=link.target_page.title,
            link_text=link.link_text,
        )
        for link in page.outgoing_links.select_related("target_page", "target_page__project").filter(
            target_page__is_deleted=False,
            target_page__project__is_deleted=False,
        )
    ]

    incoming = [
        LinkItem(
            external_id=link.source_page.external_id,
            title=link.source_page.title,
            link_text=link.link_text,
        )
        for link in page.incoming_links.select_related("source_page", "source_page__project").filter(
            source_page__is_deleted=False,
            source_page__project__is_deleted=False,
        )
    ]

    return SyncLinksOut(synced=synced, outgoing=outgoing, incoming=incoming)
