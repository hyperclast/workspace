"""
Archive-then-purge pipeline for CRDT updates.

Archives old y_updates rows to object storage (R2/local) before deleting them
from the OLTP database. Uses a ledger (CrdtArchiveBatch) for idempotency and
auditability.

State machine per batch: created → uploaded → verified → deleted
                                                          ↘ failed
"""

import base64
import gzip
import hashlib
import json
import logging

from django.conf import settings
from django.db import IntegrityError, connection

from collab.models import ArchiveBatchStatus, CrdtArchiveBatch
from filehub.storage import get_storage_backend

logger = logging.getLogger(__name__)


def get_archive_bucket():
    """Return the bucket to use for CRDT archives."""
    return settings.CRDT_ARCHIVE_BUCKET or settings.WS_FILEHUB_R2_BUCKET


def build_object_key(room_id, from_id, to_id):
    """Build the object storage key for an archive batch."""
    return f"crdt-archives/{room_id}/{from_id}-{to_id}.jsonl.gz"


def serialize_updates(rows):
    """
    Serialize y_updates rows to gzip-compressed JSONL.

    Args:
        rows: List of tuples (id, room_id, yupdate, timestamp)

    Returns:
        (compressed_bytes, sha256_hex, row_count)
    """
    lines = []
    for update_id, room_id, yupdate, timestamp in rows:
        line = json.dumps(
            {
                "id": update_id,
                "room_id": room_id,
                "yupdate": base64.b64encode(bytes(yupdate)).decode("ascii"),
                "timestamp": timestamp.isoformat(),
            },
            separators=(",", ":"),
        )
        lines.append(line)

    raw = "\n".join(lines).encode("utf-8")
    compressed = gzip.compress(raw)
    sha256_hex = hashlib.sha256(compressed).hexdigest()
    return compressed, sha256_hex, len(lines)


def find_eligible_rooms(cutoff, batch_size):
    """
    Find rooms with old updates that are safe to archive.

    Returns list of dicts:
        [{room_id, last_update_id, old_count, min_id, max_eligible_id}]

    A room is eligible when:
    - It has a snapshot (so we know which updates are subsumed)
    - It has updates with id <= snapshot.last_update_id AND timestamp < cutoff
    - It has no in-progress archive batches (status not in created/uploaded/verified)
    """
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT s.room_id,
                   s.last_update_id,
                   COUNT(u.id) AS old_count,
                   MIN(u.id) AS min_id,
                   MAX(u.id) AS max_eligible_id
            FROM y_snapshots s
            JOIN y_updates u
              ON u.room_id = s.room_id
             AND u.id <= s.last_update_id
             AND u.timestamp < %s
            WHERE NOT EXISTS (
                SELECT 1 FROM collab_crdtarchivebatch b
                WHERE b.room_id = s.room_id
                  AND b.status IN ('created', 'uploaded', 'verified')
            )
            GROUP BY s.room_id, s.last_update_id
            HAVING COUNT(u.id) > 0
            ORDER BY s.room_id
            LIMIT %s
            """,
            [cutoff, batch_size],
        )
        columns = ["room_id", "last_update_id", "old_count", "min_id", "max_eligible_id"]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]


def fetch_updates_for_room(room_id, min_id, max_id, cutoff):
    """
    Fetch y_updates rows for archival, with double-check on snapshot coverage.

    Returns list of tuples (id, room_id, yupdate, timestamp).
    """
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT u.id, u.room_id, u.yupdate, u.timestamp
            FROM y_updates u
            JOIN y_snapshots s ON s.room_id = u.room_id
            WHERE u.room_id = %s
              AND u.id >= %s
              AND u.id <= %s
              AND u.id <= s.last_update_id
              AND u.timestamp < %s
            ORDER BY u.id
            """,
            [room_id, min_id, max_id, cutoff],
        )
        return cursor.fetchall()


