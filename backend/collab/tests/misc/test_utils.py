"""Tests for collab utility functions."""

from unittest.mock import MagicMock, patch

from django.test import TestCase

from collab.utils import notify_page_access_revoked, notify_write_permission_revoked


class TestNotifyPageAccessRevoked(TestCase):
    """Tests for notify_page_access_revoked function."""

    @patch("collab.utils.get_channel_layer")
    @patch("collab.utils.async_to_sync")
    def test_sends_access_revoked_message(self, mock_async_to_sync, mock_get_channel_layer):
        """Test that access_revoked message is sent to the correct group."""
        mock_channel_layer = MagicMock()
        mock_get_channel_layer.return_value = mock_channel_layer

        # Create a mock function that async_to_sync will "convert"
        mock_sync_fn = MagicMock()
        mock_async_to_sync.return_value = mock_sync_fn

        notify_page_access_revoked("abc123", 42)

        # Check that async_to_sync was called with group_send
        mock_async_to_sync.assert_called_once_with(mock_channel_layer.group_send)

        # Check that the sync function was called with correct arguments
        mock_sync_fn.assert_called_once_with(
            "page_abc123",
            {
                "type": "access_revoked",
                "user_id": 42,
            },
        )

    @patch("collab.utils.get_channel_layer")
    def test_does_nothing_without_channel_layer(self, mock_get_channel_layer):
        """Test that nothing happens when channel layer is not available."""
        mock_get_channel_layer.return_value = None

        # Should not raise any errors
        notify_page_access_revoked("abc123", 42)


class TestNotifyWritePermissionRevoked(TestCase):
    """Tests for notify_write_permission_revoked function."""

    @patch("collab.utils.get_channel_layer")
    @patch("collab.utils.async_to_sync")
    def test_sends_write_permission_revoked_message(self, mock_async_to_sync, mock_get_channel_layer):
        """Test that write_permission_revoked message is sent to the correct group."""
        mock_channel_layer = MagicMock()
        mock_get_channel_layer.return_value = mock_channel_layer

        # Create a mock function that async_to_sync will "convert"
        mock_sync_fn = MagicMock()
        mock_async_to_sync.return_value = mock_sync_fn

        notify_write_permission_revoked("page-xyz", 123)

        # Check that async_to_sync was called with group_send
        mock_async_to_sync.assert_called_once_with(mock_channel_layer.group_send)

        # Check that the sync function was called with correct arguments
        mock_sync_fn.assert_called_once_with(
            "page_page-xyz",
            {
                "type": "write_permission_revoked",
                "user_id": 123,
            },
        )

    @patch("collab.utils.get_channel_layer")
    def test_does_nothing_without_channel_layer(self, mock_get_channel_layer):
        """Test that nothing happens when channel layer is not available."""
        mock_get_channel_layer.return_value = None

        # Should not raise any errors
        notify_write_permission_revoked("page-xyz", 123)
