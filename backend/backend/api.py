import importlib

from django.conf import settings
from ninja import NinjaAPI

from ask.api import router as ask_router
from core.api import router as utils_router
from pages.api import links_router, mentions_router, pages_router, projects_router
from users.api import ai_router, orgs_router, users_router


if settings.RUNTIME_ENV == "dev":
    api = NinjaAPI()

else:
    api = NinjaAPI(docs_url=None, openapi_url=None)


api.add_router("/users/", users_router)
api.add_router("/orgs/", orgs_router)
api.add_router("/ai/", ai_router)
api.add_router("", projects_router)  # For /orgs/{id}/projects and /projects/{id}
api.add_router("/pages/", pages_router)
api.add_router("/pages/", links_router)
api.add_router("/mentions/", mentions_router)
api.add_router("/ask/", ask_router)
api.add_router("/utils/", utils_router)


def _register_private_routers():
    """Auto-discover and register API routers from private apps."""
    for app_name in getattr(settings, "PRIVATE_APPS", []):
        short_name = app_name.replace("private.", "")
        try:
            api_module = importlib.import_module(f"{app_name}.api")
            if hasattr(api_module, "router"):
                api.add_router(f"/{short_name}/", api_module.router)
        except ImportError:
            pass


_register_private_routers()
