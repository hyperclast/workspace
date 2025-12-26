"""
WebSocket URL routing for collaborative editing.
"""

from django.urls import path

from .consumers import PageYjsConsumer

websocket_urlpatterns = [
    path("ws/pages/<str:page_uuid>/", PageYjsConsumer.as_asgi()),
]
