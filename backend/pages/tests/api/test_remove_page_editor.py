from http import HTTPStatus
from datetime import timedelta
from django.utils import timezone
import uuid

from core.tests.common import BaseAuthenticatedViewTestCase
from pages.models import PageInvitation, PageEditorRemoveEvent
from pages.tests.factories import PageFactory, PageInvitationFactory
from users.tests.factories import UserFactory


class TestRemovePageEditorAPI(BaseAuthenticatedViewTestCase):
    """Test DELETE /api/pages/{external_id}/editors/{user_external_id}/ endpoint."""

    def send_remove_editor_request(self, page_external_id, user_external_id):
        url = f"/api/pages/{page_external_id}/editors/{user_external_id}/"
        return self.send_api_request(url=url, method="delete")

    def test_remove_confirmed_editor(self):
        """Test removing a confirmed editor."""
        page = PageFactory(creator=self.user)
        editor = UserFactory(email="editor@example.com")
        page.editors.add(editor)

        response = self.send_remove_editor_request(page.external_id, editor.external_id)

        self.assertEqual(response.status_code, HTTPStatus.NO_CONTENT)

        # Verify editor was removed
        self.assertFalse(page.editors.filter(id=editor.id).exists())

        # Verify event was logged
        self.assertTrue(
            PageEditorRemoveEvent.objects.filter(
                page=page, removed_by=self.user, editor=editor, editor_email=editor.email
            ).exists()
        )

    def test_remove_pending_invitation(self):
        """Test removing a pending invitation."""
        page = PageFactory(creator=self.user)
        invitation = PageInvitationFactory(page=page, email="pending@example.com", invited_by=self.user, accepted=False)

        response = self.send_remove_editor_request(page.external_id, str(invitation.external_id))

        self.assertEqual(response.status_code, HTTPStatus.NO_CONTENT)

        # Verify invitation was deleted
        self.assertFalse(PageInvitation.objects.filter(id=invitation.id).exists())

        # Verify event was logged
        self.assertTrue(
            PageEditorRemoveEvent.objects.filter(
                page=page, removed_by=self.user, editor=None, editor_email="pending@example.com"
            ).exists()
        )

    def test_cannot_remove_owner(self):
        """Test that owner cannot be removed."""
        page = PageFactory(creator=self.user)
        editor = UserFactory()
        page.editors.add(editor)
        self.login(editor)  # Login as editor

        response = self.send_remove_editor_request(page.external_id, page.creator.external_id)
        payload = response.json()

        self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)
        self.assertIn("Cannot remove the page owner", payload["message"])

        # Verify owner is still an editor
        self.assertTrue(page.editors.filter(id=page.creator_id).exists())

    def test_editor_can_remove_themselves(self):
        """Test that an editor can remove themselves."""
        page = PageFactory()  # Owned by different user
        page.editors.add(self.user)

        response = self.send_remove_editor_request(page.external_id, self.user.external_id)

        self.assertEqual(response.status_code, HTTPStatus.NO_CONTENT)

        # Verify user was removed
        self.assertFalse(page.editors.filter(id=self.user.id).exists())

    def test_editor_can_remove_other_editors(self):
        """Test that any editor can remove other editors."""
        page = PageFactory()  # Owned by different user
        page.editors.add(self.user)  # Current user is an editor
        other_editor = UserFactory()
        page.editors.add(other_editor)

        response = self.send_remove_editor_request(page.external_id, other_editor.external_id)

        self.assertEqual(response.status_code, HTTPStatus.NO_CONTENT)

        # Verify other editor was removed
        self.assertFalse(page.editors.filter(id=other_editor.id).exists())

    def test_remove_non_existent_user_returns_400(self):
        """Test removing user who is not an editor returns 400."""
        page = PageFactory(creator=self.user)
        non_editor = UserFactory()

        response = self.send_remove_editor_request(page.external_id, non_editor.external_id)
        payload = response.json()

        self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)
        self.assertIn("not an editor", payload["message"])

    def test_remove_with_non_existent_uuid_returns_404(self):
        """Test removing with non-existent UUID returns 404."""
        page = PageFactory(creator=self.user)
        fake_uuid = str(uuid.uuid4())

        response = self.send_remove_editor_request(page.external_id, fake_uuid)
        payload = response.json()

        self.assertEqual(response.status_code, HTTPStatus.NOT_FOUND)
        self.assertIn("not found", payload["message"].lower())

    def test_non_editor_cannot_remove_editors(self):
        """Test that non-editors cannot remove editors."""
        page = PageFactory()  # Owned by different user
        editor = UserFactory()
        page.editors.add(editor)

        response = self.send_remove_editor_request(page.external_id, editor.external_id)

        self.assertEqual(response.status_code, HTTPStatus.NOT_FOUND)

        # Verify editor was NOT removed
        self.assertTrue(page.editors.filter(id=editor.id).exists())

    def test_remove_expired_invitation_succeeds(self):
        """Test removing expired invitation succeeds (cleanup)."""
        page = PageFactory(creator=self.user)
        invitation = PageInvitationFactory(
            page=page,
            email="expired@example.com",
            invited_by=self.user,
            accepted=False,
            expires_at=timezone.now() - timedelta(days=1),
        )

        # The endpoint doesn't check expiration when deleting, so this should succeed
        response = self.send_remove_editor_request(page.external_id, str(invitation.external_id))

        self.assertEqual(response.status_code, HTTPStatus.NO_CONTENT)

        # Verify invitation was deleted
        self.assertFalse(PageInvitation.objects.filter(id=invitation.id).exists())

    def test_remove_accepted_invitation_returns_404(self):
        """Test removing accepted invitation returns 404."""
        page = PageFactory(creator=self.user)
        user = UserFactory(email="accepted@example.com")
        page.editors.add(user)

        invitation = PageInvitationFactory(
            page=page, email="accepted@example.com", invited_by=self.user, accepted=True, accepted_by=user
        )

        # Should not find the invitation since accepted=True
        response = self.send_remove_editor_request(page.external_id, str(invitation.external_id))
        payload = response.json()

        self.assertEqual(response.status_code, HTTPStatus.NOT_FOUND)
        self.assertIn("not found", payload["message"].lower())

    def test_invalid_page_returns_404(self):
        """Test removing editor from non-existent page returns 404."""
        user = UserFactory()

        response = self.send_remove_editor_request("invalid-page-id", user.external_id)

        self.assertEqual(response.status_code, HTTPStatus.NOT_FOUND)

    def test_unauthenticated_request_returns_401(self):
        """Test that unauthenticated requests are rejected."""
        page = PageFactory(creator=self.user)
        editor = UserFactory()
        page.editors.add(editor)
        self.client.logout()

        response = self.send_remove_editor_request(page.external_id, editor.external_id)

        self.assertEqual(response.status_code, HTTPStatus.UNAUTHORIZED)
