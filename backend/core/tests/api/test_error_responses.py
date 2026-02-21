"""
Tests verifying that all API error responses are normalized by
APIErrorNormalizerMiddleware into a consistent shape:

    {"error": "<code>", "message": "<human-readable>", "detail": <obj|array|null>}

The 5 endpoint error patterns covered:

    Pattern A: return STATUS, {"message": "..."}
    Pattern B: return STATUS, {"error": "...", "message": "..."}
    Pattern C: return Response({"message": "..."}, status=...)
    Pattern D: raise HttpError(STATUS, "...")  →  {"detail": "..."}
    Ninja:     Built-in validation/auth/404  →  {"detail": "..."} or {"detail": [...]}
"""

from http import HTTPStatus

from core.tests.common import BaseAuthenticatedViewTestCase
from imports.tests.factories import ImportJobFactory
from pages.constants import ProjectEditorRole
from pages.tests.factories import ProjectEditorFactory, ProjectFactory
from users.constants import OrgMemberRole
from users.tests.factories import OrgFactory, OrgMemberFactory, UserFactory


class NormalizedErrorAssertionsMixin:
    """Shared assertions for the normalized error shape."""

    def assert_normalized_error(self, response, expected_error="error", expected_message=None):
        """Assert response has the standard normalized error shape."""
        data = response.json()
        self.assertIn("error", data)
        self.assertIn("message", data)
        self.assertIn("detail", data)
        self.assertIsInstance(data["error"], str)
        self.assertIsInstance(data["message"], str)
        if expected_error:
            self.assertEqual(data["error"], expected_error)
        if expected_message:
            self.assertEqual(data["message"], expected_message)
        return data


class TestPatternAErrorNormalization(NormalizedErrorAssertionsMixin, BaseAuthenticatedViewTestCase):
    """Pattern A: return STATUS, {"message": "..."}

    Middleware adds "error" (defaulting to "error") and "detail" (null).
    Original "message" is preserved.

    Tested via: PATCH /api/orgs/{id}/ — non-admin tries to update org.
    Location: users/api/orgs.py:114
    """

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.org_admin = UserFactory()
        cls.org = OrgFactory()
        # cls.user (from super) is a regular member, not admin
        OrgMemberFactory(org=cls.org, user=cls.user, role=OrgMemberRole.MEMBER.value)
        OrgMemberFactory(org=cls.org, user=cls.org_admin, role=OrgMemberRole.ADMIN.value)

    def test_non_admin_update_org_returns_403(self):
        """Non-admin member attempting to update org gets normalized error."""
        response = self.send_api_request(
            url=f"/api/orgs/{self.org.external_id}/",
            method="patch",
            data={"name": "New Name"},
        )

        self.assertEqual(response.status_code, HTTPStatus.FORBIDDEN)
        data = self.assert_normalized_error(
            response,
            expected_error="error",
            expected_message="Only admins can update the organization",
        )
        self.assertIsNone(data["detail"])

    def test_non_admin_delete_org_returns_403(self):
        """Non-admin member attempting to delete org gets normalized error."""
        response = self.send_api_request(
            url=f"/api/orgs/{self.org.external_id}/",
            method="delete",
        )

        self.assertEqual(response.status_code, HTTPStatus.FORBIDDEN)
        data = self.assert_normalized_error(
            response,
            expected_error="error",
            expected_message="Only admins can delete the organization",
        )
        self.assertIsNone(data["detail"])


class TestPatternBErrorNormalization(NormalizedErrorAssertionsMixin, BaseAuthenticatedViewTestCase):
    """Pattern B: return STATUS, {"error": "...", "message": "..."}

    Middleware preserves existing "error" and "message", adds "detail" (null).

    Tested via: POST /api/files/ — viewer tries to upload file.
    Location: filehub/api/files.py:116-117
    """

    def setUp(self):
        super().setUp()
        self.org = OrgFactory()
        project_creator = UserFactory()
        OrgMemberFactory(org=self.org, user=project_creator, role=OrgMemberRole.ADMIN.value)
        self.project = ProjectFactory(org=self.org, creator=project_creator)
        # Add self.user as a viewer (not org member) — only project-level viewer access
        ProjectEditorFactory(
            user=self.user,
            project=self.project,
            role=ProjectEditorRole.VIEWER.value,
        )

    def test_viewer_upload_file_returns_403_with_error_and_message(self):
        """Viewer attempting to upload file gets normalized error with preserved error code."""
        response = self.send_api_request(
            url="/api/files/",
            method="post",
            data={
                "project_id": str(self.project.external_id),
                "filename": "test.png",
                "content_type": "image/png",
                "size_bytes": 1024,
            },
        )

        self.assertEqual(response.status_code, HTTPStatus.FORBIDDEN)
        data = self.assert_normalized_error(
            response,
            expected_error="forbidden",
            expected_message="You do not have permission to upload files to this project",
        )
        self.assertIsNone(data["detail"])


