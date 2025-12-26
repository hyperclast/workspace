"""
ASGI config for Hyperclast backend.
Exposes both HTTP and WebSocket applications.
"""

import os

from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "backend.settings.dev")

# Initialize Django ASGI application early
django_asgi_app = get_asgi_application()

# Import after Django setup
from collab.routing import websocket_urlpatterns

# Removed AllowedHostsOriginValidator for local testing
application = ProtocolTypeRouter(
    {
        "http": django_asgi_app,
        "websocket": AuthMiddlewareStack(URLRouter(websocket_urlpatterns)),
    }
)
