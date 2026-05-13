"""
Regression: `apply_text_to_room` and `_seed_ydoc_from_page` must serialize.

Without the per-room advisory lock both writers can independently read an
empty `y_updates`, each write a row with the same content but distinct
Yjs `clientID`s, and the CRDT preserves both inserts as doubled text
(e.g. "hellohello"). The lock — `pg_advisory_xact_lock(SEED_LOCK_NAMESPACE,
advisory_lock_key_for_room(room_id))` — held by both writers collapses
the race to a clean winner/loser ordering. Whichever writer acquires
the lock first commits its row; the other blocks until release, then
its in-lock recheck sees the existing row and either applies it (seed
loser) or returns NOOP because the requested overwrite is already in
effect (apply_text loser). Either way: exactly one row.

These tests run the two paths concurrently against a freshly-empty
room and assert the post-lock invariant. The end-to-end shape (real
DB connections in two threads, real advisory lock contention) makes
this a load-bearing regression guard against future refactors that
might rearrange the locking discipline.
"""

import asyncio
from unittest.mock import MagicMock, patch

from asgiref.sync import sync_to_async
from django.test import TransactionTestCase
from pycrdt import Doc, Text

from collab.consumers import PageYjsConsumer
from collab.models import YUpdate
from collab.services.apply_text import ApplyResult, apply_text_to_room
from collab.tests import create_page_with_access, create_user_with_org_and_project


SEED_CONTENT = "hello"


def _make_consumer_for_page(page_external_id: str) -> PageYjsConsumer:
    consumer = PageYjsConsumer()
    consumer.room_name = f"page_{page_external_id}"
    return consumer


def _replay_text(update_rows: list[bytes]) -> str:
    doc = Doc()
    for chunk in update_rows:
        doc.apply_update(chunk)
    ytext = doc.get("codemirror", type=Text)
    return str(ytext) if ytext else ""


async def _rows_for_room(room_id: str) -> list[bytes]:
    rows = await sync_to_async(list)(
        YUpdate.objects.filter(room_id=room_id).order_by("id").values_list("yupdate", flat=True)
    )
    return [bytes(r) for r in rows]


@patch("collab.services.apply_text.get_channel_layer")
class TestApplyTextSeedRace(TransactionTestCase):
    async def test_concurrent_seed_and_apply_text_overwrite_writes_exactly_one_row(self, mocked_channel_layer):
        """Both writers race; the lock guarantees a single y_updates row.

        Pre-lock: two rows can land, replay yields "hellohello".
        Post-lock: one row, replay yields "hello".
        """
        mocked_channel_layer.return_value = MagicMock()

        user, org, project = await create_user_with_org_and_project()
        page = await create_page_with_access(user, org, project, details={"content": SEED_CONTENT})
        room_id = f"page_{page.external_id}"

        consumer = _make_consumer_for_page(page.external_id)
        seed_target_doc = Doc()

        async def _run_seed():
            return await consumer._seed_ydoc_from_page(seed_target_doc)

        async def _run_apply_text():
            return await sync_to_async(apply_text_to_room)(room_id, SEED_CONTENT, user.id, "overwrite")

        seed_result, apply_text_result = await asyncio.gather(_run_seed(), _run_apply_text())

        # Whichever writer won, the seed path reports True (it either
        # wrote the row as winner, or read+applied the existing row as
        # loser). The apply_text path is either APPLIED (winner) or
        # NOOP (loser: in-lock recheck saw the seed row, current already
        # equals new_content).
        self.assertTrue(
            seed_result,
            "seed must report success: winner wrote, or loser applied existing",
        )
        self.assertIn(
            apply_text_result,
            (ApplyResult.APPLIED, ApplyResult.NOOP),
            "apply_text must be the writer (APPLIED) or the loser that saw the row (NOOP)",
        )

        rows = await _rows_for_room(room_id)
        self.assertEqual(
            len(rows),
            1,
            f"Expected exactly one y_updates row; got {len(rows)}. "
            f"More than one indicates the writers did not serialize.",
        )

        replayed = _replay_text(rows)
        self.assertEqual(
            replayed,
            SEED_CONTENT,
            f"Replay must equal input content; got {replayed!r}. "
            f"Doubled content here indicates two writers both inserted under the empty base.",
        )

    async def test_apply_text_winning_the_race_lets_seed_become_loser(self, mocked_channel_layer):
        """Pre-seed a `y_updates` row to model the apply_text-wins case.

        Even when apply_text has already persisted a row by the time the
        seed path runs, the seed must still see exactly one row and not
        write a second. This is the loser branch of `_seed_ydoc_from_page`
        — its in-lock recheck finds the pre-existing row, applies the
        bytes to its local doc, and returns True without writing.
        """
        mocked_channel_layer.return_value = MagicMock()

        user, org, project = await create_user_with_org_and_project()
        page = await create_page_with_access(user, org, project, details={"content": SEED_CONTENT})
        room_id = f"page_{page.external_id}"

        await sync_to_async(apply_text_to_room)(room_id, SEED_CONTENT, user.id, "overwrite")
        rows_before_seed = await _rows_for_room(room_id)
        self.assertEqual(len(rows_before_seed), 1, "apply_text must have written exactly one row")

        consumer = _make_consumer_for_page(page.external_id)
        seed_doc = Doc()
        result = await consumer._seed_ydoc_from_page(seed_doc)

        self.assertTrue(result, "loser seed must report success after applying existing row")

        rows = await _rows_for_room(room_id)
        self.assertEqual(len(rows), 1, "seed loser must not append a duplicate row")
        self.assertEqual(rows, rows_before_seed, "the original row must be untouched")

        self.assertEqual(
            str(seed_doc.get("codemirror", type=Text)),
            SEED_CONTENT,
            "seed's caller doc must be hydrated from the apply_text row",
        )

    async def test_seed_winning_the_race_lets_apply_text_become_noop(self, mocked_channel_layer):
        """Pre-seed a `y_updates` row to model the seed-wins case.

        With the seed row already in place, the apply_text overwrite of
        the same content must observe `current == new_content` during
        its in-lock read, return NOOP, and not write a second row.
        """
        mocked_channel_layer.return_value = MagicMock()

        user, org, project = await create_user_with_org_and_project()
        page = await create_page_with_access(user, org, project, details={"content": SEED_CONTENT})
        room_id = f"page_{page.external_id}"

        consumer = _make_consumer_for_page(page.external_id)
        seed_doc = Doc()
        seed_result = await consumer._seed_ydoc_from_page(seed_doc)
        self.assertTrue(seed_result)
        rows_before_apply = await _rows_for_room(room_id)
        self.assertEqual(len(rows_before_apply), 1)

        result = await sync_to_async(apply_text_to_room)(room_id, SEED_CONTENT, user.id, "overwrite")
        self.assertEqual(result, ApplyResult.NOOP, "apply_text loser must NOOP, not append")

        rows = await _rows_for_room(room_id)
        self.assertEqual(len(rows), 1, "apply_text loser must not append a duplicate row")
        self.assertEqual(rows, rows_before_apply, "the original row must be untouched")
        self.assertEqual(_replay_text(rows), SEED_CONTENT)
