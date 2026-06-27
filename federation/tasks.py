"""
federation/tasks.py

Celery tasks for async ActivityPub delivery.

All network I/O happens here — views just queue tasks and return 202
immediately. This keeps inbox response times fast and makes delivery
retryable.
"""

import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=5, default_retry_delay=60)
def deliver_accept(self, local_actor_pk, follow_activity_id, remote_actor_id, inbox_url):
    """
    Send an Accept(Follow) activity to the remote actor's inbox.
    Retries up to 5 times with 60s delay on failure.
    """
    from federation.models import Actor, FederationActivity
    from federation.fetch import deliver_activity
    from federation.utils import build_accept_activity

    try:
        actor = Actor.objects.get(pk=local_actor_pk)
    except Actor.DoesNotExist:
        logger.error('deliver_accept: Actor %s not found', local_actor_pk)
        return

    payload = build_accept_activity(actor, follow_activity_id, remote_actor_id)

    log = FederationActivity.objects.create(
        direction='out',
        activity_type='Accept',
        activity_id=payload.get('id', ''),
        local_actor=actor,
        payload=payload,
        status='queued',
    )

    success, status_code, error = deliver_activity(payload, inbox_url, actor)

    if success:
        log.status = 'delivered'
        log.save(update_fields=['status'])
        logger.info('Delivered Accept to %s', inbox_url)
    else:
        log.status = 'failed'
        log.error = error or f'HTTP {status_code}'
        log.save(update_fields=['status', 'error'])
        logger.warning('Failed to deliver Accept to %s: %s', inbox_url, error)
        raise self.retry(exc=Exception(error))


@shared_task(bind=True, max_retries=5, default_retry_delay=60)
def deliver_follow(self, local_actor_pk, remote_board_pk):
    """
    Send a Follow activity from one of our local board Actors to a remote
    board, so the remote instance begins delivering that board's threads to us.

    Fired when an operator maps a remote board to a local board. The remote
    instance auto-accepts (see _handle_follow) and adds us as a follower.

    local_actor_pk  — Actor PK of our local board (the follower).
    remote_board_pk — RemoteBoard PK of the board we want to follow.
    """
    from federation.models import Actor, RemoteBoard, FederationActivity
    from federation.fetch import deliver_activity
    from federation.utils import build_follow_activity

    try:
        actor = Actor.objects.get(pk=local_actor_pk)
    except Actor.DoesNotExist:
        logger.error('deliver_follow: Actor %s not found', local_actor_pk)
        return

    try:
        remote_board = RemoteBoard.objects.get(pk=remote_board_pk)
    except RemoteBoard.DoesNotExist:
        logger.error('deliver_follow: RemoteBoard %s not found', remote_board_pk)
        return

    if not remote_board.actor_url or not remote_board.inbox_url:
        logger.warning(
            'deliver_follow: remote board %s missing actor_url/inbox_url; '
            'cannot follow', remote_board
        )
        return

    payload = build_follow_activity(actor, remote_board.actor_url)

    log = FederationActivity.objects.create(
        direction='out',
        activity_type='Follow',
        activity_id=payload.get('id', ''),
        local_actor=actor,
        payload=payload,
        status='queued',
    )

    success, status_code, error = deliver_activity(payload, remote_board.inbox_url, actor)

    if success:
        log.status = 'delivered'
        log.save(update_fields=['status'])
        logger.info('Delivered Follow to %s', remote_board.inbox_url)
    else:
        log.status = 'failed'
        log.error = error or f'HTTP {status_code}'
        log.save(update_fields=['status', 'error'])
        logger.warning('Failed to deliver Follow to %s: %s', remote_board.inbox_url, error)
        raise self.retry(exc=Exception(error))


