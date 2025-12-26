from django.conf import settings
from django.urls import path, re_path
from django.views.static import serve

from . import views

FAVICON_DIR = settings.BASE_DIR / "core" / "static" / "core" / "img" / "favicon"

urlpatterns = [
    # Favicon files at root
    path("favicon.ico", serve, {"document_root": FAVICON_DIR, "path": "favicon.ico"}),
    path("favicon.svg", serve, {"document_root": FAVICON_DIR, "path": "favicon.svg"}),
    path("favicon-96x96.png", serve, {"document_root": FAVICON_DIR, "path": "favicon-96x96.png"}),
    path("apple-touch-icon.png", serve, {"document_root": FAVICON_DIR, "path": "apple-touch-icon.png"}),
    path("site.webmanifest", serve, {"document_root": FAVICON_DIR, "path": "site.webmanifest"}),
    path("web-app-manifest-192x192.png", serve, {"document_root": FAVICON_DIR, "path": "web-app-manifest-192x192.png"}),
    path("web-app-manifest-512x512.png", serve, {"document_root": FAVICON_DIR, "path": "web-app-manifest-512x512.png"}),
    #
    path("about/", views.about, name="about"),
    path("dev/", views.dev_index, name="dev_index"),
    path("dev/api/", views.api_docs, name="api_docs_index"),
    path("dev/api/<str:doc_name>/", views.api_docs, name="api_docs"),
    path("dev/oss/", views.oss_index, name="oss_index"),
    path("dev/oss/<str:repo_name>/", views.oss_repo, name="oss_repo"),
    path("pricing/", views.pricing, name="pricing"),
    path("privacy/", views.privacy, name="privacy"),
    path("terms/", views.terms, name="terms"),
    path("", views.homepage, name="home"),
    # SPA routes - explicitly defined
    path("login/", views.spa, name="login"),
    path("signup/", views.spa, name="signup"),
    path("invitation/", views.spa, name="invitation"),
    path("reset-password/", views.spa, name="reset-password"),
    path("forgot-password/", views.spa, name="forgot-password"),
    path("settings/", views.spa, name="settings"),
    re_path(r"^pages/(?P<page_id>[^/]+)/$", views.spa, name="page"),
]
