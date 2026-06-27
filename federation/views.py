"""
federation/views.py

ActivityPub endpoints:
  /.well-known/webfinger          — Actor discovery
  /ap/boards/<slug>               — Board Group Actor
  /ap/boards/<slug>/inbox         — Receive inbound activities
  /ap/boards/<slug>/outbox        — Published threads
  /ap/boards/<slug>/followers     — Follower collection
  /ap/users/<username>            — User Person Actor
"""

import json
import logging

from django.http import JsonResponse, HttpResponse
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.shortcuts import get_object_or_404

from core.models import Board, User
from federation.models import Actor, RemoteInstance, RemoteActor, Follow, FederationActivity
from federation.utils import (
    build_board_actor, build_user_actor, build_thread_note,
    build_accept_activity, board_actor_url, board_inbox_url, base_url,
)

logger = logging.getLogger(__name__)

AP_CONTENT_TYPE = 'application/activity+json'
AP_LD_CONTENT_TYPE = 'application/ld+json; profile="https://www.w3.org/ns/activitystreams"'


def ap_response(data, status=200):
    """Return a JSON response with the correct ActivityPub content type."""
    return JsonResponse(data, status=status, content_type=AP_CONTENT_TYPE)


def _wants_ap(request):
    """True if the client is asking for ActivityPub JSON."""
    accept = request.META.get('HTTP_ACCEPT', '')
    return (
        AP_CONTENT_TYPE in accept
        or AP_LD_CONTENT_TYPE in accept
        or 'application/ld+json' in accept
    )


# ---------------------------------------------------------------------------
# Webfinger — Actor discovery
# ---------------------------------------------------------------------------

class InstanceInfoView(View):
    """
    /ap/instance  (GET, public)

    Returns instance metadata and a list of federated boards.
    Used by remote FaceChan instances during federation setup so operators
    can discover available boards without manually typing slugs.

    Only boards with allow_federation=True are included.
    Returns 503 if federation is disabled at the instance level.
    """

    def get(self, request):
        from core.models import SiteSettings, Board

        settings = SiteSettings.get()

        if not settings.federation_enabled:
            return ap_response({'error': 'federation disabled on this instance'}, status=503)

        boards = Board.objects.filter(allow_federation=True).order_by('slug')
        board_list = []
        for board in boards:
            actor_url = board_actor_url(board.slug)
            board_list.append({
                'slug': board.slug,
                'name': board.name,
                'description': board.description,
                'nsfw': board.nsfw,
                'actor_url': actor_url,
                'inbox_url': board_inbox_url(board.slug),
            })

        return JsonResponse({
            'software': 'facechan',
            'version': '1.0',
            'base_url': base_url(),
            'site_name': settings.site_name,
            'site_tagline': settings.site_tagline,
            'federation_enabled': True,
            'boards': board_list,
        })


# ---------------------------------------------------------------------------
# Webfinger — Actor discovery
# ---------------------------------------------------------------------------

class WebfingerView(View):
    """
    /.well-known/webfinger?resource=acct:boardslug@instance.tld

    Lets remote servers resolve a board or user handle to their Actor URL.
    """

    def get(self, request):
        resource = request.GET.get('resource', '')
        if not resource:
            return JsonResponse({'error': 'resource parameter required'}, status=400)

        if not resource.startswith('acct:'):
            return JsonResponse({'error': 'only acct: scheme supported'}, status=400)

        acct = resource[len('acct:'):]
        if '@' not in acct:
            return JsonResponse({'error': 'malformed acct'}, status=400)

        identifier, domain = acct.rsplit('@', 1)

        our_domain = base_url().replace('https://', '').replace('http://', '')
        if domain != our_domain:
            return JsonResponse({'error': 'not our domain'}, status=404)

        actor_url = None
        try:
            board = Board.objects.get(slug=identifier)
            actor_url = board_actor_url(board.slug)
            subject = resource
        except Board.DoesNotExist:
            try:
                user = User.objects.get(username=identifier)
                from federation.utils import user_actor_url
                actor_url = user_actor_url(user.username)
                subject = resource
            except User.DoesNotExist:
                return JsonResponse({'error': 'not found'}, status=404)

        data = {
            'subject': subject,
            'aliases': [actor_url],
            'links': [
                {
                    'rel': 'self',
                    'type': AP_CONTENT_TYPE,
                    'href': actor_url,
                }
            ],
        }
        return JsonResponse(data, content_type='application/jrd+json')



    """
    /.well-known/webfinger?resource=acct:boardslug@instance.tld

    Lets remote servers resolve a board or user handle to their Actor URL.
    """

    def get(self, request):
        resource = request.GET.get('resource', '')
        if not resource:
            return JsonResponse({'error': 'resource parameter required'}, status=400)

        # Expect acct:identifier@domain
        if not resource.startswith('acct:'):
            return JsonResponse({'error': 'only acct: scheme supported'}, status=400)

        acct = resource[len('acct:'):]
        if '@' not in acct:
            return JsonResponse({'error': 'malformed acct'}, status=400)

        identifier, domain = acct.rsplit('@', 1)

        # Verify this request is for our instance
        our_domain = base_url().replace('https://', '').replace('http://', '')
        if domain != our_domain:
            return JsonResponse({'error': 'not our domain'}, status=404)

        # Try board first, then user
        actor_url = None
        try:
            board = Board.objects.get(slug=identifier)
            actor_url = board_actor_url(board.slug)
            subject = resource
        except Board.DoesNotExist:
            try:
                user = User.objects.get(username=identifier)
                from federation.utils import user_actor_url
                actor_url = user_actor_url(user.username)
                subject = resource
            except User.DoesNotExist:
                return JsonResponse({'error': 'not found'}, status=404)

        data = {
            'subject': subject,
            'aliases': [actor_url],
            'links': [
                {
                    'rel': 'self',
                    'type': AP_CONTENT_TYPE,
                    'href': actor_url,
                }
            ],
        }
        return JsonResponse(data, content_type='application/jrd+json')