@shared_task(bind=True, max_retries=5, default_retry_delay=60)
def deliver_create_thread(self, thread_id, local_actor_pk):
    """
    Deliver a Create(Note) activity for a new thread to all approved followers.
    Called when a new thread is created on a federated board.
    """
    from core.models import Thread
    from federation.models import Actor, Follow, FederationActivity
    from federation.fetch import deliver_activity
    from federation.utils import build_thread_note, build_create_activity

    try:
        thread = Thread.objects.select_related('board', 'author').get(pk=thread_id)
        actor = Actor.objects.get(pk=local_actor_pk)
    except (Thread.DoesNotExist, Actor.DoesNotExist) as e:
        logger.error('deliver_create_thread: %s', e)
        return

    # Respect master switch and per-board flag
    from core.models import SiteSettings
    from federation.utils import is_federation_configured
    settings = SiteSettings.get()
    if not settings.federation_enabled:
        return
    if not is_federation_configured():
        return
    if not thread.board.allow_federation:
        return

    # Anonymous threads don't federate
    if thread.author is None:
        return

    note = build_thread_note(thread)
    activity = build_create_activity(actor, note)

    followers = Follow.objects.filter(
        local_actor=actor, accepted=True
    ).select_related('remote_actor')

    for follow in followers:
        inbox_url = follow.remote_actor.inbox_url
        log = FederationActivity.objects.create(
            direction='out',
            activity_type='Create',
            activity_id=activity.get('id', ''),
            local_actor=actor,
            remote_instance=follow.remote_actor.instance,
            payload=activity,
            status='queued',
        )

        success, status_code, error = deliver_activity(activity, inbox_url, actor)

        if success:
            log.status = 'delivered'
            log.save(update_fields=['status'])
        else:
            log.status = 'failed'
            log.error = error or f'HTTP {status_code}'
            log.save(update_fields=['status', 'error'])
            logger.warning('Failed to deliver Create to %s: %s', inbox_url, error)


@shared_task(bind=True, max_retries=5, default_retry_delay=60)
def deliver_create_reply(self, post_id, local_actor_pk):
    """
    Deliver a Create(Note) activity for a reply to:
      1. The board inbox of the thread's origin server (if the thread is remote)
      2. All approved followers of the local board Actor

    Called when a local user posts a reply on a federated board.
    Anonymous replies are not federated (no AP actor to attribute to).
    """
    from core.models import Post, SiteSettings
    from federation.models import Actor, Follow, FederationActivity
    from federation.fetch import deliver_activity
    from federation.utils import build_reply_note, build_create_activity, is_federation_configured

    try:
        post = Post.objects.select_related('thread__board', 'author').get(pk=post_id)
        actor = Actor.objects.get(pk=local_actor_pk)
    except (Post.DoesNotExist, Actor.DoesNotExist) as e:
        logger.error('deliver_create_reply: %s', e)
        return

    settings = SiteSettings.get()
    if not settings.federation_enabled:
        return
    if not is_federation_configured():
        return
    if not post.thread.board.allow_federation:
        return
    if post.author is None:
        return

    note = build_reply_note(post)
    activity = build_create_activity(actor, note)

    # Collect inboxes to deliver to — deduplicated
    inbox_urls = set()

    # 1. Thread origin server board inbox (remote threads only)
    thread = post.thread
    if thread.is_remote and thread.remote_ap_id:
        # Derive the board inbox from the RemoteBoard record if we have it
        from federation.models import RemoteBoard
        remote_board = RemoteBoard.objects.filter(
            actor_url__isnull=False
        ).filter(
            instance__status='approved'
        ).first()
        # More reliable: look up via RemoteBoardMapping for this board
        from federation.models import RemoteBoardMapping
        mapping = RemoteBoardMapping.objects.select_related('instance').filter(
            local_board=thread.board
        ).first()
        if mapping:
            rb = RemoteBoard.objects.filter(
                instance=mapping.instance,
                remote_slug=mapping.remote_slug,
            ).first()
            if rb and rb.inbox_url:
                inbox_urls.add(rb.inbox_url)

    # 2. All approved followers of this board's Actor
    followers = Follow.objects.filter(
        local_actor=actor, accepted=True
    ).select_related('remote_actor')
    for follow in followers:
        inbox_urls.add(follow.remote_actor.inbox_url)

    if not inbox_urls:
        logger.debug('deliver_create_reply: no inboxes to deliver to for post %s', post_id)
        return

    for inbox_url in inbox_urls:
        log = FederationActivity.objects.create(
            direction='out',
            activity_type='Create',
            activity_id=activity.get('id', ''),
            local_actor=actor,
            payload=activity,
            status='queued',
        )

        success, status_code, error = deliver_activity(activity, inbox_url, actor)

        if success:
            log.status = 'delivered'
            log.save(update_fields=['status'])
            logger.info('Delivered reply Create to %s', inbox_url)
        else:
            log.status = 'failed'
            log.error = error or f'HTTP {status_code}'
            log.save(update_fields=['status', 'error'])
            logger.warning('Failed to deliver reply Create to %s: %s', inbox_url, error)



    """
    Fetch the board list from a remote FaceChan instance's /ap/instance
    endpoint and cache the results as RemoteBoard records.

    Called automatically when a RemoteInstance is approved.
    """
    import httpx
    from federation.models import RemoteInstance, RemoteBoard

    try:
        instance = RemoteInstance.objects.get(pk=instance_pk)
    except RemoteInstance.DoesNotExist:
        return

    url = f'https://{instance.domain}/ap/instance'
    # Try https first, fall back to http (onion instances)
    try:
        with httpx.Client(timeout=15, follow_redirects=True) as client:
            resp = client.get(url, headers={'Accept': 'application/json'})
            resp.raise_for_status()
            data = resp.json()
    except Exception:
        url = f'http://{instance.domain}/ap/instance'
        try:
            with httpx.Client(timeout=15, follow_redirects=True) as client:
                resp = client.get(url, headers={'Accept': 'application/json'})
                resp.raise_for_status()
                data = resp.json()
        except Exception as e:
            raise self.retry(exc=e)

    # Validate it's a FaceChan instance
    if data.get('software') != 'facechan':
        instance.notes = (instance.notes or '') + '\nWarning: remote instance is not FaceChan software.'
        instance.save(update_fields=['notes'])
        return

    boards = data.get('boards', [])
    for board_data in boards:
        slug = board_data.get('slug', '')
        if not slug:
            continue
        RemoteBoard.objects.update_or_create(
            instance=instance,
            remote_slug=slug,
            defaults={
                'name': board_data.get('name', slug),
                'description': board_data.get('description', ''),
                'nsfw': board_data.get('nsfw', False),
                'actor_url': board_data.get('actor_url', ''),
                'inbox_url': board_data.get('inbox_url', ''),
            }
        )

    # Remove stale boards no longer advertised
    current_slugs = [b.get('slug') for b in boards if b.get('slug')]
    RemoteBoard.objects.filter(instance=instance).exclude(
        remote_slug__in=current_slugs
    ).delete()