class TestPatternCErrorNormalization(NormalizedErrorAssertionsMixin, BaseAuthenticatedViewTestCase):
    """Pattern C: return Response({"message": "..."}, status=...)

    Middleware adds "error" (defaulting to "error") and "detail" (null).
    Original "message" is preserved.

    Tested via: POST /api/orgs/{id}/members/ — add nonexistent email.
    Location: users/api/orgs.py:188
    """

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.org = OrgFactory()
        OrgMemberFactory(org=cls.org, user=cls.user, role=OrgMemberRole.MEMBER.value)

    def test_add_nonexistent_member_returns_404(self):
        """Adding a member with nonexistent email gets normalized error."""
        response = self.send_api_request(
            url=f"/api/orgs/{self.org.external_id}/members/",
            method="post",
            data={"email": "nonexistent@example.com", "role": "member"},
        )

        self.assertEqual(response.status_code, HTTPStatus.NOT_FOUND)
        data = self.assert_normalized_error(
            response,
            expected_error="error",
            expected_message="User with email nonexistent@example.com not found",
        )
        self.assertIsNone(data["detail"])


class TestPatternDErrorNormalization(NormalizedErrorAssertionsMixin, BaseAuthenticatedViewTestCase):
    """Pattern D: raise HttpError(STATUS, "...")

    Django Ninja produces {"detail": "..."}. Middleware copies detail string
    into "message" and adds "error" (defaulting to "error").

    Tested via: GET /api/imports/{id}/ — user views someone else's import.
    Location: imports/api/imports.py:197-198
    """

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.other_user = UserFactory()
        cls.org = OrgFactory()
        OrgMemberFactory(org=cls.org, user=cls.other_user, role=OrgMemberRole.ADMIN.value)
        cls.other_project = ProjectFactory(org=cls.org, creator=cls.other_user)
        cls.import_job = ImportJobFactory(
            user=cls.other_user,
            project=cls.other_project,
        )

    def test_access_other_users_import_returns_403(self):
        """Accessing another user's import job gets normalized error with detail as message."""
        response = self.send_api_request(
            url=f"/api/imports/{self.import_job.external_id}/",
            method="get",
        )

        self.assertEqual(response.status_code, HTTPStatus.FORBIDDEN)
        data = self.assert_normalized_error(
            response,
            expected_error="error",
            expected_message="You do not have access to this import job",
        )
        # detail string is preserved and also used as message
        self.assertEqual(data["detail"], "You do not have access to this import job")


class TestNinjaValidationErrorNormalization(NormalizedErrorAssertionsMixin, BaseAuthenticatedViewTestCase):
    """Django Ninja built-in: Pydantic validation errors → {"detail": [...]}

    Middleware adds "error" ("error") and "message" ("An error occurred."
    since detail is an array, not a string). Detail array is preserved.

    Tested via: POST /api/pages/ — missing required fields.
    """

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.org = OrgFactory()
        OrgMemberFactory(org=cls.org, user=cls.user, role=OrgMemberRole.MEMBER.value)
        cls.project = ProjectFactory(org=cls.org, creator=cls.user)

    def test_missing_title_returns_422_with_detail_array(self):
        """Missing required field triggers normalized error with detail array."""
        response = self.send_api_request(
            url="/api/pages/",
            method="post",
            data={"project_id": str(self.project.external_id)},
        )

        self.assertEqual(response.status_code, HTTPStatus.UNPROCESSABLE_ENTITY)
        data = self.assert_normalized_error(
            response,
            expected_error="error",
            expected_message="An error occurred.",
        )
        # Pydantic validation detail array is preserved
        self.assertIsInstance(data["detail"], list)
        self.assertGreater(len(data["detail"]), 0)
        error = data["detail"][0]
        self.assertIn("msg", error)
        self.assertIn("type", error)


class TestNinjaAuthErrorNormalization(NormalizedErrorAssertionsMixin, BaseAuthenticatedViewTestCase):
    """Django Ninja built-in: auth failure → {"detail": "Unauthorized"}

    Middleware copies detail string into "message" and adds "error" ("error").

    Tested via: GET /api/pages/ — unauthenticated request.
    """

    def test_unauthenticated_request_returns_401(self):
        """Unauthenticated request gets normalized error."""
        self.client.logout()

        response = self.client.get("/api/pages/")

        self.assertEqual(response.status_code, HTTPStatus.UNAUTHORIZED)
        data = self.assert_normalized_error(
            response,
            expected_error="error",
            expected_message="Unauthorized",
        )
        self.assertEqual(data["detail"], "Unauthorized")


class TestNinja404ErrorNormalization(NormalizedErrorAssertionsMixin, BaseAuthenticatedViewTestCase):
    """Django Ninja built-in: get_object_or_404 → {"detail": "Not Found"}

    Middleware copies detail string into "message" and adds "error" ("error").

    Tested via: PATCH /api/orgs/{id}/ — org the user is not a member of.
    """

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        # Create an org the user is NOT a member of
        cls.other_org = OrgFactory()

    def test_nonmember_org_returns_404_json(self):
        """get_object_or_404 with filtered queryset returns normalized 404 error."""
        response = self.send_api_request(
            url=f"/api/orgs/{self.other_org.external_id}/",
            method="patch",
            data={"name": "test"},
        )

        self.assertEqual(response.status_code, HTTPStatus.NOT_FOUND)
        data = self.assert_normalized_error(response, expected_error="error")
        self.assertTrue(data["detail"].startswith("Not Found"))
        self.assertTrue(data["message"].startswith("Not Found"))
