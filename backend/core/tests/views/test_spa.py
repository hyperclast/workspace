from http import HTTPStatus

from core.tests.common import BaseAuthenticatedViewTestCase, BaseViewTestCase


class TestHomepageUnauthenticated(BaseViewTestCase):
    """Test homepage view for unauthenticated users."""

    def test_unauthenticated_user_gets_landing(self):
        """Unauthenticated user should get landing page."""
        response = self.client.get("/")

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertTemplateUsed(response, "core/landing.html")


class TestHomepageAuthenticated(BaseAuthenticatedViewTestCase):
    """Test homepage view for authenticated users."""

    url_name = "core:home"

    def test_authenticated_user_gets_spa(self):
        """Authenticated user should get SPA template."""
        response = self.client.get("/")

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertTemplateUsed(response, "core/spa.html")


class TestSPARoutes(BaseViewTestCase):
    """Test explicit SPA routes."""

    def test_login_route(self):
        """/login/ should serve the SPA."""
        response = self.client.get("/login/")

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertTemplateUsed(response, "core/spa.html")

    def test_signup_route(self):
        """/signup/ should serve the SPA."""
        response = self.client.get("/signup/")

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertTemplateUsed(response, "core/spa.html")

    def test_settings_route(self):
        """/settings/ should serve the SPA."""
        response = self.client.get("/settings/")

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertTemplateUsed(response, "core/spa.html")

    def test_pages_route(self):
        """/pages/abc123/ should serve the SPA."""
        response = self.client.get("/pages/abc123/")

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertTemplateUsed(response, "core/spa.html")

    def test_pages_route_without_trailing_slash_redirects(self):
        """/pages/abc123 should redirect to /pages/abc123/."""
        response = self.client.get("/pages/abc123")

        self.assertEqual(response.status_code, HTTPStatus.MOVED_PERMANENTLY)
        self.assertEqual(response.url, "/pages/abc123/")


class TestTrailingSlashRedirects(BaseViewTestCase):
    """Test APPEND_SLASH redirects for Django routes."""

    def test_admin_without_slash_redirects(self):
        """Requesting /admin should redirect to /admin/."""
        response = self.client.get("/admin")

        self.assertEqual(response.status_code, HTTPStatus.MOVED_PERMANENTLY)
        self.assertEqual(response.url, "/admin/")

    def test_pricing_without_slash_redirects(self):
        """Requesting /pricing should redirect to /pricing/."""
        response = self.client.get("/pricing")

        self.assertEqual(response.status_code, HTTPStatus.MOVED_PERMANENTLY)
        self.assertEqual(response.url, "/pricing/")

    def test_login_without_slash_redirects(self):
        """Requesting /login should redirect to /login/."""
        response = self.client.get("/login")

        self.assertEqual(response.status_code, HTTPStatus.MOVED_PERMANENTLY)
        self.assertEqual(response.url, "/login/")

    def test_unknown_route_returns_404(self):
        """Unknown routes should return 404."""
        response = self.client.get("/unknown-route/")

        self.assertEqual(response.status_code, HTTPStatus.NOT_FOUND)
