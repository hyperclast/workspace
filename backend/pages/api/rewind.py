import logging
from typing import List

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.conf import settings
from django.db import transaction
from django.db.models import F
from django.http import Http404, HttpRequest
from django.shortcuts import get_object_or_404
from ninja import Query, Router
from ninja.pagination import paginate

from backend.utils import log_info
from collab.models import YSnapshot, YUpdate
from core.authentication import session_auth, token_auth
from core.helpers import hashify
from pages.models import Page
from pages.models.rewind import Rewind
from pages.permissions import user_can_access_page, user_can_edit_in_page
from pages.services.rewind import _compute_line_diff
from pages.schemas import (
    RewindCheckpointIn,
    RewindListQuery,
    RewindOut,
    RewindSummaryOut,
    RewindUpdateIn,
)

logger = logging.getLogger(__name__)

rewind_router = Router(auth=[token_auth, session_auth])


@rewind_router.get(
    "/{external_id}/rewind/",
    response=List[RewindSummaryOut],
)
@paginate
def list_rewinds(request: HttpRequest, external_id: str, query: RewindListQuery = Query(...)):
    """List rewinds for a page (paginated, no content)."""
    if not settings.REWIND_ENABLED:
        raise Http404

    page = get_object_or_404(Page, external_id=external_id, is_deleted=False)

    if not user_can_access_page(request.user, page):
        raise Http404

    qs = Rewind.objects.filter(page=page).order_by("-rewind_number")

    if query.label:
        qs = qs.filter(label__icontains=query.label)

    return qs.defer("content")


@rewind_router.post(
    "/{external_id}/rewind/checkpoint/",
    response={200: RewindSummaryOut, 404: dict},
)
def create_rewind_checkpoint(
    request: HttpRequest,
    external_id: str,
    payload: RewindCheckpointIn,
):
    """Create a labeled rewind checkpoint of the current page state.

    Unlike restore, this does NOT reset CRDT state or disconnect clients —
    it simply snapshots the current content with a label so the user can
    rewind to this exact point later.
    """
    if not settings.REWIND_ENABLED:
        raise Http404

    page = get_object_or_404(Page, external_id=external_id, is_deleted=False)

    if not user_can_edit_in_page(request.user, page):
        raise Http404

    # Sync latest Yjs snapshot to page.details before snapshotting
    try:
        from collab.tasks import sync_snapshot_with_page

        room_id = f"page_{external_id}"
        sync_snapshot_with_page(room_id, content_only=True)
        page.refresh_from_db(fields=["details"])
    except Exception:
        logger.warning("Failed to sync Yjs snapshot before checkpoint for page %s", external_id)

    content = page.details.get("content", "")
    content_hash = hashify(content)

    # Always create the labeled checkpoint — the user explicitly requested it.
    # Content dedup is intentionally skipped: the label is the point of a
    # checkpoint, even if content hasn't changed since the last rewind.
    latest = Rewind.objects.filter(page=page).order_by("-rewind_number").values("content").first()

    content_size = len(content.encode("utf-8"))
    lines_added, lines_deleted = (
        _compute_line_diff(latest["content"], content) if latest else (len(content.splitlines()), 0)
    )

    with transaction.atomic():
        page = Page.objects.select_for_update().get(id=page.id)
        Page.objects.filter(id=page.id).update(current_rewind_number=F("current_rewind_number") + 1)
        new_rewind_number = Page.objects.values_list("current_rewind_number", flat=True).get(id=page.id)

        rewind = Rewind.objects.create(
            page=page,
            content=content,
            content_hash=content_hash,
            title=page.title,
            content_size_bytes=content_size,
            rewind_number=new_rewind_number,
            editors=[str(request.user.external_id)],
            label=payload.label,
            lines_added=lines_added,
            lines_deleted=lines_deleted,
        )

    # Broadcast so rewind timeline updates live
    from collab.tasks import broadcast_rewind_created

    room_id = f"page_{page.external_id}"
    broadcast_rewind_created(
        room_id,
        str(page.external_id),
        {
            "external_id": str(rewind.external_id),
            "rewind_number": rewind.rewind_number,
            "title": rewind.title,
            "content_size_bytes": rewind.content_size_bytes,
            "editors": rewind.editors,
            "label": rewind.label,
            "lines_added": rewind.lines_added,
            "lines_deleted": rewind.lines_deleted,
            "is_compacted": rewind.is_compacted,
            "compacted_from_count": rewind.compacted_from_count,
            "created": rewind.created.isoformat(),
        },
    )

    log_info(
        "Created checkpoint rewind %d for page %s: '%s'",
        rewind.rewind_number,
        page.external_id,
        payload.label,
    )

    return rewind


