"""
Access control for collaborative editing.

Validates user permissions using three-tier access control:
- Tier 1: Organization level (org admin, org member if enabled)
- Tier 2: Project level (project editor/viewer roles)
- Tier 3: Page level (page editor/viewer roles)

See docs/sharing.md for full documentation.
"""

from typing import Union

from asgiref.sync import sync_to_async
from django.contrib.auth import get_user_model

from backend.utils import log_debug, log_error, log_warning
from pages.models import Page

User = get_user_model()


async def can_access_page(user_or_id: Union[User, int], page_uuid: str) -> bool:  # type: ignore
    """
    Check if user can access the page for reading (WebSocket connection).

    Three-tier access (access granted if ANY condition is met):
    - Tier 1: Org level - User is org admin, or org member with org_members_can_access=True
    - Tier 2: Project level - User is a project editor (admin/editor/viewer role)
    - Tier 3: Page level - User is a page editor (admin/editor/viewer role)

    Args:
        user_or_id: User instance or user ID (int)
        page_uuid: External ID of the page

    Returns:
        bool: True if user has read access via any tier
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


async def can_edit_page(user_or_id: Union[User, int], page_uuid: str) -> bool:  # type: ignore
    """
    Check if user has write permission for a page (can send Yjs updates).

    Three-tier access with roles (write access granted if ANY condition is met):
    - Tier 1: Org level - User is org admin, or org member with org_members_can_access=True
    - Tier 2: Project level - User is a project editor with 'admin' or 'editor' role (NOT 'viewer')
    - Tier 3: Page level - User is a page editor with 'admin' or 'editor' role (NOT 'viewer')

    Args:
        user_or_id: User instance or user ID (int)
        page_uuid: External ID of the page

    Returns:
        bool: True if user has write access, False for viewers (read-only)
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
        f"Checking write permission - User: {getattr(user, 'email', 'anonymous')}, "
        f"Page: {page_uuid}, Authenticated: {getattr(user, 'is_authenticated', False)}"
    )

    if not user or not user.is_authenticated:
        log_warning(f"Unauthenticated write attempt for page {page_uuid}")
        return False

    try:
        # Fetch page with related data for efficient checking
        page = (
            await Page.objects.select_related("project__org")
            .prefetch_related("editors", "project__editors")
            .filter(external_id=page_uuid, is_deleted=False)
            .afirst()
        )

        if not page:
            log_warning(f"Page {page_uuid} does not exist or is deleted")
            return False

        # Use the centralized permission helper (wrapped for async)
        from pages.permissions import user_can_edit_in_page

        can_edit = await sync_to_async(user_can_edit_in_page)(user, page)

        if can_edit:
            log_debug(f"Write access granted: user {user.id} can edit page {page_uuid}")
        else:
            log_debug(f"Write access denied: user {user.id} is viewer for page {page_uuid}")

        return can_edit

    except Exception as e:
        log_error(f"Unexpected error in write permission check: {e}", exc_info=True)
        return False
