from django.db.models.signals import post_save, pre_delete
from django.dispatch import receiver
from django.utils import timezone
import os

BOARD_THREAD_LIMIT = 100
PRIVATE_COMMUNITY_THREAD_LIMIT = 50
POST_BUMP_LIMIT = 250
POST_HARD_LIMIT = 300


def _delete_image_file(image_field):
    if image_field and image_field.name:
        try:
            path = image_field.path
            if os.path.exists(path):
                os.remove(path)
        except Exception:
            pass


def _delete_thread_images(thread):
    _delete_image_file(thread.image)
    for post in thread.posts.all():
        _delete_image_file(post.image)


def _cull_oldest_thread(queryset, protect_pk=None):
    """Delete the thread with the oldest last_reply_at from the given queryset."""
    candidate = (
        queryset
        .filter(is_pinned=False)
        .exclude(pk=protect_pk)
        .order_by('last_reply_at')
        .first()
    )
    if candidate:
        _delete_thread_images(candidate)
        candidate.delete()


@receiver(post_save, sender='core.Post')
def on_post_created(sender, instance, created, **kwargs):
    if not created:
        return

    from .models import Thread

    thread = instance.thread
    post_count = thread.posts.count()

    # Hard lock at 300
    if post_count >= POST_HARD_LIMIT:
        Thread.objects.filter(pk=thread.pk).update(is_locked=True)
        return

    # Bump or sage
    if not instance.sage and post_count < POST_BUMP_LIMIT:
        Thread.objects.filter(pk=thread.pk).update(last_reply_at=timezone.now())


@receiver(post_save, sender='core.Thread')
def on_thread_created(sender, instance, created, **kwargs):
    if not created:
        return

    community = instance.community

    if community and community.is_private:
        # Private community — own cap, no board interference
        thread_count = community.threads.count()
        if thread_count > PRIVATE_COMMUNITY_THREAD_LIMIT:
            _cull_oldest_thread(
                community.threads.all(),
                protect_pk=instance.pk
            )
    else:
        # Public thread — counts toward board cap
        board = instance.board
        thread_count = board.threads.filter(
            community__isnull=True
        ).count() + board.threads.filter(
            community__is_private=False
        ).count()

        if thread_count > BOARD_THREAD_LIMIT:
            # Only cull public threads from the board
            _cull_oldest_thread(
                board.threads.filter(
                    is_pinned=False
                ).exclude(
                    community__is_private=True
                ),
                protect_pk=instance.pk
            )

    # Federation delivery for newly created threads is handled exclusively
    # by federation/signals.py's on_thread_created receiver, which guards
    # on is_remote=False before delivering. Do not duplicate that call here
    # — this receiver and that one both fire on every Thread save (Django
    # supports multiple receivers per signal), and a thread that arrives
    # via inbound federation (is_remote=True) is itself created via
    # Thread.objects.create(...), which also triggers this same post_save
    # signal. Calling deliver_create_thread from here unconditionally used
    # to re-broadcast every inbound federated thread back out under this
    # instance's own identity — causing the same post to arrive at a third
    # instance twice (once direct from the origin, once relayed) under two
    # different Note ids, since each relay regenerates a fresh id from its
    # own local Thread row rather than preserving the original.


@receiver(pre_delete, sender='core.Thread')
def on_thread_delete(sender, instance, **kwargs):
    _delete_thread_images(instance)


@receiver(pre_delete, sender='core.Post')
def on_post_delete(sender, instance, **kwargs):
    _delete_image_file(instance.image)