@rewind_router.get(
    "/{external_id}/rewind/{rewind_external_id}/",
    response={200: RewindOut, 404: dict},
)
def get_rewind(request: HttpRequest, external_id: str, rewind_external_id: str):
    """Get a rewind with full content."""
    if not settings.REWIND_ENABLED:
        raise Http404

    page = get_object_or_404(Page, external_id=external_id, is_deleted=False)

    if not user_can_access_page(request.user, page):
        raise Http404

    rewind = get_object_or_404(
        Rewind,
        page=page,
        external_id=rewind_external_id,
    )
    return rewind


@rewind_router.post(
    "/{external_id}/rewind/{rewind_external_id}/restore/",
    response={200: RewindOut, 404: dict},
)
def restore_rewind(request: HttpRequest, external_id: str, rewind_external_id: str):
    """Restore a page to a previous rewind.

    Creates a new rewind recording the restore, resets CRDT state,
    and disconnects active WebSocket clients.
    """
    if not settings.REWIND_ENABLED:
        raise Http404

    page = get_object_or_404(Page, external_id=external_id, is_deleted=False)

    if not user_can_edit_in_page(request.user, page):
        raise Http404

    rewind = get_object_or_404(
        Rewind,
        page=page,
        external_id=rewind_external_id,
    )

    content = rewind.content
    content_hash = hashify(content)

    with transaction.atomic():
        # Lock the page row to prevent concurrent restores/rewind-creates
        # from racing on current_rewind_number.
        page = Page.objects.select_for_update().get(id=page.id)

        # Compute line diff between current page content and restored content
        current_content = page.details.get("content", "")
        lines_added, lines_deleted = _compute_line_diff(current_content, content)

        # Update page details
        page.title = rewind.title
        page.details["content"] = content
        page.details["content_hash"] = content_hash
        page.save(update_fields=["title", "details", "modified"])

        # Atomic increment — matches the pattern in services/rewind.py
        Page.objects.filter(id=page.id).update(current_rewind_number=F("current_rewind_number") + 1)
        new_rewind_number = Page.objects.values_list("current_rewind_number", flat=True).get(id=page.id)

        restore_rewind_obj = Rewind.objects.create(
            page=page,
            content=content,
            content_hash=content_hash,
            title=rewind.title,
            content_size_bytes=len(content.encode("utf-8")),
            rewind_number=new_rewind_number,
            editors=[str(request.user.external_id)],
            label=f"Restored from v{rewind.rewind_number}",
            lines_added=lines_added,
            lines_deleted=lines_deleted,
        )

        # Reset CRDT state
        room_id = f"page_{page.external_id}"
        YUpdate.objects.filter(room_id=room_id).delete()
        YSnapshot.objects.filter(room_id=room_id).delete()

    # Disconnect active WebSocket clients so they reconnect with restored content
    _disconnect_ws_clients(room_id)

    log_info(
        "Restored page %s to rewind %d (new rewind %d)",
        page.external_id,
        rewind.rewind_number,
        restore_rewind_obj.rewind_number,
    )

    return restore_rewind_obj


@rewind_router.patch(
    "/{external_id}/rewind/{rewind_external_id}/",
    response={200: RewindOut, 404: dict},
)
def update_rewind_label(
    request: HttpRequest,
    external_id: str,
    rewind_external_id: str,
    payload: RewindUpdateIn,
):
    """Update a rewind's label."""
    if not settings.REWIND_ENABLED:
        raise Http404

    page = get_object_or_404(Page, external_id=external_id, is_deleted=False)

    if not user_can_edit_in_page(request.user, page):
        raise Http404

    rewind = get_object_or_404(
        Rewind,
        page=page,
        external_id=rewind_external_id,
    )

    rewind.label = payload.label
    rewind.save(update_fields=["label", "modified"])

    log_info(
        "Updated label for rewind %d of page %s: '%s'",
        rewind.rewind_number,
        page.external_id,
        payload.label,
    )

    return rewind


def _disconnect_ws_clients(room_id: str):
    """Send a message to disconnect all WS clients for a room."""
    try:
        channel_layer = get_channel_layer()
        if channel_layer is None:
            return

        async_to_sync(channel_layer.group_send)(
            room_id,
            {
                "type": "rewind_restored",
                "message": "Page has been restored to a previous rewind",
            },
        )
    except Exception:
        logger.error("Failed to disconnect WS clients for room %s", room_id, exc_info=True)
