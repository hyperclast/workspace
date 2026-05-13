"""
Django Channels consumer for Yjs WebSocket sync with Postgres persistence.
Subclasses pycrdt-websocket's YjsConsumer.
"""

import asyncio
import json
from typing import Optional, Tuple

from asgiref.sync import sync_to_async
from django.conf import settings
from django.core.cache import cache
from django.db import connection, transaction
from django.utils import timezone
from pycrdt import Doc, Text, YMessageType, YSyncMessageType, create_update_message
from pycrdt.websocket.django_channels_consumer import YjsConsumer as BaseYjsConsumer

from backend.utils import (
    REQUEST_ID_PREFIX_WS,
    clear_request_id,
    log_debug,
    log_error,
    log_info,
    log_warning,
    set_request_id,
)

from .locks import SEED_LOCK_NAMESPACE, advisory_lock_key_for_room
from .models import YUpdate
from .permissions import can_access_page, can_edit_page
from .ystore import PostgresYStore, get_db_config_from_django


# WebSocket close codes
WS_CLOSE_RATE_LIMITED = 4029  # Too Many Requests (custom code)

# Shared ytext key the CodeMirror binding uses on the client. Must stay
# in lockstep with `frontend/src/collaboration.js` (`ydoc.getText("codemirror")`)
# and `collab/services/apply_text.py` (`YTEXT_KEY`). Bumping it here without
# updating those keeps the seed and the editor on different roots.
YTEXT_KEY = "codemirror"


