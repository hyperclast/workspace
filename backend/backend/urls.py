from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.sitemaps.views import sitemap
from django.urls import include, path

from core.sitemaps import sitemaps
from core.views import email_confirm, email_verification_sent

from .api import api


urlpatterns = [
    path("sitemap.xml", sitemap, {"sitemaps": sitemaps}, name="sitemap"),
    path("accounts/confirm-email/<str:key>/", email_confirm, name="account_confirm_email"),
    path("accounts/confirm-email/", email_verification_sent, name="account_email_verification_sent"),
    path("accounts/", include("allauth.urls")),
    path("admin/", admin.site.urls),
    path("anymail/", include("anymail.urls")),
    path("api/", include("allauth.headless.urls")),
    path("api/", api.urls),
    path("hijack/", include("hijack.urls")),
    path("rq_dashboard/", include("django_rq.urls")),
    path("", include(("pages.urls", "pages"), namespace="pages")),
    path("", include(("users.urls", "users"), namespace="users")),
    path("", include(("core.urls", "core"), namespace="core")),
    path("updates/", include(("updates.urls", "updates"), namespace="updates")),
    path("pulse/", include(("pulse.urls", "pulse"), namespace="pulse")),
]

try:
    urlpatterns.insert(0, path("", include("private.urls")))
except ImportError:
    pass


if settings.RUNTIME_ENV == "dev":
    from debug_toolbar.toolbar import debug_toolbar_urls

    urlpatterns += [
        *debug_toolbar_urls(),
        *static(settings.STATIC_URL, document_root=settings.STATIC_ROOT),
    ]
