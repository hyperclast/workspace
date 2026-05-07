from unittest.mock import patch

from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from django.template import Context, Template, TemplateDoesNotExist
from django.test import Client, RequestFactory, TestCase, override_settings
from django.urls import get_resolver, path

from backend import urls as project_urls
from core.views import errors


def _boom_view(request):
    """View that raises an unhandled exception — used by the end-to-end
    integration test below to drive Django's real middleware path through
    handler500.
    """
    raise RuntimeError("intentional test failure")


def _forbidden_view(request):
    """View that raises PermissionDenied — Django's middleware translates
    this into a 403 and dispatches to handler403.
    """
    raise PermissionDenied("intentional forbidden")


def _ok_view(request):
    return HttpResponse("ok")


urlpatterns = [
    path("__boom__/", _boom_view),
    path("__forbidden__/", _forbidden_view),
    path("__ok__/", _ok_view),
]
handler500 = "core.views.errors.handler500"
handler404 = "core.views.errors.handler404"
handler403 = "core.views.errors.handler403"


class TestErrorHandlerWiring(TestCase):
    """The point of this test is to make the wiring impossible to silently undo.

    Django's defaults.server_error renders error templates with an EMPTY Context
    (no context processors), which is why brand_name was missing on every 500.
    Our custom handlers go through django.shortcuts.render, which uses
    RequestContext and runs context processors. If anyone reverts the wiring,
    these assertions break.
    """

    def test_handler500_points_to_custom_view(self):
        self.assertEqual(project_urls.handler500, "core.views.errors.handler500")

    def test_handler404_points_to_custom_view(self):
        self.assertEqual(project_urls.handler404, "core.views.errors.handler404")

    def test_handler403_points_to_custom_view(self):
        self.assertEqual(project_urls.handler403, "core.views.errors.handler403")

    def test_resolver_resolves_handler500_to_our_callable(self):
        """Django actually looks up handler500 from the resolver — confirm it lands here."""
        resolver = get_resolver()
        callback = resolver.resolve_error_handler(500)
        self.assertIs(callback, errors.handler500)


@override_settings(BRAND_NAME="Hyperclast")
class TestErrorHandlerRendering(TestCase):
    """Ensures error templates render with branding context populated.

    Asserts on `og:site_name` content (from _seo_meta.html) because that
    template directly interpolates {{ brand_name }} with no `|default:`
    fallback. If the context processor doesn't run, the attribute renders as
    `content=""` and the assertion fails — proving the regression.
    """

    def setUp(self):
        self.factory = RequestFactory()

    def _assert_brand_name_rendered(self, response, status):
        self.assertEqual(response.status_code, status)
        body = response.content.decode()
        self.assertIn('property="og:site_name" content="Hyperclast"', body)

    def test_handler500_renders_with_branding_context(self):
        response = errors.handler500(self.factory.get("/"))
        self._assert_brand_name_rendered(response, 500)

    def test_handler404_renders_with_branding_context(self):
        response = errors.handler404(self.factory.get("/missing"))
        self._assert_brand_name_rendered(response, 404)

    def test_handler403_renders_with_branding_context(self):
        response = errors.handler403(self.factory.get("/forbidden"))
        self._assert_brand_name_rendered(response, 403)


@override_settings(BRAND_NAME="Acme")
class TestErrorHandlerBrandingFollowsSettings(TestCase):
    """If BRAND_NAME changes, the rendered output should follow it.

    This proves brand_name is coming from the live context processor, not a
    template literal someone hardcoded.
    """

    def test_handler500_uses_current_brand_name(self):
        response = errors.handler500(RequestFactory().get("/"))
        self.assertEqual(response.status_code, 500)
        self.assertIn('property="og:site_name" content="Acme"', response.content.decode())


