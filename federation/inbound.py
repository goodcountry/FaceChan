"""
federation/inbound.py

Handles inbound ActivityPub Create(Note) activities — federated threads
arriving from approved remote instances.

Flow:
  1. Extract the Note object and the remote board context from the activity
  2. Look up RemoteBoardMapping to find which local board to file it under
  3. Get or create a stub User for the remote author
  4. Create a local Thread marked is_remote=True
  5. Push to the board's WebSocket channel group
"""

import logging
from urllib.parse import urlparse

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from core.models import Board, Thread
from federation.models import RemoteInstance, RemoteBoardMapping, RemoteActor, FederationActivity

logger = logging.getLogger(__name__)


def handle_create_note(activity, remote_instance, log_entry):
    """
    Process a Create(Note) activity from an approved remote instance.

    Args:
        activity:        Parsed activity JSON dict
        remote_instance: Approved RemoteInstance the activity came from
        log_entry:       FederationActivity for audit logging
    """
    obj = activity.get('object', {})
    if not isinstance(obj, dict):
        log_entry.status = 'rejected'
        log_entry.error = 'Create activity object is not a dict'
        log_entry.save(update_fields=['status', 'error'])
        return

    obj_type = obj.get('type', '')
    if obj_type != 'Note':
        # We only handle Note objects for now
        log_entry.status = 'rejected'
        log_entry.error = f'Unhandled object type: {obj_type}'
        log_entry.save(update_fields=['status', 'error'])
        return

    # Route: Notes with inReplyTo are replies; Notes without are thread OPs
    if obj.get('inReplyTo'):
        handle_create_reply(activity, obj, remote_instance, log_entry)
        return

    note_id = obj.get('id', '')
    if not note_id:
        log_entry.status = 'rejected'
        log_entry.error = 'Note has no id'
        log_entry.save(update_fields=['status', 'error'])
        return

    # Deduplicate — reject if we already have this Note
    if Thread.objects.filter(remote_ap_id=note_id).exists():
        log_entry.status = 'rejected'
        log_entry.error = f'Duplicate Note id: {note_id}'
        log_entry.save(update_fields=['status', 'error'])
        return

    # Resolve the remote board slug from the Note's context field
    # context should be the remote board Actor URL e.g. http://other.tld/ap/boards/Pols
    remote_board_url = obj.get('context', '') or activity.get('context', '')
    local_board = _resolve_local_board(remote_board_url, remote_instance)
    if local_board is None:
        log_entry.status = 'rejected'
        log_entry.error = f'No board mapping for remote board: {remote_board_url}'
        log_entry.save(update_fields=['status', 'error'])
        return

    # Resolve or create stub user for the remote author.
    # Anonymous posts are attributed to the board's own Group actor (see
    # build_thread_note), not a Person — obj['facechan:anonymous'] is how
    # the origin server tells us that, so we must not treat that Group
    # actor as if it were the post's author.
    attributed_to = obj.get('attributedTo', '')
    if isinstance(attributed_to, list):
        # Take the first Person actor if multiple attributions
        attributed_to = next(
            (a for a in attributed_to if isinstance(a, str) and 'users' in a),
            attributed_to[0] if attributed_to else ''
        )
    if obj.get('facechan:anonymous'):
        remote_author = None
    else:
        remote_author = _get_or_create_stub_user(attributed_to, remote_instance)

    # Build the thread
    title = obj.get('name', '') or obj.get('summary', '') or _truncate(obj.get('content', ''), 100)
    body = obj.get('content', '')

    if not title or not body:
        log_entry.status = 'rejected'
        log_entry.error = 'Note missing name/content'
        log_entry.save(update_fields=['status', 'error'])
        return

    # Strip basic HTML from content — remote servers may send HTML
    body = _strip_html(body)
    title = _strip_html(title)

    try:
        thread = Thread.objects.create(
            board=local_board,
            author=remote_author,
            title=title,
            body=body,
            is_remote=True,
            remote_ap_id=note_id,
            remote_actor_url=attributed_to or '',
            # Relay metadata — stored exactly as received. The hop count and
            # seen-instances list already reflect every instance this
            # activity has passed through, including the one that just sent
            # it to us — both build_thread_note (origin) and build_relay_note
            # (relay) append the sender's own domain before delivery, so we
            # don't append anything further here at receive time. Defaults
            # of 0/[] only apply if the sender is a non-FaceChan AP server
            # that doesn't send this extension at all.
            relay_hop_count=obj.get('facechan:relayHopCount', 0),
            relay_seen_instances=obj.get('facechan:relaySeenInstances', []),
        )
    except Exception as e:
        log_entry.status = 'failed'
        log_entry.error = f'Thread creation failed: {e}'
        log_entry.save(update_fields=['status', 'error'])
        logger.exception('Failed to create remote thread from %s', note_id)
        return

    log_entry.status = 'delivered'
    log_entry.save(update_fields=['status'])
    logger.info('Created remote thread %s in /%s/', thread.pk, local_board.slug)

    # Push to board WebSocket channel so users see it without refresh
    _push_thread_to_board(thread, local_board)



