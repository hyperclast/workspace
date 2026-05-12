"""
Tests for `PageYjsConsumer._seed_ydoc_from_page`.

This helper is the server-side mechanism that hydrates an empty Yjs room
from `Page.details["content"]` and persists the resulting CRDT update to
`y_updates`. It is called from `make_ydoc()` when the store has no
usable state — replacing the frontend's "seed if ytext is empty" gate
that races between concurrent loaders.

The helper acquires a Postgres advisory transaction lock keyed on the
room before writing, so two consumers racing on the same empty room
serialize: the winner inserts the seed row, the loser reads it back and
applies it to its own doc.

These tests exercise the helper directly (not over a WebSocket) so they
cover the seed contract without entangling with the consumer's full
connect/disconnect lifecycle.
"""

from unittest.mock import MagicMock, patch

from asgiref.sync import sync_to_async
from django.test import TransactionTestCase
from pycrdt import Doc, Text

from collab.consumers import PageYjsConsumer
from collab.models import YUpdate
from collab.tests import create_page_with_access, create_user_with_org_and_project
from pages.constants import FileType


def _make_consumer_for_page(page_external_id: str) -> PageYjsConsumer:
    """Build a bare consumer wired up just enough to call the seed helper.

    `PageYjsConsumer.__init__` does not require a scope / channel name,
    so we skip the websocket dance entirely. `room_name` is the only
    attribute the helper touches now that persistence goes through the
    Django ORM rather than the ystore.
    """
    consumer = PageYjsConsumer()
    consumer.room_name = f"page_{page_external_id}"
    return consumer


async def _yupdate_rows_for_room(room_id: str) -> list[bytes]:
    rows = await sync_to_async(list)(
        YUpdate.objects.filter(room_id=room_id).order_by("id").values_list("yupdate", flat=True)
    )
    return [bytes(b) for b in rows]


