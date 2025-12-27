"""
Django Channels consumer for Yjs WebSocket sync with Postgres persistence.
Subclasses pycrdt-websocket's YjsConsumer.
"""

import asyncio
from typing import Optional, Tuple

from asgiref.sync import sync_to_async
from django.conf import settings
from django.core.cache import cache
from pycrdt import Doc
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

from .permissions import can_access_page
from .ystore import PostgresYStore, get_db_config_from_django


# WebSocket close codes
WS_CLOSE_RATE_LIMITED = 4029  # Too Many Requests (custom code)


class PageYjsConsumer(BaseYjsConsumer):
    """
    Handles real-time collaborative editing for pages.
    Room name: "page_<uuid>"
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        log_debug("PageYjsConsumer instantiated")
        self.user_id = None  # Will be set in connect()
        self.snapshot_task = None  # asyncio task handle for periodic snapshots
        self.has_unsaved_changes = False  # Flag for dirty tracking
        self.updates_since_snapshot = 0  # Counter for update-based snapshot trigger
        self.pending_writes = set()  # Track in-flight write tasks to await on disconnect

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
        Check if the connection is within rate limits.
        Returns (allowed, current_count).
        """
        key = self._get_rate_limit_key()
        limit = getattr(settings, "WS_RATE_LIMIT_CONNECTIONS", 30)
        window = getattr(settings, "WS_RATE_LIMIT_WINDOW_SECONDS", 60)

        # Use sync_to_async for cache operations (they're synchronous)
        current = await sync_to_async(cache.get)(key, 0)

        if current >= limit:
            log_warning(
                "Rate limit exceeded: key=%s, count=%s, limit=%s",
                key,
                current,
                limit,
            )
            return False, current

        # Increment counter
        await sync_to_async(cache.set)(key, current + 1, timeout=window)
        return True, current + 1

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
            await self.close(code=WS_CLOSE_RATE_LIMITED)
            return

        # Access check
        has_access = await can_access_page(user, page_uuid)
        if not has_access:
            log_warning(f"Access denied for user {user} to page {page_uuid}")
            await self.close(code=4003)  # Reject without accepting
            return

        log_info(f"Access granted for user {user} to page {page_uuid}")

        # Store user ID for access revocation checks
        self.user_id = user.id if user.is_authenticated else None

        # Prepare persistence *before* parent sets up the ydoc
        await self._ensure_ystore()

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
                # No snapshot exists, fall back to loading all updates
                log_debug("No snapshot found for room=%s, loading all updates", room_name)
                update_count = 0
                async for update_bytes, _meta, _ts in self.ystore.read():
                    doc.apply_update(update_bytes)
                    update_count += 1
                log_info(
                    "[PERF] Hydration via full replay: room=%s, " "update_count=%s, " "total_operations=%s",
                    room_name,
                    update_count,
                    update_count,
                )

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

                # Persist asynchronously but track the task for cleanup
                if getattr(self, "ystore", None):
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

    async def _take_snapshot(self) -> bool:
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
                return False

            max_id = await self.ystore.get_max_update_id() or 0
            await self.ystore.upsert_snapshot(snapshot_bytes, max_id)

            # Cleanup old updates
            deleted = await self.ystore.delete_updates_before_snapshot()

            # Reset the update counter after successful snapshot
            self.updates_since_snapshot = 0

            log_info(
                "Snapshot created for %s: max_id=%s, cleaned_up=%s updates",
                self.room_name,
                max_id,
                deleted,
            )
            return True
        except Exception as e:
            log_error("Error taking snapshot: %s", e, exc_info=True)
            return False

    async def receive(self, text_data=None, bytes_data=None):
        """
        Let the base class handle the Yjs protocol; we only log sizes.
        Persistence is doc-observer-driven.
        """
        # Restore request ID context for this message (may be lost in async boundaries)
        if hasattr(self, "request_id"):
            set_request_id(self.request_id)

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
                    saved = await self._take_snapshot()
                    if saved:
                        log_info("Final snapshot taken on disconnect for %s", self.room_name)
                else:
                    log_debug("No changes since last snapshot, skipping final snapshot for %s", self.room_name)

            # Close the ystore pool
            if getattr(self, "ystore", None):
                await self.ystore.close_pool()
        except Exception as e:
            log_error("Error during disconnect cleanup: %s", e, exc_info=True)

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

    async def links_updated(self, event):
        """
        Handle links_updated message from the channel layer.
        Notify the client that page links have been updated so it can refresh the Ref sidebar.
        """
        page_id = event.get("page_id", "")
        log_debug(f"Sending links_updated to client for page {page_id}")
        await self.send(text_data=f'{{"type":"links_updated","page_id":"{page_id}"}}')