def handle_create_reply(activity, obj, remote_instance, log_entry):
    """
    Process a Create(Note) activity where the Note has an inReplyTo field —
    i.e. a reply to an existing thread.

    The inReplyTo value is the canonical AP URL of the parent thread. We
    resolve it to a local Thread by:
      1. Matching against Thread.remote_ap_id (remote thread we already have)
      2. Matching against thread_object_url pattern (local thread UUID)

    If we cannot find the parent thread we reject — orphaned replies are not stored.
    """
    import uuid as uuid_mod
    from core.models import Thread, Post

    note_id = obj.get("id", "")
    if not note_id:
        log_entry.status = "rejected"
        log_entry.error = "Reply Note has no id"
        log_entry.save(update_fields=["status", "error"])
        return

    # Deduplicate
    if Post.objects.filter(remote_ap_id=note_id).exists():
        log_entry.status = "rejected"
        log_entry.error = f"Duplicate reply Note id: {note_id}"
        log_entry.save(update_fields=["status", "error"])
        return

    in_reply_to = obj.get("inReplyTo", "")
    if not in_reply_to:
        log_entry.status = "rejected"
        log_entry.error = "inReplyTo is empty"
        log_entry.save(update_fields=["status", "error"])
        return

    # Resolve the parent thread
    thread = _resolve_parent_thread(in_reply_to)
    if thread is None:
        log_entry.status = "rejected"
        log_entry.error = f"Parent thread not found for inReplyTo: {in_reply_to}"
        log_entry.save(update_fields=["status", "error"])
        return

    # Resolve or create stub user for the remote author.
    # See the matching comment in handle_create_note — anonymous replies are
    # attributed to the board's Group actor, not a Person, and facechan:anonymous
    # is how the origin server signals that.
    attributed_to = obj.get("attributedTo", "")
    if isinstance(attributed_to, list):
        attributed_to = next(
            (a for a in attributed_to if isinstance(a, str) and "users" in a),
            attributed_to[0] if attributed_to else ""
        )
    if obj.get('facechan:anonymous'):
        remote_author = None
    else:
        remote_author = _get_or_create_stub_user(attributed_to, remote_instance)

    body = obj.get("content", "")
    if not body:
        log_entry.status = "rejected"
        log_entry.error = "Reply Note has no content"
        log_entry.save(update_fields=["status", "error"])
        return

    body = _strip_html(body)

    try:
        post = Post.objects.create(
            thread=thread,
            author=remote_author,
            body=body,
            is_remote=True,
            remote_ap_id=note_id,
            remote_actor_url=attributed_to or "",
            # See the matching comment in handle_create_note above —
            # stored exactly as received, no append at receive time.
            relay_hop_count=obj.get('facechan:relayHopCount', 0),
            relay_seen_instances=obj.get('facechan:relaySeenInstances', []),
        )
    except Exception as e:
        log_entry.status = "failed"
        log_entry.error = f"Post creation failed: {e}"
        log_entry.save(update_fields=["status", "error"])
        logger.exception("Failed to create remote reply from %s", note_id)
        return

    log_entry.status = "delivered"
    log_entry.save(update_fields=["status"])
    logger.info("Created remote reply %s in thread %s", post.pk, thread.pk)

    # Bump reply_count. Unlike last_reply_at (handled by the core.Post
    # post_save signal, which fires regardless of creation path),
    # reply_count is only ever incremented directly inside core/views.py's
    # reply-creation code — never via a signal. Federated replies go
    # through Post.objects.create() here instead, bypassing that entirely.
    # Without this, federated replies silently never count towards unread
    # totals: not just a missing WebSocket push, but broken even for the
    # 60s polling fallback, since that reads this same field.
    from django.db.models import F
    Thread.objects.filter(pk=thread.pk).update(reply_count=F('reply_count') + 1)

    # Fan out to watchers — same shape as PostViewSet.perform_create's
    # equivalent block for same-site replies, so federated replies show
    # up in the feed and push a live bell update too, not just a silent
    # reply_count bump.
    from core.models import WatchedThread, FeedItem
    watchers = WatchedThread.objects.filter(thread=thread).select_related('user')
    if remote_author is not None:
        watchers = watchers.exclude(user=remote_author)
    FeedItem.objects.bulk_create([
        FeedItem(user=w.user, thread=thread, post=post, reason='thread_reply')
        for w in watchers
    ], ignore_conflicts=True)

    channel_layer = get_channel_layer()
    if channel_layer is not None:
        for w in watchers:
            async_to_sync(channel_layer.group_send)(
                f"notifications_{w.user.id}",
                {
                    "type": "send.notification",
                    "unread": w.unread_count,
                    "thread_id": str(thread.id),
                    "thread_title": thread.title,
                    "post_id": str(post.id),
                }
            )


