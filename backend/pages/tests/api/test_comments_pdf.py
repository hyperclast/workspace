from http import HTTPStatus
from unittest.mock import patch

from core.tests.common import BaseAuthenticatedViewTestCase
from pages.models import Comment
from pages.tests.factories import CommentFactory, PageFactory, ProjectFactory
from users.constants import OrgMemberRole
from users.tests.factories import OrgFactory, OrgMemberFactory


PDF_DETAILS = {
    "content": "",
    "extracted_text": "Hello world",
    "pdf_file_id": "file-1",
    "filetype": "pdf",
    "schema_version": 2,
}


VALID_PDF_ANCHOR = {
    "page": 1,
    "rects": [{"x": 10.0, "y": 20.0, "w": 100.0, "h": 12.0}],
    "text": "highlighted phrase",
}


class PdfCommentsTestMixin:
    def setUp(self):
        super().setUp()
        self.org = OrgFactory()
        OrgMemberFactory(org=self.org, user=self.user, role=OrgMemberRole.MEMBER.value)
        self.project = ProjectFactory(org=self.org, creator=self.user)
        self.pdf_page = PageFactory(project=self.project, creator=self.user, details=PDF_DETAILS.copy())
        self.md_page = PageFactory(project=self.project, creator=self.user)

    def url(self, page, comment_id=None):
        base = f"/api/pages/{page.external_id}/comments/"
        if comment_id:
            return f"{base}{comment_id}/"
        return base


class TestPdfCommentCreate(PdfCommentsTestMixin, BaseAuthenticatedViewTestCase):
    def test_create_with_pdf_anchor_succeeds(self):
        response = self.send_api_request(
            url=self.url(self.pdf_page),
            method="post",
            data={"body": "What does this mean?", "pdf_anchor": VALID_PDF_ANCHOR},
        )
        self.assertEqual(response.status_code, HTTPStatus.CREATED, response.content)
        body = response.json()
        self.assertEqual(body["pdf_anchor"], VALID_PDF_ANCHOR)
        # anchor_text should be populated from pdf_anchor.text
        self.assertEqual(body["anchor_text"], "highlighted phrase")

        comment = Comment.objects.get(external_id=body["external_id"])
        self.assertEqual(comment.pdf_anchor, VALID_PDF_ANCHOR)
        self.assertEqual(comment.anchor_text, "highlighted phrase")
        self.assertIsNone(comment.anchor_from)
        self.assertIsNone(comment.anchor_to)

    def test_pdf_page_rejects_text_anchors(self):
        response = self.send_api_request(
            url=self.url(self.pdf_page),
            method="post",
            data={
                "body": "comment",
                "anchor_from_b64": "AAAA",
                "anchor_to_b64": "AAAA",
                "anchor_text": "x",
            },
        )
        self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)
        self.assertIn("PDF pages do not accept text anchors", response.json()["detail"])

    def test_markdown_page_rejects_pdf_anchor(self):
        response = self.send_api_request(
            url=self.url(self.md_page),
            method="post",
            data={"body": "comment", "pdf_anchor": VALID_PDF_ANCHOR},
        )
        self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)
        self.assertIn("Only PDF-type pages accept pdf_anchor", response.json()["detail"])

    def test_reply_rejects_pdf_anchor(self):
        root = CommentFactory(
            page=self.pdf_page,
            author=self.user,
            anchor_text="highlighted phrase",
            pdf_anchor=VALID_PDF_ANCHOR,
        )
        response = self.send_api_request(
            url=self.url(self.pdf_page),
            method="post",
            data={
                "body": "reply",
                "parent_id": root.external_id,
                "pdf_anchor": VALID_PDF_ANCHOR,
            },
        )
        self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)
        self.assertIn("Replies cannot have their own anchors", response.json()["detail"])

    def test_reply_without_anchor_succeeds(self):
        root = CommentFactory(
            page=self.pdf_page,
            author=self.user,
            anchor_text="highlighted phrase",
            pdf_anchor=VALID_PDF_ANCHOR,
        )
        response = self.send_api_request(
            url=self.url(self.pdf_page),
            method="post",
            data={"body": "reply", "parent_id": root.external_id},
        )
        self.assertEqual(response.status_code, HTTPStatus.CREATED, response.content)

    def test_pdf_anchor_validation_rejects_empty_rects(self):
        bad = {**VALID_PDF_ANCHOR, "rects": []}
        response = self.send_api_request(
            url=self.url(self.pdf_page),
            method="post",
            data={"body": "comment", "pdf_anchor": bad},
        )
        self.assertEqual(response.status_code, HTTPStatus.UNPROCESSABLE_ENTITY)

    def test_pdf_anchor_validation_rejects_negative_page(self):
        bad = {**VALID_PDF_ANCHOR, "page": 0}
        response = self.send_api_request(
            url=self.url(self.pdf_page),
            method="post",
            data={"body": "comment", "pdf_anchor": bad},
        )
        self.assertEqual(response.status_code, HTTPStatus.UNPROCESSABLE_ENTITY)


class TestPdfCommentList(PdfCommentsTestMixin, BaseAuthenticatedViewTestCase):
    def test_list_returns_pdf_anchor(self):
        CommentFactory(
            page=self.pdf_page,
            author=self.user,
            anchor_text="highlighted phrase",
            pdf_anchor=VALID_PDF_ANCHOR,
        )
        response = self.send_api_request(url=self.url(self.pdf_page))
        self.assertEqual(response.status_code, HTTPStatus.OK)
        items = response.json()["items"]
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["pdf_anchor"], VALID_PDF_ANCHOR)

    @patch("pages.api.comments.notify_comments_updated")
    def test_create_broadcasts_comments_updated(self, mock_notify):
        """PDF pages rely on this broadcast for live cross-session updates;
        without it a second browser session would never see new comments."""
        response = self.send_api_request(
            url=self.url(self.pdf_page),
            method="post",
            data={"body": "Comment for broadcast", "pdf_anchor": VALID_PDF_ANCHOR},
        )
        self.assertEqual(response.status_code, HTTPStatus.CREATED, response.content)
        mock_notify.assert_called_once_with(str(self.pdf_page.external_id))

    def test_list_returns_page_only_anchor_with_empty_rects(self):
        """AI-resolved PDF anchors carry only page+text (rects=[]); the
        output schema must round-trip them so the sidebar can navigate."""
        page_only_anchor = {"page": 2, "rects": [], "text": "highlighted phrase"}
        CommentFactory(
            page=self.pdf_page,
            author=None,
            ai_persona="socrates",
            anchor_text="highlighted phrase",
            pdf_anchor=page_only_anchor,
        )
        response = self.send_api_request(url=self.url(self.pdf_page))
        self.assertEqual(response.status_code, HTTPStatus.OK)
        items = response.json()["items"]
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["pdf_anchor"], page_only_anchor)
