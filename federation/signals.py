"""
federation/signals.py

Signals that trigger federation delivery:
  - RemoteInstance approved → fetch remote board list
  - Thread created (local, non-remote) → deliver Create(Note) to followers
  - Post created (local, non-remote) → deliver Create(Note) reply to followers
    and the thread's origin server
"""

from django.db.models.signals import post_save
from django.dispatch import receiver

from federation.models import RemoteInstance


@receiver(post_save, sender=RemoteInstance)
def on_instance_status_change(sender, instance, created, **kwargs):
    """
    When a RemoteInstance is approved, queue a task to fetch their
    board list from /ap/instance so the operator can set up mappings.
    """
    if instance.status == 'approved':
        from federation.tasks import fetch_instance_boards
        fetch_instance_boards.delay(str(instance.pk))


@receiver(post_save, sender='core.Thread')
def on_thread_created(sender, instance, created, **kwargs):
    """
    When a thread is created, either deliver it (if it originated here) or
    relay it onward (if it arrived from another instance and relay
    federation is enabled).

    Guards (origin delivery, is_remote=False):
    - created=True only (no re-delivery on edits)
    - author is not None (anonymous threads don't federate)
    - Board and site federation flags checked inside deliver_create_thread

    Guards (relay, is_remote=True):
    - created=True only
    - SiteSettings.relay_federation_enabled must be on — see
      relay_create_thread for the rest (hop limit, seen-instances, etc.)
    """
    if not created:
        return

    from core.models import SiteSettings
    from federation.models import Actor
    from federation.utils import is_federation_configured

    if not is_federation_configured():
        return

    settings = SiteSettings.get()
    if not settings.federation_enabled:
        return

    if instance.is_remote:
        if not settings.relay_federation_enabled:
            return
        try:
            actor = Actor.objects.get(board=instance.board)
        except Actor.DoesNotExist:
            return
        from federation.tasks import relay_create_thread
        relay_create_thread.delay(str(instance.pk), str(actor.pk))
        return

    if instance.author is None:
        return

    try:
        actor = Actor.objects.get(board=instance.board)
    except Actor.DoesNotExist:
        return

    from federation.tasks import deliver_create_thread
    deliver_create_thread.delay(str(instance.pk), str(actor.pk))


@receiver(post_save, sender='core.Post')
def on_post_created(sender, instance, created, **kwargs):
    """
    When a local reply is created on a federated board, deliver a
    Create(Note) activity (with inReplyTo) to:
      - The board inbox of the thread's origin server (remote threads)
      - All approved followers of the local board Actor

    Guards:
    - created=True only
    - is_remote=False (don't re-federate inbound replies)
    - author is not None (anonymous replies don't federate)
    - Board and site federation flags checked inside the task
    """
    if not created:
        return
    if instance.is_remote:
        return
    if instance.author is None:
        return

    from federation.models import Actor
    from federation.utils import is_federation_configured
    from core.models import SiteSettings

    if not is_federation_configured():
        return

    settings = SiteSettings.get()
    if not settings.federation_enabled:
        return

    try:
        actor = Actor.objects.get(board=instance.thread.board)
    except Actor.DoesNotExist:
        return

    from federation.tasks import deliver_create_reply
    deliver_create_reply.delay(str(instance.pk), str(actor.pk))