def _resolve_parent_thread(in_reply_to):
    """
    Resolve an inReplyTo URL to a local Thread.

    Tries two strategies:
    1. Match Thread.remote_ap_id — for threads that originated remotely
    2. Extract a UUID from the URL path and match Thread.pk — for local threads

    Returns a Thread instance or None.
    """
    import uuid as uuid_mod
    from core.models import Thread

    if not in_reply_to:
        return None

    # Strategy 1: remote thread we received earlier
    try:
        return Thread.objects.get(remote_ap_id=in_reply_to)
    except Thread.DoesNotExist:
        pass

    # Strategy 2: local thread — URL pattern is /ap/objects/threads/<uuid>
    path = urlparse(in_reply_to).path
    parts = [p for p in path.split("/") if p]
    # Expect [..., "threads", "<uuid>"]
    try:
        threads_idx = parts.index("threads")
        raw_id = parts[threads_idx + 1]
        thread_uuid = uuid_mod.UUID(raw_id)
        return Thread.objects.get(pk=thread_uuid)
    except (ValueError, IndexError, Thread.DoesNotExist):
        pass

    return None


def _resolve_local_board(remote_board_url, remote_instance):
    """
    Extract the remote board slug from the Actor URL and look up the
    local board via RemoteBoardMapping.

    Returns a Board instance or None if no mapping exists.
    """
    if not remote_board_url:
        return None

    # Extract slug from URL: http://other.tld/ap/boards/Pols → Pols
    path = urlparse(remote_board_url).path
    parts = [p for p in path.split('/') if p]
    # Expect [..., 'boards', '<slug>']
    try:
        boards_idx = parts.index('boards')
        remote_slug = parts[boards_idx + 1]
    except (ValueError, IndexError):
        logger.warning('Could not extract board slug from: %s', remote_board_url)
        return None

    try:
        mapping = RemoteBoardMapping.objects.select_related('local_board').get(
            instance=remote_instance,
            remote_slug=remote_slug,
        )
        return mapping.local_board
    except RemoteBoardMapping.DoesNotExist:
        return None


