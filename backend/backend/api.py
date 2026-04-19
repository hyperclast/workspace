import importlib

from django.conf import settings
from ninja import NinjaAPI

from ask.api import router as ask_router
from core.api import router as utils_router
from filehub.api import files_router, webhooks_router
from imports.api import imports_router
from pages.api import (
    comments_router,
    folders_router,
    links_router,
    mentions_router,
    pages_router,
    projects_router,
    rewind_router,
)
from users.api import ai_router, daily_note_router, devices_router, orgs_router, tokens_router, users_router


if settings.RUNTIME_ENV == "dev":
    api = NinjaAPI()

else:
    api = NinjaAPI(docs_url=None, openapi_url=None)


api.add_router("/users/", users_router)
api.add_router("/users/me/devices", devices_router)
api.add_router("/users/me/tokens", tokens_router)
api.add_router("/users/me/daily-note/", daily_note_router)
api.add_router("/orgs/", orgs_router)
api.add_router("/ai/", ai_router)
api.add_router("", projects_router)  # For /orgs/{id}/projects and /projects/{id}
api.add_router("", folders_router)  # For /projects/{id}/folders/*
api.add_router("/pages/", pages_router)
api.add_router("/pages/", rewind_router)
api.add_router("/pages/", links_router)
api.add_router("/pages/", comments_router)
api.add_router("/mentions/", mentions_router)
api.add_router("/ask/", ask_router)
api.add_router("/utils/", utils_router)
api.add_router("/files/", files_router)
api.add_router("/files/webhooks/", webhooks_router)
api.add_router("/imports/", imports_router)


def _register_private_routers():
    """Auto-discover and register API routers from private apps.

    Each app's ``api`` module may define a ``ROUTER_PREFIX`` attribute to
    override the default URL prefix (which is the app directory name).
    Example: ``ROUTER_PREFIX = "/referrals/"`` in ``private/referrals/api.py``.
    """
    for app_name in getattr(settings, "PRIVATE_APPS", []):
        short_name = app_name.replace("private.", "")
        try:
            api_module = importlib.import_module(f"{app_name}.api")
            if hasattr(api_module, "router"):
                prefix = getattr(api_module, "ROUTER_PREFIX", f"/{short_name}/")
                api.add_router(prefix, api_module.router)
        except ImportError:
            pass


_register_private_routers()