class PageYjsConsumer(BaseYjsConsumer):
    """
    Handles real-time collaborative editing for pages.
    Room name: "page_<uuid>"
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        log_debug("PageYjsConsumer instantiated")
        self.user_id = None  # Will be set in connect()
        self.can_write = False  # Will be set in connect() - False means viewer (read-only)
        self.snapshot_task = None  # asyncio task handle for periodic snapshots
        self.has_unsaved_changes = False  # Flag for dirty tracking
        self.updates_since_snapshot = 0  # Counter for update-based snapshot trigger
        self.pending_writes = set()  # Track in-flight write tasks to await on disconnect
        # Set to True when applying an externally-injected update (from
        # collab.services.apply_text) so the transaction observer skips
        # re-persisting — the update is already in y_updates.
        self._suppress_persistence = False
        # Set to True when `_seed_ydoc_from_page` persisted (or read
        # back) a seed row but `doc.apply_update` raised, leaving the
        # local doc empty. Gates the empty-doc reconcile path: without
        # this guard, reconcile would see y_updates rows alongside an
        # empty local doc and erase `Page.details["content"]` — but the
        # doc is only empty because we could not decode the bytes, not
        # because the room is actually empty.
        self._seed_apply_failed = False

    # -----------------------------
    # Helpers
    # -----------------------------
    def make_room_name(self) -> str:
        # Base class calls this during connect() and uses the result as the group name
        page_uuid = self.scope["url_route"]["kwargs"]["page_uuid"]
        return f"page_{page_uuid}"

    async def _ensure_ystore(self) -> None:
        if getattr(self, "ystore", None) is None:
            db_config = get_db_config_from_django()
            self.ystore = PostgresYStore(self.make_room_name(), db_config)
            await self.ystore.initialize_pool()

    def _get_rate_limit_key(self) -> str:
        """Get the cache key for rate limiting based on user or IP."""
        user = self.scope.get("user")
        if user and user.is_authenticated:
            return f"ws_rate_user_{user.id}"
        # Fallback to IP for unauthenticated users
        client = self.scope.get("client", ("unknown", 0))
        return f"ws_rate_ip_{client[0]}"

    async def _check_rate_limit(self) -> Tuple[bool, int]:
        """
        Atomically check and increment the rate limit counter.
        Returns (allowed, current_count).

        Uses atomic cache operations to prevent TOCTOU race conditions where
        concurrent connections could exceed the limit by checking simultaneously
        before either increments the counter.
        """
        key = self._get_rate_limit_key()
        limit = getattr(settings, "WS_RATE_LIMIT_CONNECTIONS", 30)
        window = getattr(settings, "WS_RATE_LIMIT_WINDOW_SECONDS", 60)

        try:
            # Use atomic incr which increments and returns the new value in one operation
            try:
                new_count = await sync_to_async(cache.incr)(key)
            except ValueError:
                # Key doesn't exist - create it with initial value of 1
                # Use add() which only sets if key doesn't exist (atomic)
                added = await sync_to_async(cache.add)(key, 1, timeout=window)
                if added:
                    new_count = 1
                else:
                    # Another connection created it first, increment it
                    new_count = await sync_to_async(cache.incr)(key)

            # Check if we're over the limit AFTER incrementing
            if new_count > limit:
                log_warning(
                    "Rate limit exceeded: key=%s, count=%s, limit=%s",
                    key,
                    new_count,
                    limit,
                )
                return False, new_count

            return True, new_count
        except Exception as e:
            # If cache is unavailable, allow the connection but log the error
            log_warning("Rate limit check failed (allowing connection): %s", str(e))
            return True, 0

    # -----------------------------
    # Lifecycle
    # -----------------------------
    async def connect(self):
        """
        Check access, init persistence, then defer to the base connect (which constructs the Doc and starts sync).
        """
        # Set request ID for this WebSocket session (for log tracing)
        self.request_id = set_request_id(prefix=REQUEST_ID_PREFIX_WS)

        user = self.scope["user"]
        page_uuid = self.scope["url_route"]["kwargs"]["page_uuid"]

        # Log connection source details
        headers = dict(self.scope.get("headers", []))
        real_ip = (
            headers.get(b"cf-connecting-ip", b"").decode()
            or headers.get(b"x-forwarded-for", b"").decode().split(",")[0].strip()
            or headers.get(b"x-real-ip", b"").decode()
            or self.scope.get("client", ["unknown"])[0]
        )
        user_agent = headers.get(b"user-agent", b"unknown").decode()[:100]
        log_info(f"WS connect: page={page_uuid}, user={user}, ip={real_ip}, ua={user_agent}")

        # Rate limiting check (before any expensive operations)
        allowed, count = await self._check_rate_limit()
        if not allowed:
            log_warning(f"Rate limited: user={user}, page={page_uuid}, count={count}")
            # Accept briefly so client receives the close code
            await self.accept()
            await self.send(
                text_data='{"type":"error","code":"rate_limited","message":"Too many connections. Please try again later."}'
            )
            await self.close(code=WS_CLOSE_RATE_LIMITED)
            return

        # Access check
        has_access = await can_access_page(user, page_uuid)
        if not has_access:
            log_warning(f"Access denied for user {user} to page {page_uuid}")
            # Accept the connection briefly so client receives the close code
            # (Rejecting before accept means client only sees HTTP 403, not WS close code)
            await self.accept()
            await self.send(
                text_data='{"type":"error","code":"access_denied","message":"You do not have access to this page"}'
            )
            await self.close(code=4003)
            return

        log_info(f"Access granted for user {user} to page {page_uuid}")

        # Store user ID for access revocation checks
        self.user_id = user.id if user.is_authenticated else None

        # Check if user has write permission (editor role)
        # Viewers will have can_write=False and their SYNC_UPDATE messages will be rejected
        self.can_write = await can_edit_page(self.user_id, page_uuid) if self.user_id else False
        log_info(f"Write permission for user {user} to page {page_uuid}: {self.can_write}")

        # Prepare persistence *before* parent sets up the ydoc
        await self._ensure_ystore()

        # Track editor session for rewind
        if self.user_id and self.can_write:
            try:
                await self._create_editor_session(page_uuid)
            except Exception as e:
                log_error(f"Error creating editor session for page {page_uuid}: {e}", exc_info=True)

        # Join project-level group for folder sync
        try:
            from pages.models import Page

            page_obj = await sync_to_async(
                lambda: Page.objects.select_related("project").get(external_id=page_uuid, is_deleted=False)
            )()
            self.project_group = f"project_{page_obj.project.external_id}"
            await self.channel_layer.group_add(self.project_group, self.channel_name)
        except Exception as e:
            log_warning(f"Could not join project group for page {page_uuid}: {e}")

        # Hand off to parent: computes room_name, builds ydoc via make_ydoc(), joins group, accepts socket
        try:
            await super().connect()
            log_debug(f"Parent connect() completed successfully for page {page_uuid}")
        except Exception as e:
            log_error(f"Error in parent connect() for page {page_uuid}: {e}", exc_info=True)

    async def make_ydoc(self) -> Doc:
        """
        Build Doc, hydrate from store, then subscribe to transactions to persist incremental updates.
        Optimization: Load from snapshot + incremental updates if snapshot exists.
        """
        doc = Doc()

        # --- 1) Hydrate from persisted data (BEFORE subscribing to observer)
        if getattr(self, "ystore", None):
            room_name = self.make_room_name()
            log_debug("Hydrating Doc from store for room=%s", room_name)

            # Try to load from snapshot first
            snapshot_data = await self.ystore.get_snapshot()

            # Check if snapshot is valid (not corrupted 2-byte empty doc)
            valid_snapshot = False
            if snapshot_data:
                snapshot_bytes, last_update_id = snapshot_data
                if len(snapshot_bytes) <= 2:
                    log_warning(
                        "Invalid snapshot detected for %s (only %s bytes), falling back to full replay",
                        room_name,
                        len(snapshot_bytes),
                    )
                else:
                    valid_snapshot = True

            if valid_snapshot:
                log_debug("Loading snapshot (up to update %s)", last_update_id)

                # Apply the snapshot (single operation instead of thousands)
                doc.apply_update(snapshot_bytes)

                # Now apply only incremental updates since the snapshot
                incremental_count = 0
                async for update_bytes, _meta, _ts, _id in self.ystore.read_since(last_update_id):
                    doc.apply_update(update_bytes)
                    incremental_count += 1

                log_info(
                    "[PERF] Hydration via snapshot: room=%s, "
                    "snapshot_up_to_id=%s, "
                    "incremental_count=%s, "
                    "total_operations=%s",
                    room_name,
                    last_update_id,
                    incremental_count,
                    1 + incremental_count,
                )
            else:
                # No usable snapshot — load all updates from scratch. A
                # corrupt 2-byte snapshot falls through here too, so the
                # seed branch below covers that edge case as well when
                # update_count ends at 0.
                log_debug("No snapshot found for room=%s, loading all updates", room_name)
                update_count = 0
                async for update_bytes, _meta, _ts in self.ystore.read():
                    doc.apply_update(update_bytes)
                    update_count += 1

                if update_count == 0:
                    # Yjs store is empty for this room. Hydrate from
                    # Page.details["content"] so concurrent loaders don't
                    # each insert the same REST content with different
                    # Yjs clientIDs (which would double the page text).
                    # The helper persists the seed as a y_updates row;
                    # this runs BEFORE the observer is subscribed so the
                    # seed is not re-persisted on top of itself.
                    seeded = await self._seed_ydoc_from_page(doc)
                    if seeded:
                        update_count = 1

                log_info(
                    "[PERF] Hydration via full replay: room=%s, update_count=%s, total_operations=%s",
                    room_name,
                    update_count,
                    update_count,
                )

            # Connect-time reconcile for the stale-content edge case:
            # hydration left ytext empty but Page.details["content"] is
            # still the value a previous session wrote. Disconnect-time
            # reconcile is unreliable here because the empty-doc
            # snapshot skip never enqueues sync_snapshot_with_page, AND
            # the ASGI test harness can cancel the consumer task before
            # disconnect runs to completion (asgiref's receive_output
            # cancels the future on TimeoutError). Running the reconcile
            # during make_ydoc — synchronously, while the consumer task
            # is still alive — closes both gaps. The internal
            # `y_updates`-exists gate keeps a fail-opened seed from
            # erasing user content, and `_seed_apply_failed` keeps a
            # seed-bytes-decode failure from doing the same.
            if getattr(self, "ystore", None) and str(doc.get(YTEXT_KEY, type=Text)) == "":
                if self._seed_apply_failed:
                    log_warning(
                        "Skipping connect-time empty-doc reconcile: seed apply failed for room=%s",
                        room_name,
                    )
                else:
                    await self._reconcile_empty_page_content()

        # --- 2) NOW subscribe to observer for FUTURE updates only
        # Callback receives a TransactionEvent. The update bytes are in event.update
        def _on_transaction(event) -> None:
            """Called after each transaction commits. Extract and persist the update."""
            try:
                # Extract the update bytes from the event
                update_bytes = getattr(event, "update", None)
                if not update_bytes:
                    log_warning("Transaction event has no update bytes")
                    return

                log_debug("Doc transaction: %s bytes", len(update_bytes))

                # Persist asynchronously but track the task for cleanup.
                # Skip the ystore.write when applying an externally-injected
                # update — the caller already wrote the bytes to y_updates
                # (see external_update handler). We still need the dirty /
                # snapshot bookkeeping below so the periodic / threshold /
                # disconnect snapshot path runs and sync_snapshot_with_page
                # picks up the change. Without that, denormalized state
                # (links, mentions, file-links, rewind) goes stale until the
                # next human edit.
                if self._suppress_persistence:
                    log_debug("Suppressing persistence for external update: %s bytes", len(update_bytes))
                elif getattr(self, "ystore", None):
                    task = asyncio.create_task(self.ystore.write(update_bytes))
                    self.pending_writes.add(task)
                    task.add_done_callback(self.pending_writes.discard)
                    log_debug("Persistence task scheduled")

                # Mark document as having unsaved changes
                self.has_unsaved_changes = True

                # Increment update counter
                self.updates_since_snapshot += 1

                # Check if we've reached the edit count threshold for snapshot
                if self.updates_since_snapshot >= settings.CRDT_SNAPSHOT_AFTER_EDIT_COUNT:
                    log_info(
                        "Edit count threshold reached (%s updates), triggering snapshot for %s",
                        self.updates_since_snapshot,
                        self.room_name,
                    )
                    asyncio.create_task(self._take_snapshot())
                    # Reset flags immediately (will be set again if more edits occur before snapshot completes)
                    self.has_unsaved_changes = False
                    self.updates_since_snapshot = 0
                else:
                    # Schedule periodic snapshot if not already scheduled
                    self._schedule_periodic_snapshot()
            except Exception as e:
                log_error("Error in transaction observer: %s", e, exc_info=True)

        # Register the observer (sync callback) - AFTER hydration
        try:
            doc.observe(_on_transaction)
            log_debug("Subscribed to Doc transactions")
        except Exception as e:
            log_error("Failed to subscribe to Doc transactions: %s", e, exc_info=True)

        return doc

    def _schedule_periodic_snapshot(self):
        """
        Schedule a snapshot to run after CRDT_SNAPSHOT_INTERVAL_SECONDS
        if one isn't already scheduled.
        """
        # If timer already running, don't schedule another
        if self.snapshot_task and not self.snapshot_task.done():
            return

        # Schedule snapshot
        self.snapshot_task = asyncio.create_task(self._periodic_snapshot_worker())
        log_debug("Scheduled periodic snapshot for %s", self.room_name)

    async def _periodic_snapshot_worker(self):
        """Worker that waits for interval, then takes snapshot if dirty."""
        try:
            await asyncio.sleep(settings.CRDT_SNAPSHOT_INTERVAL_SECONDS)

            # Only snapshot if there are unsaved changes
            if self.has_unsaved_changes:
                await self._take_snapshot()
                self.has_unsaved_changes = False
                log_info("Periodic snapshot completed for %s", self.room_name)
            else:
                log_debug("No changes to snapshot for %s", self.room_name)
        except asyncio.CancelledError:
            log_debug("Snapshot worker cancelled for %s", self.room_name)
        except Exception as e:
            log_error("Error in periodic snapshot worker: %s", e, exc_info=True)

    async def _take_snapshot(self, is_session_end=False) -> bool:
        """
        Take a snapshot and sync with page.
        Returns True if snapshot was saved, False if skipped (empty doc).
        """
        if not getattr(self, "ydoc", None) or not getattr(self, "ystore", None):
            return False

        try:
            snapshot_bytes = self.ydoc.get_update()

            # Skip saving empty/minimal snapshots - they cause client sync issues
            # An empty Yjs doc produces a 2-byte 0x0000 update which crashes y-websocket
            if len(snapshot_bytes) <= 2:
                log_info(
                    "Skipping empty snapshot for %s (only %s bytes) - prevents client crash",
                    self.room_name,
                    len(snapshot_bytes),
                )
                # The snapshot upsert is skipped here, which means
                # `sync_snapshot_with_page` (enqueued from
                # `ystore.upsert_snapshot`) does not run and
                # `Page.details["content"]` keeps whatever non-empty
                # value the previous snapshot wrote. Reconcile inline
                # so the page row reflects the now-empty CRDT state.
                # Skip when the seed apply failed at hydration: the
                # ydoc looks empty only because we could not decode
                # the bytes we (or another writer) persisted, not
                # because the room is actually empty. See
                # `_seed_apply_failed` in `__init__`.
                if self._seed_apply_failed:
                    log_warning(
                        "Skipping snapshot-skip empty-doc reconcile: seed apply failed for room=%s",
                        self.room_name,
                    )
                else:
                    await self._reconcile_empty_page_content()
                return False

            max_id = await self.ystore.get_max_update_id() or 0
            await self.ystore.upsert_snapshot(snapshot_bytes, max_id, is_session_end=is_session_end)

            # Reset the update counter after successful snapshot
            self.updates_since_snapshot = 0

            log_info(
                "Snapshot created for %s: max_id=%s",
                self.room_name,
                max_id,
            )
            return True
        except Exception as e:
            log_error("Error taking snapshot: %s", e, exc_info=True)
            return False

    async def _reconcile_empty_page_content(self) -> bool:
        """Clear stale `Page.details["content"]` when the CRDT has drained empty.

        The empty-doc snapshot skip in `_take_snapshot` does not write
        through `ystore.upsert_snapshot`, so `sync_snapshot_with_page`
        is never enqueued and `Page.details["content"]` retains the
        non-empty value the previous snapshot wrote. The REST page
        payload then carries that stale content into every subsequent
        page load even though the CRDT is empty — the editor briefly
        renders the stale REST body before the WS sync arrives and
        wipes it back out, and any tooling that reads `details.content`
        directly (Ask, search, exports) sees the wrong text indefinitely.

        Reconciliation runs only when at least one `y_updates` row
        exists for the room. That gate distinguishes "the room was
        edited down to empty" (safe to reconcile) from "the
        server-side seed fail-opened on a fresh room and the doc is
        empty because nothing was ever written" (must NOT clobber
        `details.content` — the next opener should retry the seed).

        Returns True when a write actually happened. Idempotent on
        repeat calls because `details.content` already being empty
        short-circuits.
        """
        page_external_id = self.room_name.removeprefix("page_")
        room_id = self.room_name

        @sync_to_async
        def _reconcile() -> bool:
            from core.helpers import hashify
            from filehub.models import FileLink
            from pages.models import Page, PageLink, PageMention

            if not YUpdate.objects.filter(room_id=room_id).exists():
                return False

            try:
                page = Page.objects.get(external_id=page_external_id, is_deleted=False)
            except Page.DoesNotExist:
                return False
            if page.is_pdf:
                return False

            details = page.details or {}
            if not details.get("content"):
                return False

            page.details["content"] = ""
            page.details["content_hash"] = hashify("")
            page.save(update_fields=["details", "modified"])

            PageLink.objects.sync_parsed_links(page, [])
            PageMention.objects.sync_parsed_mentions(page, [])
            FileLink.objects.sync_parsed_file_links(page, [])
            return True

        try:
            reconciled = await _reconcile()
        except Exception as e:
            log_error(
                "Error reconciling empty page content for %s: %s",
                self.room_name,
                e,
                exc_info=True,
            )
            return False

        if reconciled:
            log_info(
                "[RECONCILE] Cleared stale details.content for empty room=%s",
                self.room_name,
            )
        return reconciled

    async def _create_editor_session(self, page_uuid):
        """Create a RewindEditorSession row for rewind attribution."""
        from pages.models import Page
        from pages.models.rewind import RewindEditorSession

        @sync_to_async
        def _create():
            try:
                page = Page.objects.get(external_id=page_uuid, is_deleted=False)
                session = RewindEditorSession.objects.create(
                    page=page,
                    user_id=self.user_id,
                )
                return session.id
            except Page.DoesNotExist:
                return None

        self._editor_session_id = await _create()

    async def _close_editor_session(self):
        """Set disconnected_at on the editor session."""
        from pages.models.rewind import RewindEditorSession

        session_id = getattr(self, "_editor_session_id", None)
        if not session_id:
            return

        @sync_to_async
        def _close():
            RewindEditorSession.objects.filter(id=session_id).update(disconnected_at=timezone.now())

        await _close()

    async def _seed_ydoc_from_page(self, doc: Doc) -> bool:
        """Seed `doc` from `Page.details["content"]` and persist the seed.

        Called from `make_ydoc()` when hydration finds no usable state in
        the Yjs store. Without coordination, two browsers connecting to
        the same empty room would each insert the same REST content with
        different Yjs clientIDs; the CRDT keeps both, doubling the page.

        Single-writer-per-room is enforced via a Postgres advisory
        transaction lock keyed on a hash of `room_name`. The lock
        acquisition, the `y_updates` recheck, and the seed insert all
        run inside one `transaction.atomic` block on Django's DB
        connection, so the lock and the persisted row commit together
        and the lock auto-releases on commit. Two consumers racing on
        the same room produce:

          - **Winner**: acquires the lock first, finds `y_updates`
            still empty, inserts the seed row, commits. Then applies
            the seed bytes to its local `doc` and returns True.
          - **Loser**: blocks on the lock until the winner commits,
            then finds the winner's row in `y_updates`, applies those
            bytes to its local `doc` (keeping its server-side ydoc
            consistent with persistence), and returns True without
            writing a new row.

        Returns False when there is nothing to seed (page missing,
        soft-deleted, PDF, or empty `details.content`) or when the
        seed transaction raises. PDF pages store their body in
        `details.extracted_text`, not `details.content`, so seeding
        from `details.content` for a PDF would inject the empty v2
        markdown wrapper into the editor.
        """
        page_external_id = self.room_name.removeprefix("page_")
        room_id = self.room_name

        @sync_to_async
        def _seed_under_lock():
            from pages.models import Page

            try:
                page = Page.objects.only("details").get(
                    external_id=page_external_id,
                    is_deleted=False,
                )
            except Page.DoesNotExist:
                return None, None
            if page.is_pdf:
                return None, None
            content = (page.details or {}).get("content") or None
            if not content:
                return None, None

            lock_key = advisory_lock_key_for_room(room_id)

            with transaction.atomic():
                with connection.cursor() as cursor:
                    cursor.execute(
                        "SELECT pg_advisory_xact_lock(%s, %s)",
                        [SEED_LOCK_NAMESPACE, lock_key],
                    )

                existing = list(
                    YUpdate.objects.filter(room_id=room_id).order_by("id").values_list("yupdate", flat=True)
                )
                if existing:
                    return [bytes(chunk) for chunk in existing], "loser"

                seed_doc = Doc()
                ytext = seed_doc.get(YTEXT_KEY, type=Text)
                ytext.insert(0, content)
                seed_update = bytes(seed_doc.get_update())

                YUpdate.objects.create(room_id=room_id, yupdate=seed_update)
                return [seed_update], "winner"

        try:
            result_updates, role = await _seed_under_lock()
        except Exception as e:
            log_error(
                "Error seeding ydoc for room=%s: %s",
                self.room_name,
                e,
                exc_info=True,
            )
            return False

        if not result_updates:
            return False

        try:
            for chunk in result_updates:
                doc.apply_update(chunk)
        except Exception as e:
            # The seed bytes are committed to y_updates (winner) or were
            # authored by another writer (loser), but applying them to
            # the local doc raised — likely a pycrdt parse error from a
            # version skew or, in practice, never. Fail open like the
            # other branches of this helper, and flag the consumer so
            # the empty-doc reconcile does NOT clear Page.details based
            # on this consumer's (now-misleading) empty local doc.
            log_error(
                "Failed to apply seed bytes to local doc for room=%s role=%s: %s",
                self.room_name,
                role,
                e,
                exc_info=True,
            )
            self._seed_apply_failed = True
            return False

        log_info(
            "[SEED] room=%s role=%s update_count=%s total_bytes=%s",
            self.room_name,
            role,
            len(result_updates),
            sum(len(c) for c in result_updates),
        )
        return True

    async def receive(self, text_data=None, bytes_data=None):
        """
        Filter incoming messages. Reject write operations from viewers
        BEFORE broadcasting to prevent state divergence.

        IMPORTANT: Filtering must happen here, not in _on_transaction(), because:
        1. super().receive() broadcasts to all clients AND applies to server ydoc
        2. If we filter later, other clients already have the change
        3. Result: State divergence - changes visible during session but lost on reconnect
        """
        # Restore request ID context for this message (may be lost in async boundaries)
        if hasattr(self, "request_id"):
            set_request_id(self.request_id)

        # Check for write operations from viewers
        if bytes_data is not None and not self.can_write:
            # Check if this is a sync update (write operation)
            # Yjs protocol: first byte is message type, second byte is sync message type
            if len(bytes_data) > 1 and bytes_data[0] == YMessageType.SYNC:
                sync_type = bytes_data[1]
                # SYNC_UPDATE (value=2) contains actual document changes
                if sync_type == YSyncMessageType.SYNC_UPDATE:
                    log_warning(
                        "Rejecting write from viewer: user_id=%s, room=%s",
                        self.user_id,
                        getattr(self, "room_name", "unknown"),
                    )
                    # Send error message to client
                    await self.send(
                        text_data='{"type":"error","code":"read_only","message":"You have view-only access to this page"}'
                    )
                    return  # Don't process this message - prevents broadcast AND persistence

        # Proceed with normal receive (broadcasts to group and applies to ydoc)
        await super().receive(text_data, bytes_data)

        if bytes_data is not None:
            log_debug("Received WebSocket message: %s bytes", len(bytes_data))

    async def disconnect(self, close_code):
        """
        On disconnect, wait for pending writes, cancel periodic snapshot timer, take final snapshot (if needed), and close the pool.
        """
        # Restore request ID context for disconnect logging
        if hasattr(self, "request_id"):
            set_request_id(self.request_id)

        log_info(
            "WS disconnect: room=%s, close_code=%s, user=%s",
            getattr(self, "room_name", "unknown"),
            close_code,
            self.user_id,
        )
        try:
            # Wait for all pending write tasks to complete (with timeout)
            if self.pending_writes:
                pending_count = len(self.pending_writes)
                log_info(
                    "Waiting for %s pending writes to complete for %s",
                    pending_count,
                    getattr(self, "room_name", "unknown"),
                )
                try:
                    await asyncio.wait_for(asyncio.gather(*self.pending_writes, return_exceptions=True), timeout=5.0)
                    log_info("All pending writes completed for %s", getattr(self, "room_name", "unknown"))
                except asyncio.TimeoutError:
                    log_warning("Timeout waiting for pending writes for %s", getattr(self, "room_name", "unknown"))

            # Cancel periodic snapshot task if running
            if self.snapshot_task and not self.snapshot_task.done():
                self.snapshot_task.cancel()
                try:
                    await self.snapshot_task
                except asyncio.CancelledError:
                    pass
                log_debug("Periodic snapshot task cancelled for %s", self.room_name)

            # Close editor session for rewind
            if self.user_id and self.can_write:
                try:
                    await self._close_editor_session()
                except Exception as e:
                    log_error("Error closing editor session: %s", e, exc_info=True)

            # Take final snapshot ONLY if there are unsaved changes OR no snapshot exists yet
            if getattr(self, "ydoc", None) is not None and getattr(self, "ystore", None):
                # Only snapshot if we have unsaved changes OR no snapshot exists
                # Check for existing snapshot to avoid redundant writes
                should_snapshot = self.has_unsaved_changes

                if not should_snapshot:
                    # Only check for existing snapshot if we don't already know we need to snapshot
                    try:
                        existing_snapshot = await self.ystore.get_snapshot()
                        should_snapshot = not existing_snapshot
                    except Exception as e:
                        # If we can't check, err on the side of creating a snapshot
                        log_warning("Could not check for existing snapshot: %s", e)
                        should_snapshot = True

                if should_snapshot:
                    saved = await self._take_snapshot(is_session_end=True)
                    if saved:
                        log_info("Final snapshot taken on disconnect for %s", self.room_name)
                else:
                    log_debug("No changes since last snapshot, skipping final snapshot for %s", self.room_name)

                # `_take_snapshot`'s empty-doc skip branch only
                # reconciles when the serialized doc is ≤2 bytes
                # (the byte threshold that triggers the y-websocket
                # client crash). A *collaboratively*-emptied doc
                # carries CRDT tombstones and serializes well above
                # that threshold even though `str(ytext) == ""`, so
                # the skip branch never runs. In that path
                # `upsert_snapshot` did fire and
                # `sync_snapshot_with_page` would normally clear
                # `details.content` to `""`, but the call to
                # `sync_snapshot_with_page` is enqueued from inside
                # async code and can be swallowed in environments
                # where the synchronous fallback fails (tests; rare
                # production edge cases). Gating this reconcile on
                # the actual ytext content closes both gaps with one
                # idempotent write.
                try:
                    ytext_content = str(self.ydoc.get("codemirror", type=Text))
                except Exception as exc:
                    log_warning(
                        "Could not capture ydoc text on disconnect for %s: %s",
                        getattr(self, "room_name", "unknown"),
                        exc,
                    )
                else:
                    # Skip the reconcile if the seed apply failed at
                    # hydration: the ydoc may look empty only because we
                    # could not decode the bytes we (or another writer)
                    # persisted, not because the room is actually empty.
                    # See `_seed_apply_failed` in `__init__`.
                    if len(ytext_content) == 0:
                        if self._seed_apply_failed:
                            log_warning(
                                "Skipping disconnect-time empty-doc reconcile: seed apply failed for room=%s",
                                getattr(self, "room_name", "unknown"),
                            )
                        else:
                            await self._reconcile_empty_page_content()

            # Close the ystore pool
            if getattr(self, "ystore", None):
                await self.ystore.close_pool()
        except Exception as e:
            log_error("Error during disconnect cleanup: %s", e, exc_info=True)

        # Leave project group
        if hasattr(self, "project_group"):
            try:
                await self.channel_layer.group_discard(self.project_group, self.channel_name)
            except Exception as e:
                log_warning("Error leaving project group: %s", e)

        # Only call parent disconnect if we had a ydoc (i.e., fully connected)
        if getattr(self, "ydoc", None) is not None:
            try:
                await super().disconnect(close_code)
            except Exception as e:
                log_error("Error in parent disconnect: %s", e, exc_info=True)

        # Clear request ID context
        clear_request_id()

    async def access_revoked(self, event):
        """
        Handle access revocation message from the channel layer.
        Re-check if user still has access (they might have project-level access even after
        losing org membership). Only close if they truly lost all access.
        """
        revoked_user_id = event.get("user_id")

        if self.user_id and self.user_id == revoked_user_id:
            # Re-check if user still has access via other means (e.g., project editor)
            page_external_id = self.room_name.replace("page_", "")
            still_has_access = await can_access_page(self.user_id, page_external_id)

            if not still_has_access:
                log_info(f"Access revoked for user {self.user_id}, closing WebSocket")

                # Send a custom message to the client before closing
                await self.send(
                    text_data='{"type":"access_revoked","message":"Your access to this page has been revoked"}'
                )

                # Close the connection with a custom code
                await self.close(code=4001)  # Custom close code for access revocation
            else:
                log_debug(f"User {self.user_id} still has access via other means, not closing")

    async def write_permission_revoked(self, event):
        """
        Handle write permission revocation message from the channel layer.
        Called when a user's role is changed from editor to viewer.
        Updates the can_write flag and notifies the client.
        """
        revoked_user_id = event.get("user_id")

        if self.user_id and self.user_id == revoked_user_id:
            log_info(f"Write permission revoked for user {self.user_id}, setting can_write=False")

            # Update the can_write flag so future write attempts are rejected
            self.can_write = False

            # Notify the client that they now have view-only access
            await self.send(
                text_data='{"type":"write_permission_revoked","message":"Your access has been changed to view-only"}'
            )

    async def rewind_restored(self, event):
        """
        Handle rewind_restored message from the channel layer.
        Notify the client that the page was restored and close the connection
        so they reconnect with the restored content.
        """
        log_info(f"Rewind restored for {getattr(self, 'room_name', 'unknown')}, closing WS")
        await self.send(text_data='{"type":"rewind_restored","message":"Page has been restored to a previous rewind"}')
        await self.close(code=4002)

    async def links_updated(self, event):
        """
        Handle links_updated message from the channel layer.
        Notify the client that page links have been updated so it can refresh the Ref sidebar.
        """
        page_id = event.get("page_id", "")
        log_debug(f"Sending links_updated to client for page {page_id}")
        await self.send(text_data=json.dumps({"type": "links_updated", "page_id": page_id}))

    async def rewind_created(self, event):
        """Forward rewind_created to the WebSocket client."""
        await self.send(
            text_data=json.dumps(
                {
                    "type": "rewind_created",
                    "page_id": event.get("page_id", ""),
                    "rewind": event.get("rewind", {}),
                }
            )
        )

    async def folders_updated(self, event):
        """
        Handle folders_updated broadcast from the project channel layer.
        Notify the client to refetch the folder tree.
        """
        await self.send(text_data='{"type":"folders_updated"}')

    async def comments_updated(self, event):
        """
        Handle comments_updated broadcast from the page channel layer.
        Notify the client to refetch comments.
        """
        await self.send(text_data='{"type":"comments_updated"}')

    async def ai_review_complete(self, event):
        """
        Handle ai_review_complete broadcast from the page channel layer.
        Notify the client that an AI persona review has finished.
        """
        await self.send(
            text_data=json.dumps(
                {
                    "type": "ai_review_complete",
                    "persona": event["persona"],
                    "comment_count": event["comment_count"],
                }
            )
        )

    async def external_update(self, event):
        """
        Handle an externally-injected Yjs update (from MCP/REST via
        collab.services.apply_text).

        The update is already persisted to y_updates by the caller. We must:

        1. Apply it to self.ydoc so the server-side doc stays in sync with
           persistence. If we don't, this consumer's snapshot on disconnect
           would not contain the update (the snapshot is taken from self.ydoc
           with a watermark past the update's id), silently dropping the
           external write from the next hydration.
        2. Forward it to this consumer's client as a SYNC_UPDATE message so
           the editor reflects the change live.

        If applying to self.ydoc fails, we MUST NOT forward the bytes to
        the client. Forwarding a divergent update would leave the client
        merged ahead of the server's ydoc; the next disconnect snapshot
        would then be taken from a stale self.ydoc, with the watermark
        already past the external update's row id, silently dropping the
        external write from the next hydration. Instead, we signal the
        client to resync (it can choose to reconnect); the persisted
        update will be picked up on hydration.

        We must NOT re-persist the update — `_suppress_persistence` tells the
        transaction observer to skip its usual ystore.write() call.
        """
        update_bytes = event.get("update")
        if not update_bytes:
            log_warning("external_update event missing update bytes for %s", getattr(self, "room_name", "unknown"))
            return

        if getattr(self, "ydoc", None) is None:
            log_debug(
                "external_update received before ydoc ready for %s, dropping", getattr(self, "room_name", "unknown")
            )
            return

        # Apply to server-side ydoc without re-persisting. The observer
        # fires synchronously during apply_update, so this flag is race-free.
        try:
            self._suppress_persistence = True
            try:
                self.ydoc.apply_update(update_bytes)
            finally:
                self._suppress_persistence = False
        except Exception as e:
            log_error(
                "Error applying external update to ydoc for %s: %s; not forwarding to client",
                self.room_name,
                e,
                exc_info=True,
            )
            # Do NOT forward divergent bytes. Tell the client to resync so it
            # can choose to reconnect and rehydrate from persisted state.
            try:
                await self.send(
                    text_data='{"type":"error","code":"resync_required","message":"Server failed to apply update; please reconnect to resync."}'
                )
            except Exception as send_err:
                log_error(
                    "Error sending resync_required to client for %s: %s",
                    self.room_name,
                    send_err,
                    exc_info=True,
                )
            return

        # Forward to the WS client as a Yjs SYNC_UPDATE so the editor merges.
        try:
            await self.send(bytes_data=create_update_message(update_bytes))
            log_debug("Forwarded external_update (%s bytes) to client for %s", len(update_bytes), self.room_name)
        except Exception as e:
            log_error("Error forwarding external_update to client for %s: %s", self.room_name, e, exc_info=True)
