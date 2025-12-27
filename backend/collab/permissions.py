"""
Access control for collaborative editing.
Validates user permissions using two-tier access control.
"""

from typing import Union

from asgiref.sync import sync_to_async
from django.contrib.auth import get_user_model

from backend.utils import log_debug, log_error, log_warning
from pages.models import Page

User = get_user_model()


async def can_access_page(user_or_id: Union[User, int], page_uuid: str) -> bool:  # type: ignore
    """
    Check if user can access the page via org membership or project editor.

    Two-tier access:
    - Tier 1: User is member of page's project's org
    - Tier 2: User is a project editor

    Args:
        user_or_id: User instance or user ID (int)
        page_uuid: External ID of the page

    Returns:
        bool: True if user has access via any tier
    """
    # Handle both User object and user_id (int)
    if isinstance(user_or_id, int):
        try:
            user = await User.objects.filter(id=user_or_id).afirst()
            if not user:
                log_warning(f"User with id {user_or_id} not found")
                return False
        except Exception as e:
            log_error(f"Error fetching user {user_or_id}: {e}")
            return False
    else:
        user = user_or_id

    log_debug(
        f"Checking access - User: {getattr(user, 'email', 'anonymous')}, "
        f"Page: {page_uuid}, Authenticated: {getattr(user, 'is_authenticated', False)}"
    )

    if not user or not user.is_authenticated:
        log_warning(f"Unauthenticated access attempt for page {page_uuid}")
        return False

    try:
        # Fetch page with related data for efficient checking (includes project editors)
        page = (
            await Page.objects.select_related("project__org")
            .prefetch_related("editors", "project__editors")
            .filter(external_id=page_uuid)
            .afirst()
        )

        if not page:
            log_warning(f"Page {page_uuid} does not exist")
            return False

        # Use the centralized permission helper (wrapped for async)
        from pages.permissions import user_can_access_page

        has_access = await sync_to_async(user_can_access_page)(user, page)

        if has_access:
            log_debug(f"Access granted: user {user.id} can access page {page_uuid}")
        else:
            log_warning(f"Access denied: user {user.id} cannot access page {page_uuid}")

        return has_access

    except Exception as e:
        log_error(f"Unexpected error in permissions check: {e}", exc_info=True)
        return False
