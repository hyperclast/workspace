from http import HTTPStatus

from django.test import TestCase, override_settings

from core.tests.common import BaseAuthenticatedViewTestCase, BaseViewTestCase
from core.views.home import get_app_config


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

    def test_authenticated_user_without_pages_redirects_to_welcome(self):
        """Authenticated user without pages should redirect to welcome page."""
        response = self.client.get("/")

        self.assertRedirects(response, "/welcome/")

    def test_authenticated_user_with_pages_redirects_to_first_page(self):
        """Authenticated user with pages should redirect to first page."""
        from pages.tests.factories import PageFactory, ProjectFactory
        from users.tests.factories import OrgFactory

        org = OrgFactory()
        org.members.add(self.user)
        project = ProjectFactory(org=org, creator=self.user)
        page = PageFactory(project=project, creator=self.user)
        page.editors.add(self.user)

        response = self.client.get("/")

        self.assertRedirects(response, f"/pages/{page.external_id}/")


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


class TestGetAppConfig(TestCase):
    """Test get_app_config() returns correct configuration values."""

    def test_default_values(self):
        """Returns expected defaults when no env vars override."""
        config = get_app_config()

        self.assertEqual(config["imports"]["pdfMaxFileSize"], 20 * 1024 * 1024)
        self.assertEqual(config["imports"]["maxFileSize"], 104857600)
        self.assertEqual(config["filehub"]["maxFileSize"], 10485760)

    @override_settings(WS_IMPORTS_PDF_MAX_FILE_SIZE_BYTES=50 * 1024 * 1024)
    def test_custom_pdf_max_size(self):
        """Custom PDF max size flows through."""
        config = get_app_config()

        self.assertEqual(config["imports"]["pdfMaxFileSize"], 50 * 1024 * 1024)

    @override_settings(WS_IMPORTS_MAX_FILE_SIZE_BYTES=200 * 1024 * 1024)
    def test_custom_import_max_size(self):
        """Custom import max size flows through."""
        config = get_app_config()

        self.assertEqual(config["imports"]["maxFileSize"], 200 * 1024 * 1024)

    @override_settings(WS_FILEHUB_MAX_FILE_SIZE_BYTES=25 * 1024 * 1024)
    def test_custom_filehub_max_size(self):
        """Custom filehub max size flows through."""
        config = get_app_config()

        self.assertEqual(config["filehub"]["maxFileSize"], 25 * 1024 * 1024)

    def test_structure(self):
        """Config has the expected top-level keys."""
        config = get_app_config()

        self.assertIn("imports", config)
        self.assertIn("filehub", config)
        self.assertIn("pdfMaxFileSize", config["imports"])
        self.assertIn("maxFileSize", config["imports"])
        self.assertIn("maxFileSize", config["filehub"])


class TestSPAAppConfigContext(BaseViewTestCase):
    """Test that app_config is included in SPA template context."""

    def test_spa_includes_app_config(self):
        """SPA view passes app_config to the template."""
        response = self.client.get("/login/")

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertIn("app_config", response.context)
        self.assertIn("imports", response.context["app_config"])
        self.assertIn("filehub", response.context["app_config"])

    def test_app_config_rendered_in_html(self):
        """app-config JSON script tag is present in response HTML."""
        response = self.client.get("/login/")

        self.assertContains(response, 'id="app-config"')
        self.assertContains(response, "pdfMaxFileSize")
        self.assertContains(response, "window._appConfig")
