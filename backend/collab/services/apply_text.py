"""
Apply text content changes to the Yjs CRDT doc for a page from non-WS
callers (MCP, REST API, scripts).

Why this exists: the editor hydrates from the Yjs store (y_snapshots +
y_updates). `page.details["content"]` is a denormalized copy maintained
by `sync_snapshot_with_page`. Writes that only touch
`page.details["content"]` are invisible to any client whose Yjs doc is
already populated, and get overwritten by the next snapshot sync.

This module hydrates a Doc from the existing ystore, applies the
requested text change, persists the resulting CRDT update to y_updates,
and broadcasts an `external_update` channel-layer message. Connected
`PageYjsConsumer` instances apply the update to their own ydoc (to
prevent snapshot drift) AND forward the update to their WS client so the
editor merges the change live.

Critical design note: we do NOT broadcast a raw SYNC_UPDATE via the base
consumer's `send_message` type. `send_message` only forwards bytes to
the client — it does NOT apply to the consumer's `self.ydoc`. The
consumer's next snapshot (taken from self.ydoc with a watermark past the
injected update's row id) would then silently drop the update from
persistence. The update would appear live on connected screens, then
vanish on reload. Use the `external_update` handler instead, which both
applies and forwards.
"""

import enum
import logging
from typing import Literal

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.db import connection, transaction
from pycrdt import Doc, Text

from collab.locks import SEED_LOCK_NAMESPACE, advisory_lock_key_for_room
from collab.models import YSnapshot, YUpdate
from collab.permissions import can_edit_page

logger = logging.getLogger(__name__)

ApplyMode = Literal["overwrite", "append", "prepend"]


class ApplyResult(enum.Enum):
    """Outcome of `apply_text_to_room`.

    Distinguishing these three cases lets the task wrapper log them
    separately so dashboards can chart applied / no-op / denied volumes
    independently. Treating denial as just "no-op" hides revocation
    churn behind a stable success-rate metric.
    """

    APPLIED = "applied"
    NOOP = "noop"
    DENIED = "denied"


# The shared text key used by the CodeMirror editor. Must match the key
# the frontend y-codemirror binding uses (see frontend/src/collab/*).
YTEXT_KEY = "codemirror"

# Snapshots smaller than this are treated as empty/corrupt. Matches
# the guard in collab/consumers.py:make_ydoc.
MIN_VALID_SNAPSHOT_BYTES = 2


def _build_doc_from_store(room_id: str) -> Doc:
    """Hydrate a Doc from the latest snapshot + incremental updates."""
    doc = Doc()

    snapshot = YSnapshot.objects.filter(room_id=room_id).first()

    if snapshot is not None and len(bytes(snapshot.snapshot)) > MIN_VALID_SNAPSHOT_BYTES:
        doc.apply_update(bytes(snapshot.snapshot))
        updates_qs = YUpdate.objects.filter(room_id=room_id, id__gt=snapshot.last_update_id).order_by("id")
    else:
        updates_qs = YUpdate.objects.filter(room_id=room_id).order_by("id")

    for update_bytes in updates_qs.values_list("yupdate", flat=True):
        doc.apply_update(bytes(update_bytes))

    return doc


