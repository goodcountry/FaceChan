"""
federation/utils.py

URL helpers and ActivityPub JSON builders for FaceChan actors and objects.
All AP-facing URLs are constructed here so there's one place to change
if the URL scheme ever shifts.
"""

from django.conf import settings


# ---------------------------------------------------------------------------
# URL helpers
# ---------------------------------------------------------------------------

def base_url():
    """Canonical origin for this instance, e.g. https://facechan.example"""
    return settings.FEDERATION_BASE_URL


def is_federation_configured():
    """
    Returns True if FEDERATION_BASE_URL is set to a real public address.
    Returns False if it's still the default localhost value — in that case
    federation is effectively disabled even if SiteSettings.federation_enabled
    is True. Operators must set FEDERATION_BASE_URL to activate federation.
    """
    url = base_url()
    return bool(url and url != 'http://localhost:8000' and 'localhost' not in url)


def actor_url(actor):
    """Canonical AP URL for a local Actor."""
    if actor.board:
        return f'{base_url()}/ap/boards/{actor.board.slug}'
    if actor.user:
        return f'{base_url()}/ap/users/{actor.user.username}'
    raise ValueError(f'Actor {actor.pk} has neither board nor user')


def board_actor_url(board_slug):
    return f'{base_url()}/ap/boards/{board_slug}'


def user_actor_url(username):
    return f'{base_url()}/ap/users/{username}'


def board_inbox_url(board_slug):
    return f'{base_url()}/ap/boards/{board_slug}/inbox'


def board_outbox_url(board_slug):
    return f'{base_url()}/ap/boards/{board_slug}/outbox'


def board_followers_url(board_slug):
    return f'{base_url()}/ap/boards/{board_slug}/followers'


def thread_object_url(thread_id):
    return f'{base_url()}/ap/objects/threads/{thread_id}'


def post_object_url(post_id):
    return f'{base_url()}/ap/objects/posts/{post_id}'


def webfinger_url():
    return f'{base_url()}/.well-known/webfinger'


# ---------------------------------------------------------------------------
# ActivityPub JSON builders
# ---------------------------------------------------------------------------

AP_CONTEXT = [
    'https://www.w3.org/ns/activitystreams',
    'https://w3id.org/security/v1',
]


def build_board_actor(board, actor):
    """
    Render a Board as an ActivityPub Group Actor JSON-LD object.
    This is what remote servers fetch when they want to know about a board.
    """
    slug = board.slug
    ap_id = board_actor_url(slug)
    return {
        '@context': AP_CONTEXT,
        'id': ap_id,
        'type': 'Group',
        'name': board.name,
        'summary': board.description,
        'preferredUsername': slug,
        'url': f'{base_url()}/boards/{slug}',
        'inbox': board_inbox_url(slug),
        'outbox': board_outbox_url(slug),
        'followers': board_followers_url(slug),
        'publicKey': {
            'id': actor.key_id,
            'owner': ap_id,
            'publicKeyPem': actor.public_key_pem,
        },
        # FaceChan extension: hint to remote instances that this is a board
        'facechan:boardSlug': slug,
        'facechan:nsfw': board.nsfw,
    }


def build_user_actor(user, actor):
    """
    Render a pseudonymous User as an ActivityPub Person Actor.
    No real-identity fields are included — username only.
    """
    ap_id = user_actor_url(user.username)
    return {
        '@context': AP_CONTEXT,
        'id': ap_id,
        'type': 'Person',
        'preferredUsername': user.username,
        'name': user.display_name or user.username,
        'url': f'{base_url()}/users/{user.username}',
        'inbox': f'{ap_id}/inbox',
        'outbox': f'{ap_id}/outbox',
        'publicKey': {
            'id': actor.key_id,
            'owner': ap_id,
            'publicKeyPem': actor.public_key_pem,
        },
    }


