from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.conf import settings

from ask.tasks import update_page_embedding
from backend.utils import log_error, log_info
from core.helpers import task
from filehub.models import FileLink
from pages.models import Page, PageLink, PageMention
from pages.services.content_refs import parse_page_refs

from .models import YSnapshot


def broadcast_rewind_created(room_id: str, page_id: str, rewind_data: dict):
    """Broadcast rewind_created event to all WebSocket clients.

    Args:
        room_id: The collaboration room ID.
        page_id: The page external_id.
        rewind_data: Dict with the following required fields (consumed by
            frontend/src/rewind/index.js and RewindTab.svelte):
            - external_id (str)
            - rewind_number (int)
            - title (str)
            - content_size_bytes (int)
            - editors (list[str])
            - label (str)
            - lines_added (int)
            - lines_deleted (int)
            - is_compacted (bool)
            - compacted_from_count (int)
            - created (str, ISO 8601)
    """
    try:
        channel_layer = get_channel_layer()
        if channel_layer is None:
            return
        async_to_sync(channel_layer.group_send)(
            room_id,
            {
                "type": "rewind_created",
                "page_id": page_id,
                "rewind": rewind_data,
            },
        )
        log_info("Broadcast rewind_created for %s", room_id)
    except Exception as e:
        log_error("Error broadcasting rewind_created for %s: %s", room_id, e)


def broadcast_links_updated(room_id: str, page_id: str):
    """
    Broadcast links_updated event to all WebSocket clients connected to a page.
    This notifies clients to refresh their Ref sidebar.
    """
    try:
        channel_layer = get_channel_layer()
        if channel_layer is None:
            log_info("No channel layer available, skipping links_updated broadcast")
            return

        async_to_sync(channel_layer.group_send)(
            room_id,
            {
                "type": "links_updated",
                "page_id": page_id,
            },
        )
        log_info("Broadcast links_updated for %s", room_id)
    except Exception as e:
        log_error("Error broadcasting links_updated for %s: %s", room_id, e)


@task(settings.JOB_INTERNAL_QUEUE)
def sync_snapshot_with_page(room_id: str, is_session_end: bool = False, content_only: bool = False):
    """Hydrate page.details from the latest Yjs snapshot.

    When content_only=True, only update page.details (content + hash) and
    return immediately — skip rewind creation, link/mention/file-link sync,
    and embedding enqueue. Use this for synchronous callers that just need
    fresh content (e.g. AI review, generate-edit, checkpoint creation).
    """
    try:
        snapshot = YSnapshot.objects.get(room_id=room_id)
        page_id = room_id.split("_")[-1]
        page = Page.objects.get(external_id=page_id)
        page.update_details_from_snapshot(snapshot=snapshot)

        log_info("Synced snapshot for %s", room_id)

        if content_only:
            return

        content = snapshot.content or ""

        # Create rewind snapshot if enabled
        if settings.REWIND_ENABLED:
            from pages.services.rewind import maybe_create_rewind

            content_hash = page.details.get("content_hash", "")
            if content_hash:
                rewind = maybe_create_rewind(page, content, content_hash, is_session_end=is_session_end)
                if rewind:
                    broadcast_rewind_created(
                        room_id,
                        page_id,
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

        # Single combined parse pass over the snapshot content for all three
        # reference types, instead of three separate regex sweeps.
        parsed_mentions, parsed_page_links, parsed_file_links = parse_page_refs(content)

        _, links_changed = PageLink.objects.sync_parsed_links(page, parsed_page_links)

        if links_changed:
            log_info("Links changed for %s, broadcasting update", room_id)
            broadcast_links_updated(room_id, page_id)
        else:
            log_info("Links unchanged for %s, skipping broadcast", room_id)

        # Sync @mentions
        _, mentions_changed = PageMention.objects.sync_parsed_mentions(page, parsed_mentions)
        if mentions_changed:
            log_info("Mentions changed for %s", room_id)

        # Sync file links
        _, file_links_changed = FileLink.objects.sync_parsed_file_links(page, parsed_file_links)
        if file_links_changed:
            log_info("File links changed for %s", room_id)

        if not settings.ASK_FEATURE_ENABLED:
            log_info("Skipping embedding compute, ask feature is disabled.")
            return

        update_page_embedding.enqueue(page_id=page.external_id)

    except Exception as e:
        log_error("Error syncing snapshot for %s: %s", room_id, e)