def _get_or_create_stub_user(actor_url, remote_instance):
    """
    Return a local stub User for a remote ActivityPub Person actor.
    Creates one if it doesn't exist yet.

    Stub users:
    - Have is_remote=True
    - Cannot log in (unusable password)
    - Username is derived from their AP handle: username@domain
    - remote_actor_url is their canonical AP URL (unique constraint)

    Returns None if actor_url is empty or fetch fails.
    """
    from core.models import User

    if not actor_url:
        return None

    # Check cache first
    try:
        return User.objects.get(remote_actor_url=actor_url)
    except User.DoesNotExist:
        pass

    # Try to fetch their Actor document for display name / username
    username = None
    display_name = ''
    try:
        from federation.fetch import fetch_remote_actor
        data = fetch_remote_actor(actor_url)
        actor_type = data.get('type', 'Person')
        if actor_type != 'Person':
            # Boards/relays federate as Group actors. A caller should not be
            # asking us to attribute a post to one of these — callers are
            # expected to check facechan:anonymous first — but guard here too
            # in case a non-FaceChan sender hands us a Group actor URL without
            # that flag. Refusing to create a "Person" stub from it prevents a
            # post ending up attributed to a board/instance name.
            logger.warning(
                'Refusing to create stub user from non-Person actor (%s): %s',
                actor_type, actor_url,
            )
            return None
        preferred = data.get('preferredUsername', '')
        domain = urlparse(actor_url).netloc
        username = f'{preferred}@{domain}' if preferred else None
        display_name = data.get('name', '') or preferred
    except Exception as e:
        logger.warning('Could not fetch remote actor %s: %s', actor_url, e)

    if not username:
        domain = urlparse(actor_url).netloc
        path_parts = [p for p in urlparse(actor_url).path.split('/') if p]
        username = f'{path_parts[-1]}@{domain}' if path_parts else f'remote@{domain}'

    # Ensure username uniqueness
    base_username = username[:148]  # leave room for suffix
    final_username = base_username
    suffix = 1
    while User.objects.filter(username=final_username).exists():
        final_username = f'{base_username}_{suffix}'
        suffix += 1

    user = User.objects.create(
        username=final_username,
        display_name=display_name[:150],
        is_remote=True,
        remote_actor_url=actor_url,
        is_active=False,  # cannot log in
    )
    user.set_unusable_password()
    user.save(update_fields=['password'])

    return user


def _push_thread_to_board(thread, board):
    """
    Push a new thread event to the board's WebSocket channel group.
    Anyone currently viewing the board gets the new thread without refresh.
    """
    try:
        channel_layer = get_channel_layer()
        if channel_layer is None:
            return

        thread_data = {
            'id': str(thread.pk),
            'title': thread.title,
            'body': thread.body[:300],
            'board_slug': board.slug,
            'author': thread.author.username if thread.author else 'anon',
            'is_remote': True,
            'reply_count': 0,
            'created_at': thread.created_at.isoformat(),
        }

        async_to_sync(channel_layer.group_send)(
            f'board_{board.slug}',
            {
                'type': 'new.thread',
                'thread': thread_data,
            }
        )
    except Exception as e:
        # Never let WebSocket push failure affect the inbound handling
        logger.warning('WebSocket push failed for board %s: %s', board.slug, e)


def _strip_html(text):
    """
    Minimal HTML stripping for remote content.
    Removes tags, decodes common entities. Not a full sanitiser —
    content is stored as plain text and re-escaped on output.
    """
    import re
    import html
    text = re.sub(r'<br\s*/?>', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'<p>', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'</p>', '', text, flags=re.IGNORECASE)
    text = re.sub(r'<[^>]+>', '', text)
    text = html.unescape(text)
    return text.strip()


def _truncate(text, length):
    return text[:length] + '…' if len(text) > length else text
