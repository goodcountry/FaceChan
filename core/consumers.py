"""
WebSocket consumers for FaceChan.

NotificationConsumer — one persistent connection per authenticated user.
Each user joins their own private group: "notifications_{user_id}".

When a post is created, views.py sends a message to that group via the
channel layer. The consumer forwards it to the browser instantly.

Falls back gracefully — if the WebSocket drops, NotificationContext.jsx
reverts to the 60s polling safety net.

ActivityPub hook: incoming federated activities will push to the same
group format, requiring no changes to this consumer.
"""

import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from rest_framework.authtoken.models import Token


class NotificationConsumer(AsyncWebsocketConsumer):

    async def connect(self):
        """
        Authenticate via token passed as query param ?token=<key>.
        We can't use cookies/session over WS easily, so the frontend
        passes the DRF token in the query string over the encrypted
        connection (WSS in prod, WS in dev — both acceptable).
        """
        self.user = await self._get_user()

        if self.user is None:
            await self.close(code=4001)
            return

        self.group_name = f"notifications_{self.user.id}"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, code):
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data=None, bytes_data=None):
        # Client sends nothing meaningful — connections are receive-only.
        # Silently ignore any incoming messages.
        pass

    # ------------------------------------------------------------------
    # Group message handler — called when views.py pushes a notification
    # ------------------------------------------------------------------
    async def send_notification(self, event):
        """
        Relay a notification event to the WebSocket client.

        event shape (set by views.py):
        {
            "type": "send.notification",   # channels routing key
            "unread": <int>,               # current unread count
            "thread_id": <int>,
            "thread_title": <str>,
            "post_id": <int>,
        }
        """
        await self.send(text_data=json.dumps({
            "type": "notification",
            "unread": event.get("unread", 0),
            "thread_id": event.get("thread_id"),
            "thread_title": event.get("thread_title", ""),
            "post_id": event.get("post_id"),
        }))

    # ------------------------------------------------------------------
    # Auth helper
    # ------------------------------------------------------------------
    @database_sync_to_async
    def _get_user(self):
        query_string = self.scope.get("query_string", b"").decode()
        params = dict(
            pair.split("=", 1)
            for pair in query_string.split("&")
            if "=" in pair
        )
        token_key = params.get("token")
        if not token_key:
            return None
        try:
            token = Token.objects.select_related("user").get(key=token_key)
            user = token.user
            # Respect bans — banned users get no connection
            if user.is_banned:
                return None
            return user
        except Token.DoesNotExist:
            return None


class BoardConsumer(AsyncWebsocketConsumer):
    """
    Board-scoped WebSocket — pushes new threads to anyone viewing a board.

    Used to deliver federated threads in real time without a page refresh.
    Connection: /ws/boards/<slug>/
    No authentication required — board feeds are public.
    """

    async def connect(self):
        self.slug = self.scope['url_route']['kwargs']['slug']
        self.group_name = f'board_{self.slug}'
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, code):
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data=None, bytes_data=None):
        pass  # receive-only

    async def new_thread(self, event):
        """Push a new thread card to connected clients."""
        await self.send(text_data=json.dumps({
            'type': 'new_thread',
            'thread': event['thread'],
        }))
