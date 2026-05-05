from unittest.mock import patch

from django.template import TemplateDoesNotExist
from django.test import RequestFactory, TestCase, override_settings
from django.urls import get_resolver

from backend import urls as project_urls
from core.views import errors


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

    def test_branding_fallback_dict_has_safe_defaults(self):
        """Direct unit test on the fallback dict: even with no settings configured,
        it must always have a brand_name. Other downstream templates depend on it."""
        fallback = errors._branding_fallback()
        self.assertEqual(fallback["brand_name"], "Hyperclast")
        self.assertIn("support_email", fallback)
        self.assertIn("deployment_id", fallback)


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
        self.assertIn("500", body)
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
        self.assertIn("404", response.content.decode())

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