# ---------------------------------------------------------------------------
# Board Actor
# ---------------------------------------------------------------------------

class BoardActorView(View):
    """
    /ap/boards/<slug>

    Returns the Group Actor JSON for a board when Accept includes an AP
    content type. Regular browsers just get a redirect to the board page.
    """

    def get(self, request, slug):
        board = get_object_or_404(Board, slug=slug)

        if not _wants_ap(request):
            # Redirect non-AP clients (browsers) to the actual board UI
            return HttpResponse(
                status=302,
                headers={'Location': f'{base_url()}/boards/{slug}'}
            )

        actor, _ = Actor.objects.get_or_create(
            board=board,
            defaults={'actor_type': 'Group'}
        )
        return ap_response(build_board_actor(board, actor))


# ---------------------------------------------------------------------------
# Board Inbox — receives inbound activities
# ---------------------------------------------------------------------------

@method_decorator(csrf_exempt, name='dispatch')
class BoardInboxView(View):
    """
    /ap/boards/<slug>/inbox  (POST only)

    Receives Follow, Undo(Follow), Create(Note) activities from remote
    instances. Validates HTTP Signature, checks allowlist, dispatches
    to the appropriate handler.
    """

    def post(self, request, slug):
        board = get_object_or_404(Board, slug=slug)

        try:
            body = request.body
            activity = json.loads(body)
        except (json.JSONDecodeError, UnicodeDecodeError):
            return ap_response({'error': 'invalid JSON'}, status=400)

        # Respect master federation switch
        from core.models import SiteSettings
        from federation.utils import is_federation_configured
        if not SiteSettings.get().federation_enabled:
            return ap_response({'error': 'federation disabled'}, status=503)
        if not is_federation_configured():
            return ap_response({'error': 'federation not configured on this instance'}, status=503)

        activity_type = activity.get('type', '')
        actor_id = activity.get('actor', '')
        activity_id = activity.get('id', '')

        # Log all inbound activities
        log_entry = FederationActivity.objects.create(
            direction='in',
            activity_type=activity_type,
            activity_id=activity_id,
            payload=activity,
            status='queued',
        )

        # Verify the sending instance is on our allowlist
        remote_instance = _get_approved_instance_for_actor(actor_id)
        if remote_instance is None:
            log_entry.status = 'rejected'
            log_entry.error = f'Instance not approved for actor: {actor_id}'
            log_entry.save(update_fields=['status', 'error'])
            return ap_response({'error': 'instance not approved'}, status=403)

        log_entry.remote_instance = remote_instance
        log_entry.save(update_fields=['remote_instance'])

        # Verify HTTP Signature
        try:
            _verify_inbound_signature(request, body, actor_id)
        except Exception as e:
            log_entry.status = 'rejected'
            log_entry.error = f'Signature verification failed: {e}'
            log_entry.save(update_fields=['status', 'error'])
            logger.warning('Signature verification failed from %s: %s', actor_id, e)
            return ap_response({'error': 'signature invalid'}, status=401)

        # Dispatch to handler
        try:
            if activity_type == 'Follow':
                _handle_follow(board, activity, remote_instance, log_entry)
            elif activity_type == 'Undo' and isinstance(activity.get('object'), dict):
                inner = activity['object']
                if inner.get('type') == 'Follow':
                    _handle_unfollow(board, activity, remote_instance, log_entry)
            elif activity_type == 'Create':
                obj = activity.get('object', {})
                if isinstance(obj, dict) and obj.get('type') == 'Note':
                    from federation.inbound import handle_create_note
                    handle_create_note(activity, remote_instance, log_entry)
                else:
                    log_entry.status = 'delivered'
                    log_entry.error = 'Create with non-Note object — ignored'
                    log_entry.save(update_fields=['status', 'error'])
            elif activity_type == 'Accept':
                # A remote instance accepted our outbound Follow.
                # Mark the matching RemoteBoardMapping as accepted so the
                # dashboard can show follow status.
                accepted_obj = activity.get('object', {})
                # object.object is our local board actor URL
                local_actor_url = (
                    accepted_obj.get('object') if isinstance(accepted_obj, dict)
                    else accepted_obj
                )
                try:
                    from federation.models import Actor, RemoteBoardMapping
                    if local_actor_url:
                        for a in Actor.objects.filter(actor_type='Group').select_related('board'):
                            if a.ap_id == local_actor_url and a.board:
                                RemoteBoardMapping.objects.filter(
                                    local_board=a.board,
                                    instance=remote_instance,
                                ).update(follow_accepted=True)
                                break
                except Exception as accept_err:
                    log_entry.error = f'Accept: follow-state update failed: {accept_err}'
                    log_entry.save(update_fields=['error'])
                log_entry.status = 'delivered'
                log_entry.save(update_fields=['status'])
            else:
                # Unknown activity type — accepted but not acted on
                log_entry.status = 'delivered'
                log_entry.error = f'Unhandled activity type: {activity_type}'
                log_entry.save(update_fields=['status', 'error'])

        except Exception as e:
            log_entry.status = 'failed'
            log_entry.error = str(e)
            log_entry.save(update_fields=['status', 'error'])
            logger.exception('Error handling %s from %s', activity_type, actor_id)
            return ap_response({'error': 'internal error'}, status=500)

        return ap_response({'status': 'accepted'}, status=202)