@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def fetch_instance_boards(self, instance_pk):
    """
    Fetch the remote instance's board list from its /ap/instance endpoint
    and upsert RemoteBoard rows, so the operator can map remote boards to
    local boards via the dashboard dropdown.

    Fires automatically when an instance is approved (post_save signal) and
    on demand via the dashboard "Refresh boards" button.

    Routes through Tor automatically for .onion instances (see
    federation.fetch._client_for). Retries on transient network failure.
    """
    from federation.models import RemoteInstance, RemoteBoard
    from federation.fetch import fetch_instance_board_list

    try:
        instance = RemoteInstance.objects.get(pk=instance_pk)
    except RemoteInstance.DoesNotExist:
        logger.error('fetch_instance_boards: instance %s not found', instance_pk)
        return

    # Derive the base URL from the stored domain. Domains are stored without
    # scheme; onion instances are http, clearnet https.
    domain = instance.domain.strip().rstrip('/')
    scheme = 'http' if domain.endswith('.onion') else 'https'
    base_url = f'{scheme}://{domain}'

    try:
        boards = fetch_instance_board_list(base_url)
    except Exception as e:
        logger.warning(
            'fetch_instance_boards: failed to fetch %s board list: %s',
            instance.domain, e
        )
        # Retry transient failures (onion circuit not yet built, etc.)
        raise self.retry(exc=e)

    seen_slugs = []
    for board in boards:
        slug = (board.get('slug') or '').strip()
        if not slug:
            continue
        seen_slugs.append(slug)
        RemoteBoard.objects.update_or_create(
            instance=instance,
            remote_slug=slug,
            defaults={
                'name': board.get('name', '')[:100],
                'description': board.get('description', ''),
                'nsfw': bool(board.get('nsfw', False)),
                'actor_url': board.get('actor_url', ''),
                'inbox_url': board.get('inbox_url', ''),
            },
        )

    # Prune boards that no longer exist on the remote instance.
    removed, _ = RemoteBoard.objects.filter(
        instance=instance
    ).exclude(remote_slug__in=seen_slugs).delete()

    logger.info(
        'fetch_instance_boards: %s — upserted %d board(s), pruned %d',
        instance.domain, len(seen_slugs), removed
    )