def build_thread_note(thread):
    """
    Render a Thread as an ActivityPub Note.
    The board is the attributedTo Group; the author Person is also included
    if the thread has an account-holder author.
    """
    board = thread.board
    attributed = [board_actor_url(board.slug)]
    if thread.author and hasattr(thread.author, 'ap_actor'):
        attributed.append(user_actor_url(thread.author.username))

    obj = {
        '@context': AP_CONTEXT,
        'id': thread_object_url(thread.id),
        'type': 'Note',
        'name': thread.title,
        'content': thread.body,
        'attributedTo': attributed[0] if len(attributed) == 1 else attributed,
        'to': ['https://www.w3.org/ns/activitystreams#Public'],
        'cc': [board_followers_url(board.slug)],
        'context': board_actor_url(board.slug),
        'published': thread.created_at.isoformat(),
        'url': f'{base_url()}/boards/{board.slug}/threads/{thread.id}',
    }
    # Anonymous threads have no author Actor — remote servers must handle this
    if not thread.author:
        obj['facechan:anonymous'] = True

    return obj


def build_reply_note(post):
    """
    Render a Post (reply) as an ActivityPub Note with inReplyTo.

    inReplyTo points at the canonical AP URL of the parent thread:
    - Local thread  → thread_object_url(thread.id)
    - Remote thread → thread.remote_ap_id (the origin server's URL)

    No 'name' field — replies are body-only, unlike thread OP Notes.
    """
    thread = post.thread
    board = thread.board

    # Canonical URL of the parent thread on its origin server
    if thread.remote_ap_id:
        in_reply_to = thread.remote_ap_id
    else:
        in_reply_to = thread_object_url(thread.id)

    attributed = board_actor_url(board.slug)
    if post.author and hasattr(post.author, 'ap_actor'):
        attributed = [attributed, user_actor_url(post.author.username)]

    obj = {
        '@context': AP_CONTEXT,
        'id': post_object_url(post.id),
        'type': 'Note',
        'content': post.body,
        'inReplyTo': in_reply_to,
        'attributedTo': attributed,
        'to': ['https://www.w3.org/ns/activitystreams#Public'],
        'cc': [board_followers_url(board.slug)],
        'context': board_actor_url(board.slug),
        'published': post.created_at.isoformat(),
        'url': f'{base_url()}/boards/{board.slug}/threads/{thread.id}',
    }

    if not post.author:
        obj['facechan:anonymous'] = True

    return obj


def build_create_activity(actor, obj):
    """Wrap an object in a Create activity."""
    return {
        '@context': AP_CONTEXT,
        'id': f'{obj["id"]}#create',
        'type': 'Create',
        'actor': actor.ap_id,
        'to': obj.get('to', []),
        'cc': obj.get('cc', []),
        'object': obj,
    }


def build_follow_activity(local_actor, remote_object_url):
    """
    Build an outbound Follow activity.

    local_actor       — our own board Actor doing the following.
    remote_object_url — the AP actor URL of the remote board we want to follow.

    Sent when an operator maps a remote board to a local board: we follow the
    remote board so its instance starts delivering that board's threads to us.
    """
    return {
        '@context': AP_CONTEXT,
        'id': f'{local_actor.ap_id}#follow-{uuid_fragment()}',
        'type': 'Follow',
        'actor': local_actor.ap_id,
        'object': remote_object_url,
    }


def build_accept_activity(local_actor, follow_activity_id, remote_actor_id):
    """Accept a Follow activity."""
    return {
        '@context': AP_CONTEXT,
        'id': f'{local_actor.ap_id}#accept-{uuid_fragment()}',
        'type': 'Accept',
        'actor': local_actor.ap_id,
        'object': {
            'type': 'Follow',
            'id': follow_activity_id,
            'actor': remote_actor_id,
            'object': local_actor.ap_id,
        },
    }


def uuid_fragment():
    import uuid
    return str(uuid.uuid4())[:8]
