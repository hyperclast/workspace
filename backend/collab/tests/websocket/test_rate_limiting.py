"""
Tests for WebSocket connection rate limiting.

Rate limiting prevents DoS attacks from rapid reconnection loops,
whether caused by bugs (corrupted snapshots) or malicious actors.
"""

import asyncio

from asgiref.sync import sync_to_async
from channels.testing import WebsocketCommunicator
from django.core.cache import cache
from django.test import TransactionTestCase, override_settings

from backend.asgi import application
from collab.consumers import WS_CLOSE_RATE_LIMITED
from collab.tests import (
    add_project_editor,
    assert_ws_rejected,
    create_page_with_access,
    create_user_with_org_and_project,
)
from users.tests.factories import UserFactory


class TestWebSocketRateLimiting(TransactionTestCase):
    """Test rate limiting for WebSocket connections."""

    def setUp(self):
        cache.clear()

    def tearDown(self):
        cache.clear()

    async def _create_test_fixtures(self):
        """Create a user and page for testing."""
        user, org, project = await create_user_with_org_and_project()
        page = await create_page_with_access(user, org, project)
        return user, org, project, page

    async def _connect_websocket(self, user, page, check_rejection=False):
        """
        Attempt a WebSocket connection.
        Returns (connected, close_code, communicator).

        If check_rejection=True and the connection is initially accepted,
        will check for subsequent rejection (error message + close).
        """
        comm = WebsocketCommunicator(application, f"/ws/pages/{page.external_id}/")
        comm.scope["user"] = user
        comm.scope["client"] = ("127.0.0.1", 12345)

        connected, close_code = await comm.connect()

        if check_rejection and connected:
            # Check if connection was rejected after initial accept
            try:
                _, actual_close_code = await assert_ws_rejected(
                    comm, expected_close_code=WS_CLOSE_RATE_LIMITED, expected_error_code="rate_limited"
                )
                return False, actual_close_code, comm
            except Exception:
                # Connection was actually accepted (not rejected)
                return connected, close_code, comm

        return connected, close_code, comm

    @override_settings(WS_RATE_LIMIT_CONNECTIONS=5, WS_RATE_LIMIT_WINDOW_SECONDS=60)
    async def test_connections_within_limit_are_accepted(self):
        """Connections within the rate limit should be accepted."""
        user, org, project, page = await self._create_test_fixtures()

        connections = []
        try:
            # Make 5 connections (at the limit)
            for i in range(5):
                connected, close_code, comm = await self._connect_websocket(user, page)
                connections.append(comm)

                self.assertTrue(
                    connected,
                    f"Connection {i + 1} should be accepted (within limit)",
                )
        finally:
            # Clean up
            for comm in connections:
                try:
                    await comm.disconnect()
                except Exception:
                    pass

    @override_settings(WS_RATE_LIMIT_CONNECTIONS=3, WS_RATE_LIMIT_WINDOW_SECONDS=60)
    async def test_connections_exceeding_limit_are_rejected(self):
        """Connections exceeding the rate limit should be rejected with 4029."""
        user, org, project, page = await self._create_test_fixtures()

        connections = []
        try:
            # Make 3 connections (at the limit)
            for i in range(3):
                connected, close_code, comm = await self._connect_websocket(user, page)
                connections.append(comm)
                self.assertTrue(connected, f"Connection {i + 1} should be accepted")

            # 4th connection should be rejected (use check_rejection=True)
            connected, close_code, comm = await self._connect_websocket(user, page, check_rejection=True)
            connections.append(comm)

            self.assertFalse(connected, "Connection 4 should be rejected (over limit)")
            self.assertEqual(
                close_code,
                WS_CLOSE_RATE_LIMITED,
                f"Expected close code {WS_CLOSE_RATE_LIMITED}, got {close_code}",
            )
        finally:
            for comm in connections:
                try:
                    await comm.disconnect()
                except Exception:
                    pass

    @override_settings(WS_RATE_LIMIT_CONNECTIONS=2, WS_RATE_LIMIT_WINDOW_SECONDS=1)
    async def test_rate_limit_resets_after_window(self):
        """Rate limit should reset after the time window expires."""
        user, org, project, page = await self._create_test_fixtures()

        connections = []
        try:
            # Use up the limit (2 connections)
            for i in range(2):
                connected, _, comm = await self._connect_websocket(user, page)
                connections.append(comm)
                self.assertTrue(connected)

            # 3rd connection should be rejected (use check_rejection=True)
            connected, close_code, comm = await self._connect_websocket(user, page, check_rejection=True)
            connections.append(comm)
            self.assertFalse(connected, "Should be rate limited")
            self.assertEqual(close_code, WS_CLOSE_RATE_LIMITED)

            # Wait for window to expire (1 second + buffer)
            await asyncio.sleep(1.5)

            # Now connection should be accepted again
            connected, _, comm = await self._connect_websocket(user, page)
            connections.append(comm)
            self.assertTrue(connected, "Connection should be accepted after window reset")
        finally:
            for comm in connections:
                try:
                    await comm.disconnect()
                except Exception:
                    pass

    @override_settings(WS_RATE_LIMIT_CONNECTIONS=2, WS_RATE_LIMIT_WINDOW_SECONDS=60)
    async def test_rate_limit_is_per_user(self):
        """Each user should have their own rate limit."""
        user1, org, project, page1 = await self._create_test_fixtures()
        user2 = await sync_to_async(UserFactory.create)()
        # Give user2 access to page1
        await add_project_editor(project, user2)

        connections = []
        try:
            # User1 uses up their limit
            for i in range(2):
                connected, _, comm = await self._connect_websocket(user1, page1)
                connections.append(comm)
                self.assertTrue(connected, f"User1 connection {i + 1} should work")

            # User1's 3rd connection should be rejected (use check_rejection=True)
            connected, close_code, comm = await self._connect_websocket(user1, page1, check_rejection=True)
            connections.append(comm)
            self.assertFalse(connected, "User1 should be rate limited")

            # User2 should still be able to connect (different user, different limit)
            connected, _, comm = await self._connect_websocket(user2, page1)
            connections.append(comm)
            self.assertTrue(connected, "User2 should not be affected by User1's limit")
        finally:
            for comm in connections:
                try:
                    await comm.disconnect()
                except Exception:
                    pass

    @override_settings(WS_RATE_LIMIT_CONNECTIONS=10, WS_RATE_LIMIT_WINDOW_SECONDS=60)
    async def test_rapid_reconnection_is_limited(self):
        """
        Simulate the bug scenario: rapid connect/disconnect cycles.
        After hitting the limit, further connections should be rejected.
        """
        import json

        user, org, project, page = await self._create_test_fixtures()

        accepted_count = 0
        rejected_count = 0

        # Simulate 15 rapid connections (like a reconnection loop)
        for i in range(15):
            comm = WebsocketCommunicator(application, f"/ws/pages/{page.external_id}/")
            comm.scope["user"] = user
            comm.scope["client"] = ("127.0.0.1", 12345)

            connected, _ = await comm.connect()

            if connected:
                # Check if this was actually accepted or immediately rejected
                # The consumer accepts first, then closes for rate limiting
                try:
                    # Try to receive potential error/close message (short timeout)
                    output = await comm.receive_output(timeout=0.5)

                    if output["type"] == "websocket.send":
                        # Got a message - check if it's an error
                        text_data = output.get("text", "")
                        if text_data:
                            error_data = json.loads(text_data)
                            if error_data.get("code") == "rate_limited":
                                # This was rejected after initial accept
                                rejected_count += 1
                                # Receive the close message
                                close_msg = await comm.receive_output(timeout=1)
                                self.assertEqual(close_msg.get("code"), WS_CLOSE_RATE_LIMITED)
                            else:
                                # Unexpected message, count as accepted
                                accepted_count += 1
                                try:
                                    await comm.disconnect()
                                except Exception:
                                    pass
                        else:
                            # Binary data (Yjs sync message), connection was accepted
                            accepted_count += 1
                            try:
                                await comm.disconnect()
                            except Exception:
                                pass
                    elif output["type"] == "websocket.close":
                        # Closed immediately (rate limited)
                        rejected_count += 1
                        self.assertEqual(output.get("code"), WS_CLOSE_RATE_LIMITED)
                    else:
                        # Unknown message type, count as accepted
                        accepted_count += 1
                        try:
                            await comm.disconnect()
                        except Exception:
                            pass
                except asyncio.TimeoutError:
                    # No error message, connection was truly accepted
                    accepted_count += 1
                    try:
                        await comm.disconnect()
                    except Exception:
                        pass
            else:
                # Connection was rejected before accept (shouldn't happen with current impl)
                rejected_count += 1

        # Should have accepted 10 and rejected 5
        self.assertEqual(accepted_count, 10, f"Expected 10 accepted, got {accepted_count}")
        self.assertEqual(rejected_count, 5, f"Expected 5 rejected, got {rejected_count}")

        print(f"\n=== Rapid Reconnection Test ===")
        print(f"Total attempts: 15")
        print(f"Accepted: {accepted_count}")
        print(f"Rejected (rate limited): {rejected_count}")


class TestRateLimitCacheKey(TransactionTestCase):
    """Test the rate limit cache key generation."""

    async def test_authenticated_user_uses_user_id_key(self):
        """Authenticated users should be rate limited by user ID."""
        from collab.consumers import PageYjsConsumer

        user, org, project = await create_user_with_org_and_project()

        consumer = PageYjsConsumer()
        consumer.scope = {"user": user, "client": ("192.168.1.1", 12345)}

        key = consumer._get_rate_limit_key()

        self.assertTrue(key.startswith("ws_rate_user_"))
        self.assertIn(str(user.id), key)

    async def test_anonymous_user_uses_ip_key(self):
        """Anonymous users should be rate limited by IP address."""
        from django.contrib.auth.models import AnonymousUser

        from collab.consumers import PageYjsConsumer

        consumer = PageYjsConsumer()
        consumer.scope = {"user": AnonymousUser(), "client": ("192.168.1.100", 54321)}

        key = consumer._get_rate_limit_key()

        self.assertTrue(key.startswith("ws_rate_ip_"))
        self.assertIn("192.168.1.100", key)
