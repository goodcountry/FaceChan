from django.core.management.base import BaseCommand
from core.tasks import prune_inactive_communities


class Command(BaseCommand):
    help = (
        'Prune communities with no post activity within community_prune_days days. '
        'Deletes the community and all its threads and posts. '
        'Reads community_prune_days from SiteSettings (0 = disabled). '
        'This is also run automatically by the Celery beat scheduler.'
    )

    def handle(self, *args, **options):
        self.stdout.write('Running community pruning...')
        result = prune_inactive_communities()
        if result.get('skipped'):
            self.stdout.write(self.style.WARNING('Pruning is disabled (community_prune_days=0).'))
        elif result['pruned'] == 0:
            self.stdout.write(self.style.SUCCESS('No inactive communities found.'))
        else:
            self.stdout.write(self.style.SUCCESS(
                f"Pruned {result['pruned']} communities: {', '.join(result['communities'])}"
            ))