@override_settings(BRAND_NAME="Hyperclast")
class TestSafeRenderProcessorFallback(TestCase):
    """Layer 2 of _safe_render: when context processors fail, we still want
    the user to see the nice branded page — not a bare HTML stub. This layer
    re-renders the template with an explicit context that bypasses processors.
    """

    def setUp(self):
        self.factory = RequestFactory()

    def test_renders_branded_page_when_context_processors_fail(self):
        """If the normal render() raises (e.g. a context processor blew up),
        the explicit-context fallback should still produce the nice page with
        brand_name populated. Users never see the plain-HTML stub here."""
        with patch("core.views.errors.render", side_effect=RuntimeError("processor crashed")):
            response = errors.handler500(self.factory.get("/"))

        self.assertEqual(response.status_code, 500)
        body = response.content.decode()
        # The nice template still rendered, with branding intact.
        self.assertIn('property="og:site_name" content="Hyperclast"', body)
        # And it's the actual error template, not the bare-HTML last-resort stub.
        self.assertIn("Unexpected Error", body)

    def test_layer2_falls_through_brand_name_from_settings(self):
        """The explicit-context fallback must use the live BRAND_NAME setting,
        not a stale hardcoded value."""
        with (
            override_settings(BRAND_NAME="Acme"),
            patch("core.views.errors.render", side_effect=RuntimeError("processor crashed")),
        ):
            response = errors.handler500(self.factory.get("/"))

        self.assertIn('property="og:site_name" content="Acme"', response.content.decode())

    def test_layer2_support_email_follows_frontend_url(self):
        """The fallback's support_email must be derived from the live
        FRONTEND_URL setting (same logic as the live context processor),
        not a hardcoded `support@hyperclast.com`. Otherwise rebranded
        deployments leak the Hyperclast domain on every error page."""
        with (
            override_settings(BRAND_NAME="Acme", FRONTEND_URL="https://acme.example/"),
            patch("core.views.errors.render", side_effect=RuntimeError("processor crashed")),
        ):
            response = errors.handler500(self.factory.get("/"))

        body = response.content.decode()
        self.assertIn("mailto:support@acme.example", body)
        self.assertNotIn("support@hyperclast.com", body)

    def test_branding_fallback_dict_pulls_support_email_from_settings(self):
        """Direct unit test on the fallback dict: support_email is computed
        from FRONTEND_URL via the same helper as the context processor."""
        with override_settings(FRONTEND_URL="https://acme.example/"):
            fallback = errors._branding_fallback()
        self.assertEqual(fallback["support_email"], "support@acme.example")

    def test_branding_fallback_dict_pulls_private_features_from_settings(self):
        """pricing_enabled and referrals_enabled must reflect PRIVATE_FEATURES,
        matching how the live context processor computes them."""
        with override_settings(PRIVATE_FEATURES=["pricing", "referrals"]):
            fallback = errors._branding_fallback()
        self.assertTrue(fallback["pricing_enabled"])
        self.assertTrue(fallback["referrals_enabled"])

        with override_settings(PRIVATE_FEATURES=[]):
            fallback = errors._branding_fallback()
        self.assertFalse(fallback["pricing_enabled"])
        self.assertFalse(fallback["referrals_enabled"])

    def test_branding_fallback_dict_has_safe_defaults(self):
        """Direct unit test on the fallback dict: not just key-presence, but
        actual values. After P1, support_email is computed from FRONTEND_URL
        rather than hardcoded — so a localhost FRONTEND_URL must produce the
        documented `support@example.com` value (matching the live processor)
        and deployment_id must mirror WS_DEPLOYMENT_ID."""
        with override_settings(
            FRONTEND_URL="http://localhost:9800",
            WS_DEPLOYMENT_ID="prod_e2e",
        ):
            fallback = errors._branding_fallback()
        self.assertEqual(fallback["brand_name"], "Hyperclast")
        self.assertEqual(fallback["support_email"], "support@example.com")
        self.assertEqual(fallback["deployment_id"], "prod_e2e")


class TestSafeRenderPlainHtmlLastResort(TestCase):
    """Layer 3: plain HTML is reached ONLY when both layer 1 and layer 2 fail
    (e.g. the template file itself is broken or missing). This is rare but
    important — without this, a busted template would loop into another
    handler500 invocation.
    """

    def setUp(self):
        self.factory = RequestFactory()

    def test_plain_html_when_template_missing(self):
        with (
            patch("core.views.errors.render", side_effect=TemplateDoesNotExist("500.html")),
            patch("core.views.errors.get_template", side_effect=TemplateDoesNotExist("500.html")),
        ):
            response = errors.handler500(self.factory.get("/"))

        self.assertEqual(response.status_code, 500)
        body = response.content.decode()
        self.assertIn("<!DOCTYPE html>", body)
        self.assertIn("<h1>500</h1>", body)
        self.assertIn("Something went wrong.", body)
        self.assertEqual(response["Content-Type"], "text/html; charset=utf-8")

    def test_plain_html_when_both_render_paths_fail(self):
        """Both layers must fail before we drop to plain HTML — confirms the
        ordering and that we don't shortcut past layer 2."""
        with (
            patch("core.views.errors.render", side_effect=Exception("layer 1 failed")),
            patch("core.views.errors.get_template", side_effect=Exception("layer 2 failed")),
        ):
            response = errors.handler404(self.factory.get("/"))

        self.assertEqual(response.status_code, 404)
        body = response.content.decode()
        self.assertIn("<h1>404</h1>", body)
        self.assertIn("Something went wrong.", body)

    def test_handler_does_not_re_raise(self):
        """The handler must swallow rendering errors completely — re-raising
        would defeat the purpose, since Django would then call handler500
        again and we'd be in an infinite loop."""
        with (
            patch("core.views.errors.render", side_effect=Exception("anything")),
            patch("core.views.errors.get_template", side_effect=Exception("also anything")),
        ):
            try:
                response = errors.handler500(self.factory.get("/"))
            except Exception as exc:
                self.fail(f"handler500 must not re-raise, but did: {exc!r}")

        self.assertEqual(response.status_code, 500)


