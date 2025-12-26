"""
Access control for collaborative editing.
Validates user permissions using three-tier access control.
"""

from asgiref.sync import sync_to_async
from django.contrib.auth import get_user_model

from backend.utils import log_debug, log_error, log_warning
from pages.models import Page

User = get_user_model()


async def can_access_page(user: User, page_uuid: str) -> bool:  # type: ignore
    """
    Check if user can access the page via org membership, project editor, OR page editors.

    Three-tier access:
    - Tier 1: User is member of page's project's org
    - Tier 2: User is a project editor
    - Tier 3: User is in page's editors

    Args:
        user: User instance
        page_uuid: External ID of the page

    Returns:
        bool: True if user has access via any tier
    """
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
