import logging

from django.conf import settings
from django.db import transaction
from django.db.models import F, Q
from django.utils import timezone

from pages.models import Page
from pages.models.rewind import Rewind, RewindEditorSession


logger = logging.getLogger(__name__)


def maybe_create_rewind(page, content, content_hash, is_session_end=False):
    """
    Conditionally create a Rewind snapshot.

    Rules:
    1. Content must differ from the latest rewind (content_hash dedup).
    2. At least REWIND_MIN_INTERVAL_SECONDS since last rewind, unless:
       a. Content size changed by more than REWIND_SIGNIFICANT_CHANGE_BYTES.
       b. is_session_end=True (last editor disconnected).
    3. Respects REWIND_MAX_PER_PAGE cap.
    """
    latest = (
        Rewind.objects.filter(page=page)
        .order_by("-rewind_number")
        .values("content_hash", "created", "content_size_bytes")
        .first()
    )

    # 1. Dedup: skip if content hasn't changed
    if latest and latest["content_hash"] == content_hash:
        return None

    content_size = len(content.encode("utf-8"))

    # 2. Time threshold check (with bypasses)
    if latest:
        elapsed = (timezone.now() - latest["created"]).total_seconds()
        min_interval = getattr(settings, "REWIND_MIN_INTERVAL_SECONDS", 60)

        if elapsed < min_interval:
            # Bypass: significant content change
            size_diff = abs(content_size - latest["content_size_bytes"])
            significant_threshold = getattr(settings, "REWIND_SIGNIFICANT_CHANGE_BYTES", 500)

            if not is_session_end and size_diff < significant_threshold:
                return None

    # 3. Check max rewinds cap
    max_rewinds = getattr(settings, "REWIND_MAX_PER_PAGE", 50000)
    rewind_count = Rewind.objects.filter(page=page).count()
    if rewind_count >= max_rewinds:
        logger.warning(
            "Rewind cap reached for page %s (%d rewinds)",
            page.external_id,
            rewind_count,
        )
        return None

    # Collect editors from recent sessions
    editors = _collect_editors(page, latest)

    # Create rewind
    with transaction.atomic():
        # Atomic increment — PostgreSQL's UPDATE SET col = col + 1 takes an
        # implicit row-level lock, so a concurrent task waits for this one
        # to commit before reading the already-incremented value.
        Page.objects.filter(id=page.id).update(current_rewind_number=F("current_rewind_number") + 1)
        new_rewind_number = Page.objects.values_list("current_rewind_number", flat=True).get(id=page.id)

        rewind = Rewind.objects.create(
            page=page,
            content=content,
            content_hash=content_hash,
            title=page.title,
            content_size_bytes=content_size,
            rewind_number=new_rewind_number,
            editors=editors,
        )

    # Sync the caller's in-memory page object
    page.current_rewind_number = new_rewind_number

    logger.info(
        "Created rewind %d for page %s (hash=%s, editors=%s)",
        rewind.rewind_number,
        page.external_id,
        content_hash[:12],
        editors,
    )
    return rewind


def _collect_editors(page, latest_rewind):
    """
    Collect external_ids of users who edited since the last rewind.

    A session is considered active during the period since the last rewind if:
    - It started after the last rewind (connected_at >= rewind_time), OR
    - It is still open (disconnected_at IS NULL), OR
    - It ended after the last rewind (disconnected_at >= rewind_time)
    """
    qs = RewindEditorSession.objects.filter(page=page)

    if latest_rewind:
        rewind_time = latest_rewind["created"]
        qs = qs.filter(
            Q(connected_at__gte=rewind_time) | Q(disconnected_at__isnull=True) | Q(disconnected_at__gte=rewind_time)
        )

    user_external_ids = list(qs.values_list("user__external_id", flat=True).distinct())

    return [str(eid) for eid in user_external_ids]
