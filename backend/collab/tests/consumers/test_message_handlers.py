"""Tests for WebSocket consumer message handler methods.

Verifies that consumer handlers produce valid JSON output,
particularly for handlers that forward channel layer messages
to WebSocket clients.
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

from django.test import SimpleTestCase

from collab.consumers import PageYjsConsumer


class TestLinksUpdatedHandler(SimpleTestCase):
    """Test that the links_updated handler produces valid JSON."""

    def _make_consumer(self):
        consumer = PageYjsConsumer()
        consumer.send = AsyncMock()
        return consumer

    async def test_links_updated_sends_valid_json(self):
        consumer = self._make_consumer()

        await consumer.links_updated({"page_id": "abc123"})

        consumer.send.assert_called_once()
        text_data = consumer.send.call_args[1]["text_data"]
        parsed = json.loads(text_data)
        self.assertEqual(parsed["type"], "links_updated")
        self.assertEqual(parsed["page_id"], "abc123")

    async def test_links_updated_empty_page_id(self):
        consumer = self._make_consumer()

        await consumer.links_updated({})

        text_data = consumer.send.call_args[1]["text_data"]
        parsed = json.loads(text_data)
        self.assertEqual(parsed["page_id"], "")

    async def test_links_updated_page_id_with_special_chars(self):
        """Page IDs with quotes or backslashes must not break JSON output."""
        consumer = self._make_consumer()

        await consumer.links_updated({"page_id": 'has"quotes\\and\\slashes'})

        text_data = consumer.send.call_args[1]["text_data"]
        parsed = json.loads(text_data)
        self.assertEqual(parsed["type"], "links_updated")
        self.assertEqual(parsed["page_id"], 'has"quotes\\and\\slashes')
