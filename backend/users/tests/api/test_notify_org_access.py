"""Tests for notify_org_access_revoked function."""

from unittest.mock import MagicMock, patch

from django.test import TestCase

from pages.tests.factories import PageFactory, ProjectFactory
from users.api.orgs import notify_org_access_revoked
from users.tests.factories import OrgFactory, UserFactory


class TestNotifyOrgAccessRevoked(TestCase):
    """Test the notify_org_access_revoked helper function."""

    def setUp(self):
        self.org = OrgFactory()
        self.user = UserFactory()
        self.project = ProjectFactory(org=self.org)

    def test_sends_message_for_each_page_in_org(self):
        """Should send access_revoked message for each page in org's projects."""
        # Create multiple pages in the org's project
        page1 = PageFactory(project=self.project)
        page2 = PageFactory(project=self.project)
        page3 = PageFactory(project=self.project)

        mock_channel_layer = MagicMock()

        with patch("users.api.orgs.get_channel_layer", return_value=mock_channel_layer):
            with patch("users.api.orgs.async_to_sync") as mock_async_to_sync:
                # Make async_to_sync return a callable that we can track
                mock_group_send = MagicMock()
                mock_async_to_sync.return_value = mock_group_send

                notify_org_access_revoked(self.org, self.user.id)

                # Should have called group_send for each page
                self.assertEqual(mock_group_send.call_count, 3)

                # Verify the room names and message format
                call_args_list = mock_group_send.call_args_list
                room_names = {call[0][0] for call in call_args_list}
                expected_rooms = {
                    f"page_{page1.external_id}",
                    f"page_{page2.external_id}",
                    f"page_{page3.external_id}",
                }
                self.assertEqual(room_names, expected_rooms)

                # Verify message format
                for call in call_args_list:
                    message = call[0][1]
                    self.assertEqual(message["type"], "access_revoked")
                    self.assertEqual(message["user_id"], self.user.id)

    def test_excludes_deleted_pages(self):
        """Should not send messages for soft-deleted pages."""
        active_page = PageFactory(project=self.project)
        deleted_page = PageFactory(project=self.project, is_deleted=True)

        mock_channel_layer = MagicMock()

        with patch("users.api.orgs.get_channel_layer", return_value=mock_channel_layer):
            with patch("users.api.orgs.async_to_sync") as mock_async_to_sync:
                mock_group_send = MagicMock()
                mock_async_to_sync.return_value = mock_group_send

                notify_org_access_revoked(self.org, self.user.id)

                # Should only call for the active page
                self.assertEqual(mock_group_send.call_count, 1)
                room_name = mock_group_send.call_args[0][0]
                self.assertEqual(room_name, f"page_{active_page.external_id}")

    def test_excludes_pages_from_deleted_projects(self):
        """Should not send messages for pages in soft-deleted projects."""
        active_project = ProjectFactory(org=self.org)
        deleted_project = ProjectFactory(org=self.org, is_deleted=True)

        active_page = PageFactory(project=active_project)
        page_in_deleted_project = PageFactory(project=deleted_project)

        mock_channel_layer = MagicMock()

        with patch("users.api.orgs.get_channel_layer", return_value=mock_channel_layer):
            with patch("users.api.orgs.async_to_sync") as mock_async_to_sync:
                mock_group_send = MagicMock()
                mock_async_to_sync.return_value = mock_group_send

                notify_org_access_revoked(self.org, self.user.id)

                # Should only call for page in active project
                self.assertEqual(mock_group_send.call_count, 1)
                room_name = mock_group_send.call_args[0][0]
                self.assertEqual(room_name, f"page_{active_page.external_id}")

    def test_handles_no_channel_layer_gracefully(self):
        """Should not raise when channel layer is not available."""
        PageFactory(project=self.project)

        with patch("users.api.orgs.get_channel_layer", return_value=None):
            # Should not raise
            notify_org_access_revoked(self.org, self.user.id)

    def test_handles_channel_layer_exception_gracefully(self):
        """Should catch exceptions from channel layer operations."""
        PageFactory(project=self.project)

        mock_channel_layer = MagicMock()

        with patch("users.api.orgs.get_channel_layer", return_value=mock_channel_layer):
            with patch("users.api.orgs.async_to_sync", side_effect=Exception("Channel error")):
                # Should not raise
                notify_org_access_revoked(self.org, self.user.id)

    def test_no_messages_when_org_has_no_pages(self):
        """Should not send any messages when org has no pages."""
        empty_org = OrgFactory()
        ProjectFactory(org=empty_org)  # Project with no pages

        mock_channel_layer = MagicMock()

        with patch("users.api.orgs.get_channel_layer", return_value=mock_channel_layer):
            with patch("users.api.orgs.async_to_sync") as mock_async_to_sync:
                mock_group_send = MagicMock()
                mock_async_to_sync.return_value = mock_group_send

                notify_org_access_revoked(empty_org, self.user.id)

                # Should not call group_send
                mock_group_send.assert_not_called()

    def test_handles_pages_across_multiple_projects(self):
        """Should send messages for pages across all projects in the org."""
        # Create a fresh org for this test to avoid interference from setUp's project
        test_org = OrgFactory()
        project1 = ProjectFactory(org=test_org)
        project2 = ProjectFactory(org=test_org)

        page1 = PageFactory(project=project1)
        page2 = PageFactory(project=project2)

        mock_channel_layer = MagicMock()
        sent_messages = []

        def capture_group_send(room_name, message):
            sent_messages.append((room_name, message))

        with patch("users.api.orgs.get_channel_layer", return_value=mock_channel_layer):
            with patch("users.api.orgs.async_to_sync") as mock_async_to_sync:
                mock_async_to_sync.return_value = capture_group_send

                notify_org_access_revoked(test_org, self.user.id)

                # Should call for both pages
                self.assertEqual(len(sent_messages), 2)
                room_names = {msg[0] for msg in sent_messages}
                expected_rooms = {f"page_{page1.external_id}", f"page_{page2.external_id}"}
                self.assertEqual(room_names, expected_rooms)
