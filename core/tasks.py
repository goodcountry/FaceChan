import logging
from celery import shared_task
from django.utils import timezone
from datetime import timedelta

logger = logging.getLogger(__name__)


@shared_task(bind=True, name='core.tasks.prune_inactive_communities')
def prune_inactive_communities(self):
    """
    Delete communities (and their threads and posts via CASCADE) that have had
    no new posts for SiteSettings.community_prune_days days.

    Definition of "inactive": no Post exists with created_at within the prune
    window across any thread belonging to the community. A community with
    threads but no replies is also inactive — the thread creation date is not
    used, only post activity.

    No exceptions: all communities are subject to the same rule regardless of
    who created them or how many members they have.

    Scheduled daily via django-celery-beat (configured in Django admin under
    Periodic Tasks). community_prune_days = 0 disables pruning entirely.
    """
    from .models import SiteSettings, Community, Post

    settings = SiteSettings.get()
    if not settings.community_prune_days:
        logger.info('Community pruning is disabled (community_prune_days=0). Skipping.')
        return {'pruned': 0, 'skipped': 'disabled'}

    cutoff = timezone.now() - timedelta(days=settings.community_prune_days)

    # Find communities where the most recent post across all their threads
    # is older than the cutoff — or they have no posts at all.
    # We use a subquery approach: exclude communities that have at least one
    # post created after the cutoff.
    from django.db.models import Q

    active_community_ids = (
        Post.objects
        .filter(thread__community__isnull=False, created_at__gte=cutoff)
        .values_list('thread__community_id', flat=True)
        .distinct()
    )

    stale = Community.objects.exclude(id__in=active_community_ids)
    count = stale.count()

    if count == 0:
        logger.info('Community pruning: no inactive communities found.')
        return {'pruned': 0}

    names = list(stale.values_list('slug', flat=True))
    logger.warning(
        'Community pruning: deleting %d inactive communities (no posts in %d days): %s',
        count, settings.community_prune_days, ', '.join(names)
    )

    # CASCADE on Community → Thread → Post means this deletes everything.
    stale.delete()

    logger.warning('Community pruning: deleted %d communities.', count)
    return {'pruned': count, 'communities': names}