class TestSeedYdocFromPage(TransactionTestCase):
    SEED_CONTENT = "content1234"

    async def test_seeds_doc_and_persists_when_content_present(self):
        """Doc gets the page text; a single `y_updates` row is created."""
        user, org, project = await create_user_with_org_and_project()
        page = await create_page_with_access(user, org, project, details={"content": self.SEED_CONTENT})

        consumer = _make_consumer_for_page(page.external_id)

        doc = Doc()
        result = await consumer._seed_ydoc_from_page(doc)

        self.assertTrue(result, "seeder should report success when content is present")

        # The doc the helper returns to has the content applied.
        self.assertEqual(str(doc.get("codemirror", type=Text)), self.SEED_CONTENT)

        rows = await _yupdate_rows_for_room(f"page_{page.external_id}")
        self.assertEqual(len(rows), 1, "seeder must persist exactly one y_updates row")
        self.assertGreater(
            len(rows[0]),
            2,
            "seed update must be more than the 2-byte empty-doc marker",
        )

        # The persisted bytes round-trip back into a doc with the same content.
        replay = Doc()
        replay.apply_update(rows[0])
        self.assertEqual(str(replay.get("codemirror", type=Text)), self.SEED_CONTENT)

    async def test_returns_false_when_content_empty(self):
        """Empty `details.content` is the precondition we MUST NOT seed under."""
        user, org, project = await create_user_with_org_and_project()
        page = await create_page_with_access(user, org, project, details={"content": ""})

        consumer = _make_consumer_for_page(page.external_id)

        doc = Doc()
        result = await consumer._seed_ydoc_from_page(doc)

        self.assertFalse(result)
        rows = await _yupdate_rows_for_room(f"page_{page.external_id}")
        self.assertEqual(rows, [])
        self.assertEqual(str(doc.get("codemirror", type=Text)), "")

    async def test_returns_false_when_details_missing_content_key(self):
        """A `details` dict without a `content` key is the same as empty."""
        user, org, project = await create_user_with_org_and_project()
        page = await create_page_with_access(user, org, project, details={"filetype": "txt"})

        consumer = _make_consumer_for_page(page.external_id)

        result = await consumer._seed_ydoc_from_page(Doc())

        self.assertFalse(result)
        rows = await _yupdate_rows_for_room(f"page_{page.external_id}")
        self.assertEqual(rows, [])

    async def test_returns_false_for_pdf_page(self):
        """PDF pages keep their body in `details.extracted_text`; never seed.

        Seeding from `details.content` for a PDF page would inject the
        literal markdown wrapper (which we deliberately leave empty for
        the v2 PDF-native path) into the editor's ytext.
        """
        user, org, project = await create_user_with_org_and_project()
        page = await create_page_with_access(
            user,
            org,
            project,
            details={
                "filetype": FileType.PDF,
                "schema_version": 2,
                "content": "should-never-be-seeded",
                "extracted_text": "the real body",
            },
        )

        consumer = _make_consumer_for_page(page.external_id)

        result = await consumer._seed_ydoc_from_page(Doc())

        self.assertFalse(result)
        rows = await _yupdate_rows_for_room(f"page_{page.external_id}")
        self.assertEqual(rows, [])

    async def test_returns_false_when_page_missing(self):
        """A WS room whose Page row was deleted between connect and hydration."""
        consumer = _make_consumer_for_page("nonexistent-page-id")

        result = await consumer._seed_ydoc_from_page(Doc())

        self.assertFalse(result)
        rows = await _yupdate_rows_for_room("page_nonexistent-page-id")
        self.assertEqual(rows, [])

    async def test_returns_false_when_page_soft_deleted(self):
        """Soft-deleted pages must not contribute their stale content."""
        user, org, project = await create_user_with_org_and_project()
        page = await create_page_with_access(user, org, project, details={"content": self.SEED_CONTENT})

        await sync_to_async(type(page).objects.filter(pk=page.pk).update)(is_deleted=True)

        consumer = _make_consumer_for_page(page.external_id)

        result = await consumer._seed_ydoc_from_page(Doc())

        self.assertFalse(result)
        rows = await _yupdate_rows_for_room(f"page_{page.external_id}")
        self.assertEqual(rows, [])

    async def test_returns_false_when_yupdate_create_raises(self):
        """If persistence fails, the helper returns False instead of bubbling.

        The caller (`make_ydoc`) will continue with whatever state it has —
        we don't want a transient DB hiccup to break the WS connect.
        """
        user, org, project = await create_user_with_org_and_project()
        page = await create_page_with_access(user, org, project, details={"content": self.SEED_CONTENT})

        consumer = _make_consumer_for_page(page.external_id)

        with patch(
            "collab.consumers.YUpdate.objects.create",
            side_effect=RuntimeError("postgres down"),
        ) as mock_create:
            result = await consumer._seed_ydoc_from_page(Doc())

        self.assertFalse(result)
        mock_create.assert_called_once()
        # The transaction rolled back, so no row landed.
        rows = await _yupdate_rows_for_room(f"page_{page.external_id}")
        self.assertEqual(rows, [])

    async def test_apply_update_failure_flags_consumer_and_keeps_row(self):
        """Winner-then-apply-fails: the seed row is committed, but
        `doc.apply_update` raises (e.g. pycrdt parse error on bytes we
        just wrote). The helper must fail-open by returning False AND
        set `_seed_apply_failed` so `_reconcile_empty_page_content` does
        not erase `Page.details["content"]` based on a local doc that is
        empty only because we could not decode the row.
        """
        user, org, project = await create_user_with_org_and_project()
        page = await create_page_with_access(user, org, project, details={"content": self.SEED_CONTENT})

        consumer = _make_consumer_for_page(page.external_id)
        self.assertFalse(consumer._seed_apply_failed, "flag must start False")

        fake_doc = MagicMock()
        fake_doc.apply_update.side_effect = RuntimeError("simulated parse error")

        result = await consumer._seed_ydoc_from_page(fake_doc)

        self.assertFalse(result, "helper must return False on apply failure")
        self.assertTrue(
            consumer._seed_apply_failed,
            "consumer must flag the apply failure so reconcile skips",
        )
        fake_doc.apply_update.assert_called_once()

        # The seed row WAS persisted (the failure was on the local apply,
        # after the transaction committed) — leave it in y_updates so the
        # next opener can retry hydration from it.
        rows = await _yupdate_rows_for_room(f"page_{page.external_id}")
        self.assertEqual(len(rows), 1, "seed row must remain in y_updates after a local apply failure")

    async def test_apply_update_failure_in_loser_path_also_flags_consumer(self):
        """Loser-then-apply-fails: a previous writer's row exists, the
        helper reads it back, but applying those bytes to the caller's
        doc raises. The helper must still fail-open and flag the
        consumer; the original row stays untouched.
        """
        user, org, project = await create_user_with_org_and_project()
        page = await create_page_with_access(user, org, project, details={"content": self.SEED_CONTENT})
        room_id = f"page_{page.external_id}"

        winner_doc = Doc()
        winner_doc.get("codemirror", type=Text).insert(0, "winner-already-seeded")
        winner_bytes = bytes(winner_doc.get_update())
        await sync_to_async(YUpdate.objects.create)(room_id=room_id, yupdate=winner_bytes)

        consumer = _make_consumer_for_page(page.external_id)
        fake_doc = MagicMock()
        fake_doc.apply_update.side_effect = RuntimeError("simulated parse error")

        result = await consumer._seed_ydoc_from_page(fake_doc)

        self.assertFalse(result)
        self.assertTrue(consumer._seed_apply_failed)

        # The pre-existing row must be untouched — the helper never
        # writes in the loser path, regardless of whether apply succeeds.
        rows = await _yupdate_rows_for_room(room_id)
        self.assertEqual(rows, [winner_bytes])


