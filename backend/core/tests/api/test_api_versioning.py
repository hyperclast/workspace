"""
Tests verifying that /api/v1/ versioned paths work identically to /api/ paths.

These tests will FAIL until the versioned URL path is added to urls.py (Step 2).
Each test hits one endpoint category via /api/v1/ and verifies it returns
the expected status code.
"""

from http import HTTPStatus

from core.tests.common import BaseAuthenticatedViewTestCase


class TestVersionedAPIPaths(BaseAuthenticatedViewTestCase):
    """Verify /api/v1/ paths serve the same endpoints as /api/ paths."""

    def test_list_pages_via_versioned_path(self):
        """Pages — GET /api/v1/pages/"""
        response = self.client.get("/api/v1/pages/")
        self.assertEqual(response.status_code, HTTPStatus.OK)

    def test_list_projects_via_versioned_path(self):
        """Projects — GET /api/v1/projects/"""
        response = self.client.get("/api/v1/projects/")
        self.assertEqual(response.status_code, HTTPStatus.OK)

    def test_list_orgs_via_versioned_path(self):
        """Orgs — GET /api/v1/orgs/"""
        response = self.client.get("/api/v1/orgs/")
        self.assertEqual(response.status_code, HTTPStatus.OK)

    def test_get_current_user_via_versioned_path(self):
        """Users — GET /api/v1/users/me/"""
        response = self.client.get("/api/v1/users/me/")
        self.assertEqual(response.status_code, HTTPStatus.OK)

    def test_list_my_files_via_versioned_path(self):
        """Files — GET /api/v1/files/mine/"""
        response = self.client.get("/api/v1/files/mine/")
        self.assertEqual(response.status_code, HTTPStatus.OK)

    def test_list_imports_via_versioned_path(self):
        """Imports — GET /api/v1/imports/"""
        response = self.client.get("/api/v1/imports/")
        self.assertEqual(response.status_code, HTTPStatus.OK)

    def test_list_mentions_via_versioned_path(self):
        """Mentions — GET /api/v1/mentions/"""
        response = self.client.get("/api/v1/mentions/")
        self.assertEqual(response.status_code, HTTPStatus.OK)