def apply_text_to_room(
    room_id: str,
    new_content: str,
    user_id: int,
    mode: ApplyMode = "overwrite",
) -> ApplyResult:
    """
    Apply `new_content` to the Yjs doc for `room_id` on behalf of `user_id`.

    Modes:
      - overwrite: replace all text with `new_content`
      - append:    insert `new_content` at end
      - prepend:   insert `new_content` at start

    Re-checks `can_edit_page` at execution time. The caller already
    verified permission when enqueuing, but the RQ task runs later in a
    separate process — access could be revoked in the meantime. Without
    this re-check the write would still land.

    Returns:
      - `ApplyResult.APPLIED` if a CRDT update was persisted and broadcast.
      - `ApplyResult.NOOP` if the requested change was already in effect
        (overwrite with identical content, empty append/prepend, or no
        captured updates from the transaction).
      - `ApplyResult.DENIED` if the execution-time `can_edit_page` check
        fails — the user has lost edit access since enqueue.
    """
    page_external_id = room_id.removeprefix("page_")
    if not async_to_sync(can_edit_page)(user_id, page_external_id):
        logger.info(
            "apply_text_to_room denied: user=%s lost edit access to room=%s",
            user_id,
            room_id,
        )
        return ApplyResult.DENIED

    # Serialize with the WS seed path (`_seed_ydoc_from_page` in
    # collab.consumers). Without this, two writers racing on a freshly-
    # empty room can each insert the same content with different Yjs
    # clientIDs and the CRDT merges both inserts into doubled text. The
    # lock is held for the duration of the surrounding transaction and
    # auto-releases on commit/rollback. Hydrate, compute, persist all
    # happen under the lock so a winning writer's row is visible to the
    # loser's in-lock recheck.
    with transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT pg_advisory_xact_lock(%s, %s)",
                [SEED_LOCK_NAMESPACE, advisory_lock_key_for_room(room_id)],
            )

        doc = _build_doc_from_store(room_id)
        ytext = doc.get(YTEXT_KEY, type=Text)

        captured: list[bytes] = []

        def _on_transaction(event) -> None:
            update_bytes = getattr(event, "update", None)
            if update_bytes:
                captured.append(bytes(update_bytes))

        # Subscribe AFTER hydration so replay updates are not re-captured.
        doc.observe(_on_transaction)

        current = str(ytext) if ytext else ""
        if mode == "overwrite":
            if current == new_content:
                return ApplyResult.NOOP
            if current:
                del ytext[0 : len(current)]
            if new_content:
                ytext.insert(0, new_content)
        elif mode == "append":
            if not new_content:
                return ApplyResult.NOOP
            ytext.insert(len(current), new_content)
        elif mode == "prepend":
            if not new_content:
                return ApplyResult.NOOP
            ytext.insert(0, new_content)
        else:
            raise ValueError(f"Invalid mode: {mode!r}")

        if not captured:
            return ApplyResult.NOOP

        # Persist first, then broadcast AFTER the DB commit so connected
        # consumers don't observe an update that isn't yet queryable by
        # reconnecting peers. `on_commit` fires when this atomic block
        # exits successfully.
        YUpdate.objects.bulk_create([YUpdate(room_id=room_id, yupdate=chunk) for chunk in captured])
        transaction.on_commit(lambda: _broadcast_external_updates(room_id, captured))

        logger.info(
            "Applied text update to room=%s user=%s mode=%s update_count=%s bytes=%s",
            room_id,
            user_id,
            mode,
            len(captured),
            sum(len(c) for c in captured),
        )
        return ApplyResult.APPLIED


def _broadcast_external_updates(room_id: str, updates: list[bytes]) -> None:
    """Broadcast each persisted Yjs update to connected consumers.

    Uses the `external_update` channel-layer message type handled by
    `PageYjsConsumer.external_update`, NOT the base consumer's
    `send_message`. The difference is critical:

      - `send_message`: forwards bytes to the WS client only. The
        consumer's server-side ydoc is NOT updated. On the next snapshot
        the update is silently dropped from persistence.
      - `external_update`: applies bytes to `self.ydoc` (suppressing
        re-persistence) AND forwards to the WS client. Snapshots stay
        consistent with y_updates.

    Channel-layer failures (Redis outage, etc.) are logged but not
    re-raised: the update is already in y_updates and will be picked
    up by reconnecting peers on the next hydration. Any earlier failure
    in this function (e.g. resolving the channel layer) is a logic bug
    and propagates so the RQ task surfaces it.
    """
    channel_layer = get_channel_layer()
    if channel_layer is None:
        return
    for update_bytes in updates:
        try:
            async_to_sync(channel_layer.group_send)(
                room_id,
                {"type": "external_update", "update": update_bytes},
            )
        except Exception as e:
            logger.error("Error broadcasting Yjs external_update for %s: %s", room_id, e)