# ---------------------------------------------------------------------------
# Board Outbox
# ---------------------------------------------------------------------------

class BoardOutboxView(View):
    """
    /ap/boards/<slug>/outbox

    OrderedCollection of the board's public threads as Create(Note) activities.
    Paginated — page param selects offset.
    """

    PAGE_SIZE = 20

    def get(self, request, slug):
        from federation.utils import build_create_activity, thread_object_url
        from core.models import Thread

        board = get_object_or_404(Board, slug=slug)
        actor, _ = Actor.objects.get_or_create(board=board, defaults={'actor_type': 'Group'})

        outbox_url = f'{base_url()}/ap/boards/{slug}/outbox'

        if 'page' not in request.GET:
            # Return the collection stub
            count = Thread.objects.filter(
                board=board, is_hidden=False, is_quarantined=False
            ).count()
            return ap_response({
                '@context': 'https://www.w3.org/ns/activitystreams',
                'id': outbox_url,
                'type': 'OrderedCollection',
                'totalItems': count,
                'first': f'{outbox_url}?page=1',
            })

        # Return a page of activities
        try:
            page = max(1, int(request.GET.get('page', 1)))
        except (ValueError, TypeError):
            page = 1

        offset = (page - 1) * self.PAGE_SIZE
        threads = Thread.objects.filter(
            board=board, is_hidden=False, is_quarantined=False
        ).select_related('author').order_by('-created_at')[offset:offset + self.PAGE_SIZE]

        items = []
        for thread in threads:
            # Only federate threads by account holders — anonymous threads stay local
            if thread.author is None:
                continue
            note = build_thread_note(thread)
            activity = build_create_activity(actor, note)
            items.append(activity)

        return ap_response({
            '@context': 'https://www.w3.org/ns/activitystreams',
            'id': f'{outbox_url}?page={page}',
            'type': 'OrderedCollectionPage',
            'partOf': outbox_url,
            'orderedItems': items,
        })


# ---------------------------------------------------------------------------
# Board Followers collection
# ---------------------------------------------------------------------------

class BoardFollowersView(View):
    """
    /ap/boards/<slug>/followers

    OrderedCollection of Actor URLs following this board.
    """

    def get(self, request, slug):
        board = get_object_or_404(Board, slug=slug)
        actor = get_object_or_404(Actor, board=board)

        followers_url = f'{base_url()}/ap/boards/{slug}/followers'
        follower_ids = list(
            Follow.objects.filter(local_actor=actor, accepted=True)
            .values_list('remote_actor__ap_id', flat=True)
        )

        return ap_response({
            '@context': 'https://www.w3.org/ns/activitystreams',
            'id': followers_url,
            'type': 'OrderedCollection',
            'totalItems': len(follower_ids),
            'orderedItems': follower_ids,
        })


