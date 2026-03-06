"""
Shared test helpers for CRDT tests (archive, purge commands).
"""

from datetime import timedelta

from django.db import connection
from django.utils import timezone

from collab.models import CrdtArchiveBatch, YUpdate


class CrdtTestMixin:
    """Shared helpers for inserting/querying y_updates and y_snapshots rows."""

    def _insert_update(self, room_id, update_id, hours_ago=0, data=b"\x01"):
        ts = timezone.now() - timedelta(hours=hours_ago)
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO y_updates (id, room_id, yupdate, timestamp) VALUES (%s, %s, %s, %s)",
                [update_id, room_id, data, ts],
            )

    def _insert_snapshot(self, room_id, last_update_id, hours_ago=0, data=b"\x01\x00"):
        ts = timezone.now() - timedelta(hours=hours_ago)
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO y_snapshots (room_id, snapshot, last_update_id, timestamp)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (room_id) DO UPDATE
                SET snapshot = EXCLUDED.snapshot,
                    last_update_id = EXCLUDED.last_update_id,
                    timestamp = EXCLUDED.timestamp
                """,
                [room_id, data, last_update_id, ts],
            )

    def _update_count(self, room_id=None):
        qs = YUpdate.objects.all()
        if room_id:
            qs = qs.filter(room_id=room_id)
        return qs.count()

    def tearDown(self):
        with connection.cursor() as cursor:
            cursor.execute("DELETE FROM y_updates")
            cursor.execute("DELETE FROM y_snapshots")
        CrdtArchiveBatch.objects.all().delete()
