from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.conf import settings

from ask.tasks import update_page_embedding
from backend.utils import log_error, log_info
from core.helpers import task
from pages.models import Page, PageLink, PageMention

from .models import YSnapshot


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
def sync_snapshot_with_page(room_id: str):
    try:
        snapshot = YSnapshot.objects.get(room_id=room_id)
        page_id = room_id.split("_")[-1]
        page = Page.objects.get(external_id=page_id)
        page.update_details_from_snapshot(snapshot=snapshot)

        log_info("Synced snapshot for %s", room_id)

        content = snapshot.content or ""
        _, links_changed = PageLink.objects.sync_links_for_page(page, content)

        if links_changed:
            log_info("Links changed for %s, broadcasting update", room_id)
            broadcast_links_updated(room_id, page_id)
        else:
            log_info("Links unchanged for %s, skipping broadcast", room_id)

        # Sync @mentions
        _, mentions_changed = PageMention.objects.sync_mentions_for_page(page, content)
        if mentions_changed:
            log_info("Mentions changed for %s", room_id)

        if not settings.ASK_FEATURE_ENABLED:
            log_info("Skipping embedding compute ask ask feature is disabled.")
            return

        update_page_embedding.enqueue(page_id=page.external_id)

    except Exception as e:
        log_error("Error syncing snapshot for %s: %s", room_id, e)
