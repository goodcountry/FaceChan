"""
ASGI config for FaceChan.

Handles both HTTP (Django) and WebSocket (Channels) connections.

URL structure:
  /ws/*  → Channels WebSocket consumers (core/routing.py)
  /*     → Standard Django ASGI application (HTTP)

The channel layer uses Redis (same instance as Celery) so no extra
infrastructure is needed.
"""

import os

from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.security.websocket import AllowedHostsOriginValidator

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'facechan.settings')

# Initialise Django before importing anything that touches models/settings
django_asgi_app = get_asgi_application()

from core.routing import websocket_urlpatterns  # noqa: E402 — must be after Django setup

application = ProtocolTypeRouter({
    # Standard HTTP — handled by Django as normal
    "http": django_asgi_app,

    # WebSocket — validated against ALLOWED_HOSTS then routed
    "websocket": AllowedHostsOriginValidator(
        URLRouter(websocket_urlpatterns)
    ),
})