class TestSeoMetaPartialDefaults(TestCase):
    """Belt-and-suspenders check on _seo_meta.html.

    Even if some future code path renders a page with no `brand_name` in the
    context (e.g. a custom error route, a stripped-down management view), the
    template must not produce empty `content=""` attributes for og:site_name /
    og:title / twitter:title. The `|default:'Hyperclast'` filters guarantee a
    sensible literal as the last line of defense — independent of whether
    context processors ran.
    """

    TEMPLATE = "{% include 'core/partials/_seo_meta.html' %}"

    def _render(self, context):
        return Template("{% load static %}" + self.TEMPLATE).render(Context(context))

    def test_og_site_name_falls_back_when_brand_name_missing(self):
        body = self._render({})
        self.assertIn('property="og:site_name" content="Hyperclast"', body)
        self.assertNotIn('property="og:site_name" content=""', body)

    def test_og_title_falls_back_when_brand_name_and_seo_title_missing(self):
        body = self._render({})
        self.assertIn('property="og:title" content="Hyperclast"', body)
        self.assertNotIn('property="og:title" content=""', body)

    def test_twitter_title_falls_back_when_brand_name_and_seo_title_missing(self):
        body = self._render({})
        self.assertIn('name="twitter:title" content="Hyperclast"', body)
        self.assertNotIn('name="twitter:title" content=""', body)

    def test_brand_name_in_context_takes_precedence_over_default(self):
        body = self._render({"brand_name": "Acme"})
        self.assertIn('property="og:site_name" content="Acme"', body)
        self.assertIn('property="og:title" content="Acme"', body)
        self.assertIn('name="twitter:title" content="Acme"', body)

    def test_seo_title_in_context_takes_precedence_over_brand_name_default(self):
        body = self._render({"seo_title": "My Page"})
        self.assertIn('property="og:title" content="My Page"', body)
        self.assertIn('name="twitter:title" content="My Page"', body)
        self.assertIn('property="og:site_name" content="Hyperclast"', body)


@override_settings(
    ROOT_URLCONF=__name__,
    DEBUG=False,
    BRAND_NAME="Hyperclast",
    ALLOWED_HOSTS=["*"],
)
class TestErrorHandlerEndToEnd(TestCase):
    """End-to-end integration test: a real view raising → middleware →
    handler500 → branded HTML.

    All other handler tests in this file call ``errors.handler500(...)``
    directly with a ``RequestFactory`` request, which proves the renderer
    works but doesn't exercise the path Django actually walks at runtime
    (URL resolver → middleware → exception → handler dispatch). This test
    closes that loop by mounting a temporary urlconf (this very module)
    that points at three routes: a 500-raising view, a 403-raising view,
    and an unmatched-URL test for 404.
    """

    def setUp(self):
        # raise_request_exception=False prevents the test client from
        # re-raising the view's RuntimeError so the 500 page can render.
        self.client_no_raise = Client(raise_request_exception=False)

    def test_view_exception_renders_branded_500_page(self):
        response = self.client_no_raise.get("/__boom__/")
        self.assertEqual(response.status_code, 500)
        body = response.content.decode()
        self.assertIn('property="og:site_name" content="Hyperclast"', body)

    def test_unmatched_url_renders_branded_404_page(self):
        response = self.client.get("/__no_such_url__/")
        self.assertEqual(response.status_code, 404)
        body = response.content.decode()
        self.assertIn('property="og:site_name" content="Hyperclast"', body)

    def test_permission_denied_renders_branded_403_page(self):
        response = self.client.get("/__forbidden__/")
        self.assertEqual(response.status_code, 403)
        body = response.content.decode()
        self.assertIn('property="og:site_name" content="Hyperclast"', body)