class TestSeedYdocLockCoordination(TransactionTestCase):
    """Tests for the seed-once invariant under simulated lock contention.

    The advisory lock serializes seeders on the same room. The "winner"
    of the lock writes the seed; any later caller acquiring the lock
    finds the existing `y_updates` row and applies it instead of
    writing again. This covers the loser branch directly by
    pre-creating a `y_updates` row before invoking the helper — the
    helper must then behave like a lock-loser.
    """

    SEED_CONTENT = "content1234"
    PREEXISTING_CONTENT = "winner-already-seeded"

    async def test_loser_path_applies_existing_update_without_writing(self):
        """When a y_updates row already exists for the room (i.e. another
        consumer won the lock and seeded), the helper must NOT add a
        second row — it must apply the existing bytes to the caller's
        doc and return True."""
        user, org, project = await create_user_with_org_and_project()
        page = await create_page_with_access(user, org, project, details={"content": self.SEED_CONTENT})
        room_id = f"page_{page.external_id}"

        # Simulate the winner's persisted seed.
        winner_doc = Doc()
        winner_text = winner_doc.get("codemirror", type=Text)
        winner_text.insert(0, self.PREEXISTING_CONTENT)
        winner_bytes = bytes(winner_doc.get_update())

        await sync_to_async(YUpdate.objects.create)(room_id=room_id, yupdate=winner_bytes)

        consumer = _make_consumer_for_page(page.external_id)
        doc = Doc()
        result = await consumer._seed_ydoc_from_page(doc)

        self.assertTrue(result, "loser should still report success — doc is now hydrated")

        # The caller's doc was hydrated from the winner's bytes, NOT from
        # `page.details["content"]`. This is the key property: the loser
        # never independently seeds, even if `details.content` differs
        # from what the winner wrote.
        self.assertEqual(
            str(doc.get("codemirror", type=Text)),
            self.PREEXISTING_CONTENT,
        )

        # And critically, no second row was written.
        rows = await _yupdate_rows_for_room(room_id)
        self.assertEqual(len(rows), 1, "loser must not append a duplicate seed row")
        self.assertEqual(rows[0], winner_bytes)
