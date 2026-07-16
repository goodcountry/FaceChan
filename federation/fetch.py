"""
federation/fetch.py

Fetches remote ActivityPub Actor documents and delivers outbound activities.

Transport routing
-----------------
Onion (.onion) destinations are routed through a Tor SOCKS proxy so the
hidden-service network is reachable; clearnet destinations go direct. This
is decided per-URL by _client_for(), so clearnet, onion-only, and dual-stack
deployments all work without per-call special-casing.

The SOCKS proxy URL uses the socks5h:// scheme — the trailing 'h' makes the
proxy (Tor) perform DNS resolution, which is REQUIRED for .onion names since
the local resolver cannot resolve them.
"""

import logging
from urllib.parse import urlparse

import httpx
from django.conf import settings

from federation.models import RemoteActor, RemoteInstance

logger = logging.getLogger(__name__)

AP_HEADERS = {
    'Accept': 'application/activity+json, application/ld+json',
}

# Clearnet requests resolve fast; onion circuits need time to build.
TIMEOUT_CLEARNET = 10  # seconds
TIMEOUT_ONION = 30     # seconds


def _is_onion(url):
    """True if the URL's host ends in .onion."""
    try:
        host = urlparse(url).hostname or ''
    except Exception:
        return False
    return host.endswith('.onion')


def _socks_proxy():
    """
    Return the configured Tor SOCKS proxy URL, or None if unset/empty.

    Defaults to socks5h://tor-proxy:9150 (the dedicated outbound Tor
    container on the internal Docker network). Override via the
    FEDERATION_SOCKS_PROXY env var / Django setting.
    """
    return getattr(settings, 'FEDERATION_SOCKS_PROXY', '') or None


def _client_for(url):
    """
    Build an httpx.Client appropriate for the destination URL.

    - .onion  → routed through the Tor SOCKS proxy, longer timeout.
                Raises RuntimeError if no proxy is configured, so callers
                fail loudly rather than silently attempting (and hanging on)
                a direct connection to an unreachable onion host.
    - other   → direct connection, standard timeout.

    httpx SOCKS support requires the 'socksio' package (httpx[socks]).
    """
    if _is_onion(url):
        proxy = _socks_proxy()
        if not proxy:
            raise RuntimeError(
                f'Onion destination {url!r} requires a Tor SOCKS proxy, but '
                f'FEDERATION_SOCKS_PROXY is not configured.'
            )
        return httpx.Client(timeout=TIMEOUT_ONION, proxy=proxy, follow_redirects=True)
    return httpx.Client(timeout=TIMEOUT_CLEARNET, follow_redirects=True)


def fetch_remote_actor(actor_url):
    """
    Fetch and return the raw JSON of a remote Actor.
    Raises httpx.HTTPError on network/HTTP failure.
    """
    with _client_for(actor_url) as client:
        response = client.get(actor_url, headers=AP_HEADERS)
        response.raise_for_status()
        return response.json()


def fetch_remote_actor_key(actor_id):
    """
    Return the public key PEM for a remote Actor.
    Checks the RemoteActor cache first; fetches if not found.
    """
    try:
        remote = RemoteActor.objects.get(ap_id=actor_id)
        return remote.public_key_pem
    except RemoteActor.DoesNotExist:
        pass

    # Fetch fresh
    data = fetch_remote_actor(actor_id)
    pub_key = data.get('publicKey', {})
    pem = pub_key.get('publicKeyPem', '')
    if not pem:
        raise ValueError(f'No publicKeyPem in actor document: {actor_id}')
    return pem


def fetch_and_cache_remote_actor(actor_id, remote_instance):
    """
    Fetch a remote Actor, cache it as RemoteActor, and return the instance.
    Returns None if the fetch fails.
    """
    try:
        data = fetch_remote_actor(actor_id)
    except Exception as e:
        logger.warning('Failed to fetch remote actor %s: %s', actor_id, e)
        return None

    pub_key = data.get('publicKey', {})
    pem = pub_key.get('publicKeyPem', '')
    key_id = pub_key.get('id', actor_id + '#main-key')

    inbox = data.get('inbox', '')
    if not inbox:
        logger.warning('Remote actor %s has no inbox', actor_id)
        return None

    remote_actor, _ = RemoteActor.objects.update_or_create(
        ap_id=actor_id,
        defaults={
            'instance': remote_instance,
            'actor_type': data.get('type', 'Person'),
            'username': data.get('preferredUsername', ''),
            'display_name': data.get('name', ''),
            'inbox_url': inbox,
            'public_key_pem': pem,
            'key_id': key_id,
            'raw_json': data,
        }
    )
    return remote_actor


def deliver_activity(payload, inbox_url, actor):
    """
    HTTP POST an ActivityPub activity to a remote inbox, signed.
    Returns (success: bool, status_code: int | None, error: str | None).
    """
    import json
    from federation.signatures import sign_request

    body = json.dumps(payload).encode()
    headers = sign_request('POST', inbox_url, body, actor)
    headers['Content-Type'] = 'application/activity+json'

    try:
        with _client_for(inbox_url) as client:
            response = client.post(inbox_url, content=body, headers=headers)
            if response.status_code in (200, 201, 202):
                return True, response.status_code, None
            else:
                return False, response.status_code, response.text[:500]
    except (httpx.HTTPError, RuntimeError) as e:
        return False, None, str(e)


def fetch_instance_board_list(base_url):
    """
    Fetch the /ap/instance discovery document from a remote FaceChan instance
    and return its parsed 'boards' list.

    base_url is the instance root, e.g. http://abc123.onion or
    https://example.tld — the /ap/instance path is appended here.

    Routes through Tor automatically for .onion instances. Raises
    httpx.HTTPError on network/HTTP failure, ValueError on a malformed
    response.
    """
    url = base_url.rstrip('/') + '/ap/instance'
    with _client_for(url) as client:
        response = client.get(url, headers=AP_HEADERS)
        response.raise_for_status()
        data = response.json()

    if not isinstance(data, dict) or 'boards' not in data:
        raise ValueError(f'No board list in /ap/instance response from {base_url}')

    boards = data.get('boards', [])
    if not isinstance(boards, list):
        raise ValueError(f'Malformed board list from {base_url}')
    return boards
