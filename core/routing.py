"""
WebSocket URL routing for FaceChan.
Mounted under /ws/ in facechan/asgi.py.
"""

from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    re_path(r'^ws/notifications/$', consumers.NotificationConsumer.as_asgi()),
    re_path(r'^ws/boards/(?P<slug>[\w-]+)/$', consumers.BoardConsumer.as_asgi()),
]