# ---------------------------------------------------------------------------
# User Actor
# ---------------------------------------------------------------------------

class UserActorView(View):
    """
    /ap/users/<username>

    Returns the Person Actor JSON for a pseudonymous account holder.
    """

    def get(self, request, username):
        user = get_object_or_404(User, username=username)

        if not _wants_ap(request):
            return HttpResponse(
                status=302,
                headers={'Location': f'{base_url()}/users/{username}'}
            )

        actor, _ = Actor.objects.get_or_create(
            user=user,
            defaults={'actor_type': 'Person'}
        )
        return ap_response(build_user_actor(user, actor))


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _get_approved_instance_for_actor(actor_id):
    """
    Return the approved RemoteInstance for the given actor URL,
    or None if the instance is not on the allowlist.
    """
    from urllib.parse import urlparse
    try:
        domain = urlparse(actor_id).netloc
        instance = RemoteInstance.objects.get(domain=domain)
        return instance if instance.is_approved else None
    except RemoteInstance.DoesNotExist:
        # Auto-create as pending — operator must approve before activities land
        if actor_id:
            from urllib.parse import urlparse
            domain = urlparse(actor_id).netloc
            if domain:
                RemoteInstance.objects.get_or_create(
                    domain=domain,
                    defaults={'status': 'pending'}
                )
        return None


def _verify_inbound_signature(request, body_bytes, actor_id):
    """
    Fetch the remote actor's public key and verify the HTTP Signature.
    Raises VerificationError on failure.
    """
    from federation.signatures import verify_request, VerificationError
    from federation.fetch import fetch_remote_actor_key

    public_key_pem = fetch_remote_actor_key(actor_id)
    path = request.path
    if request.META.get('QUERY_STRING'):
        path = f'{path}?{request.META["QUERY_STRING"]}'

    headers = {
        key[5:].replace('_', '-').lower(): value
        for key, value in request.META.items()
        if key.startswith('HTTP_')
    }
    headers['content-type'] = request.content_type or ''

    verify_request(request.method, path, headers, body_bytes, public_key_pem)


def _handle_follow(board, activity, remote_instance, log_entry):
    """
    Process a Follow activity — auto-accept from approved instances.
    Queues an Accept activity delivery back to the remote actor.
    """
    from federation.tasks import deliver_accept

    actor_id = activity.get('actor', '')
    follow_id = activity.get('id', '')

    local_actor, _ = Actor.objects.get_or_create(
        board=board, defaults={'actor_type': 'Group'}
    )
    log_entry.local_actor = local_actor
    log_entry.save(update_fields=['local_actor'])

    # Fetch or update cached remote actor
    remote_actor = _get_or_fetch_remote_actor(actor_id, remote_instance)
    if remote_actor is None:
        raise ValueError(f'Could not resolve remote actor: {actor_id}')

    follow, created = Follow.objects.get_or_create(
        local_actor=local_actor,
        remote_actor=remote_actor,
        defaults={
            'follow_activity_id': follow_id,
            'accepted': True,
        }
    )
    if not created:
        follow.accepted = True
        follow.follow_activity_id = follow_id
        follow.save(update_fields=['accepted', 'follow_activity_id'])

    log_entry.status = 'delivered'
    log_entry.save(update_fields=['status'])

    # Async: send Accept back
    deliver_accept.delay(
        str(local_actor.pk),
        follow_id,
        actor_id,
        remote_actor.inbox_url,
    )


def _handle_unfollow(board, activity, remote_instance, log_entry):
    """Process an Undo(Follow) activity — mark the follow as removed."""
    actor_id = activity.get('actor', '')
    try:
        local_actor = Actor.objects.get(board=board)
        remote_actor = RemoteActor.objects.get(ap_id=actor_id)
        Follow.objects.filter(
            local_actor=local_actor,
            remote_actor=remote_actor,
        ).update(accepted=False)
    except (Actor.DoesNotExist, RemoteActor.DoesNotExist):
        pass

    log_entry.status = 'delivered'
    log_entry.save(update_fields=['status'])


def _get_or_fetch_remote_actor(actor_id, remote_instance):
    """Return cached RemoteActor or fetch and cache it."""
    try:
        return RemoteActor.objects.get(ap_id=actor_id)
    except RemoteActor.DoesNotExist:
        from federation.fetch import fetch_and_cache_remote_actor
        return fetch_and_cache_remote_actor(actor_id, remote_instance)
