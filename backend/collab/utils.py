"""
Utility functions for collaborative editing.
"""

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from backend.utils import log_info, log_warning


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


def notify_project_folders_updated(project_external_id: str):
    """
    Broadcast folder tree change to all clients in the project.

    All connected clients editing any page in this project will receive
    the event and refetch the folder tree.
    """
    channel_layer = get_channel_layer()
    if channel_layer:
        try:
            async_to_sync(channel_layer.group_send)(
                f"project_{project_external_id}",
                {"type": "folders_updated"},
            )
        except Exception as e:
            log_warning("Failed to broadcast folders_updated for project %s: %s", project_external_id, e)


def notify_comments_updated(page_external_id: str):
    """Broadcast comment change to all clients viewing the page."""
    channel_layer = get_channel_layer()
    if channel_layer:
        try:
            async_to_sync(channel_layer.group_send)(
                f"page_{page_external_id}",
                {"type": "comments_updated"},
            )
        except Exception as e:
            log_warning("Failed to broadcast comments_updated for page %s: %s", page_external_id, e)


def notify_ai_review_complete(page_external_id: str, persona: str, comment_count: int):
    """Broadcast AI review completion to all clients viewing the page."""
    channel_layer = get_channel_layer()
    if channel_layer:
        try:
            async_to_sync(channel_layer.group_send)(
                f"page_{page_external_id}",
                {"type": "ai_review_complete", "persona": persona, "comment_count": comment_count},
            )
        except Exception as e:
            log_warning("Failed to broadcast ai_review_complete for page %s: %s", page_external_id, e)


def notify_write_permission_revoked(page_external_id: str, user_id: int):
    """
    Notify WebSocket consumers that a user's write permission was revoked.

    This is called when a user's role is changed from editor to viewer.
    The WebSocket consumer will update its can_write flag and notify the client.

    Args:
        page_external_id: External ID of the page
        user_id: ID of the user whose write permission was revoked
    """
    channel_layer = get_channel_layer()
    if channel_layer:
        log_info(
            "Sending write_permission_revoked notification: page=%s, user_id=%s",
            page_external_id,
            user_id,
        )
        async_to_sync(channel_layer.group_send)(
            f"page_{page_external_id}",
            {
                "type": "write_permission_revoked",
                "user_id": user_id,
            },
        )
