"""Verify rewind endpoints reject PDF-type pages."""

from http import HTTPStatus

from django.test import override_settings

from core.tests.common import BaseAuthenticatedViewTestCase
from pages.tests.factories import PageFactory, ProjectFactory
from users.constants import OrgMemberRole
from users.tests.factories import OrgFactory, OrgMemberFactory


@override_settings(REWIND_ENABLED=True)
class TestRewindCheckpointBlockedOnPdf(BaseAuthenticatedViewTestCase):
    def setUp(self):
        super().setUp()
        self.org = OrgFactory()
        OrgMemberFactory(org=self.org, user=self.user, role=OrgMemberRole.MEMBER.value)
        self.project = ProjectFactory(org=self.org, creator=self.user)
        self.page = PageFactory(
            project=self.project,
            creator=self.user,
            details={
                "content": "",
                "extracted_text": "Body",
                "pdf_file_id": "f-1",
                "filetype": "pdf",
                "schema_version": 2,
            },
        )

    def test_checkpoint_returns_400_on_pdf_page(self):
        url = f"/api/pages/{self.page.external_id}/rewind/checkpoint/"
        response = self.send_api_request(url=url, method="post", data={"label": "v1"})
        self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)
        self.assertIn("PDF pages", response.json()["message"])