def _resume_batch(batch, cutoff, dry_run):
    """
    Resume an existing batch from its current status.

    Returns the batch (possibly updated) or None if skipped.
    """
    if batch.status == ArchiveBatchStatus.DELETED:
        logger.info("Batch %s already deleted, skipping", batch.external_id)
        return batch

    if batch.status == ArchiveBatchStatus.FAILED:
        max_retries = settings.CRDT_ARCHIVE_MAX_RETRIES
        if batch.retry_count >= max_retries:
            logger.warning(
                "Batch %s has reached max retries (%d), leaving as failed",
                batch.external_id,
                max_retries,
            )
            return None
        batch.status = ArchiveBatchStatus.CREATED
        batch.error_message = ""
        batch.retry_count += 1
        batch.save(update_fields=["status", "error_message", "retry_count", "modified"])
        logger.info(
            "Batch %s previously failed, resetting for retry (attempt %d/%d)",
            batch.external_id,
            batch.retry_count,
            max_retries,
        )
        # Fall through to the CREATED handler below

    if dry_run:
        logger.info("Dry run: would resume batch %s from status=%s", batch.external_id, batch.status)
        return batch

    # Use the batch's original cutoff for data operations, not the current
    # command invocation's cutoff. The batch was created with a specific cutoff
    # and must be processed consistently with that same cutoff.
    batch_cutoff = batch.cutoff_timestamp

    storage = get_storage_backend(batch.provider)
    bucket = batch.bucket

    if batch.status == ArchiveBatchStatus.CREATED:
        # Re-fetch, re-serialize, re-upload
        rows = fetch_updates_for_room(batch.room_id, batch.from_update_id, batch.to_update_id, batch_cutoff)
        if not rows:
            batch.status = ArchiveBatchStatus.FAILED
            batch.error_message = "No rows found on resume"
            batch.save(update_fields=["status", "error_message", "modified"])
            return None

        compressed, sha256_hex, row_count = serialize_updates(rows)
        batch.checksum_sha256 = sha256_hex
        batch.row_count = row_count
        batch.archive_size_bytes = len(compressed)

        try:
            storage.put_object(bucket, batch.object_key, compressed, content_type="application/gzip")
        except Exception as exc:
            batch.status = ArchiveBatchStatus.FAILED
            batch.error_message = str(exc)[:1000]
            batch.save(
                update_fields=[
                    "status",
                    "error_message",
                    "checksum_sha256",
                    "row_count",
                    "archive_size_bytes",
                    "modified",
                ]
            )
            logger.error("Upload failed for batch %s: %s", batch.external_id, exc)
            return None

        batch.status = ArchiveBatchStatus.UPLOADED
        batch.save(update_fields=["status", "checksum_sha256", "row_count", "archive_size_bytes", "modified"])

    if batch.status == ArchiveBatchStatus.UPLOADED:
        # Verify
        try:
            meta = storage.head_object(bucket, batch.object_key)
        except Exception as exc:
            batch.status = ArchiveBatchStatus.FAILED
            batch.error_message = f"Verification failed: {exc}"[:1000]
            batch.save(update_fields=["status", "error_message", "modified"])
            logger.error("Verify failed for batch %s: %s", batch.external_id, exc)
            return None

        if meta["size_bytes"] != batch.archive_size_bytes:
            batch.status = ArchiveBatchStatus.FAILED
            batch.error_message = f"Size mismatch: expected {batch.archive_size_bytes}, got {meta['size_bytes']}"
            batch.save(update_fields=["status", "error_message", "modified"])
            logger.error("Size mismatch for batch %s", batch.external_id)
            return None

        batch.status = ArchiveBatchStatus.VERIFIED
        batch.save(update_fields=["status", "modified"])

    if batch.status == ArchiveBatchStatus.VERIFIED:
        # Delete OLTP rows
        deleted = _delete_oltp_rows(batch.room_id, batch.from_update_id, batch.to_update_id, batch_cutoff)
        batch.status = ArchiveBatchStatus.DELETED
        batch.save(update_fields=["status", "modified"])
        logger.info(
            "Deleted %d OLTP rows for batch %s (%s)",
            deleted,
            batch.external_id,
            batch.room_id,
        )

    return batch


def _delete_oltp_rows(room_id, from_id, to_id, cutoff):
    """
    Delete y_updates rows for the archived range, with safety re-checks.

    Re-applies snapshot join + cutoff check at delete time so we never
    delete rows that aren't fully covered.
    """
    with connection.cursor() as cursor:
        cursor.execute(
            """
            DELETE FROM y_updates u
            USING y_snapshots s
            WHERE u.room_id = %s
              AND u.room_id = s.room_id
              AND u.id >= %s
              AND u.id <= %s
              AND u.id <= s.last_update_id
              AND u.timestamp < %s
            """,
            [room_id, from_id, to_id, cutoff],
        )
        return cursor.rowcount


def archive_room(room_info, cutoff, dry_run=False):
    """
    Full archive pipeline for a single room.

    Args:
        room_info: dict from find_eligible_rooms()
        cutoff: datetime cutoff
        dry_run: if True, no writes

    Returns:
        CrdtArchiveBatch or None
    """
    room_id = room_info["room_id"]
    min_id = room_info["min_id"]
    max_eligible_id = room_info["max_eligible_id"]

    provider = settings.CRDT_ARCHIVE_STORAGE_PROVIDER
    bucket = get_archive_bucket()
    object_key = build_object_key(room_id, min_id, max_eligible_id)

    # Check for existing batch (idempotency)
    existing = CrdtArchiveBatch.objects.filter(
        room_id=room_id,
        from_update_id=min_id,
        to_update_id=max_eligible_id,
    ).first()

    if existing:
        return _resume_batch(existing, cutoff, dry_run)

    if dry_run:
        logger.info(
            "Dry run: would archive %d updates for %s (ids %d-%d)",
            room_info["old_count"],
            room_id,
            min_id,
            max_eligible_id,
        )
        return None

    # Fetch actual rows
    rows = fetch_updates_for_room(room_id, min_id, max_eligible_id, cutoff)
    if not rows:
        logger.warning("No eligible rows found for %s (race condition?)", room_id)
        return None

    # Serialize
    compressed, sha256_hex, row_count = serialize_updates(rows)

    # Create ledger row (status=created)
    try:
        batch = CrdtArchiveBatch.objects.create(
            room_id=room_id,
            from_update_id=min_id,
            to_update_id=max_eligible_id,
            row_count=row_count,
            status=ArchiveBatchStatus.CREATED,
            provider=provider,
            bucket=bucket,
            object_key=object_key,
            checksum_sha256=sha256_hex,
            archive_size_bytes=len(compressed),
            cutoff_timestamp=cutoff,
        )
    except IntegrityError:
        # Concurrent creation — fetch and resume
        existing = CrdtArchiveBatch.objects.filter(
            room_id=room_id,
            from_update_id=min_id,
            to_update_id=max_eligible_id,
        ).first()
        if existing:
            return _resume_batch(existing, cutoff, dry_run)
        return None

    # Delegate upload → verify → delete to _resume_batch
    return _resume_batch(batch, cutoff, dry_run=False)
