"""
Utility functions for collaborative editing.
"""

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from backend.utils import log_info


def notify_page_access_revoked(page_external_id: str, user_id: int):
    """
    Notify WebSocket consumers that a user's page access was revoked.

    This will trigger the access_revoked handler which re-checks access
    and closes the connection if the user no longer has access.

    Args:
        page_external_id: External ID of the page
        user_id: ID of the user whose access was revoked
    """
    channel_layer = get_channel_layer()
    if channel_layer:
        log_info(
            "Sending access_revoked notification: page=%s, user_id=%s",
            page_external_id,
            user_id,
        )
        async_to_sync(channel_layer.group_send)(
            f"page_{page_external_id}",
            {
                "type": "access_revoked",
                "user_id": user_id,
            },
        )
