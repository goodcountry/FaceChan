from django.core.management.base import BaseCommand
from django.db import transaction

from core.models import User


class Command(BaseCommand):
    help = (
        'Fix federation stub users that were wrongly created from a board\'s '
        'Group actor instead of a Person, due to anonymous posts/replies being '
        'misattributed before the facechan:anonymous handling fix. Affected '
        'users have remote_actor_url containing "/ap/boards/". Deleting them '
        'sets author back to NULL on their threads/posts (author FK is '
        'SET_NULL), correctly restoring those posts to anonymous.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be deleted without making changes.',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']

        bogus_users = User.objects.filter(
            is_remote=True,
            remote_actor_url__contains='/ap/boards/',
        ).order_by('id')

        total = bogus_users.count()
        if total == 0:
            self.stdout.write(self.style.SUCCESS('No misattributed board-actor stub users found.'))
            return

        self.stdout.write(f'Found {total} stub user(s) created from a board actor instead of a Person:')
        for user in bogus_users:
            thread_count = user.threads.count()
            post_count = user.posts.count()
            self.stdout.write(
                f'  - {user.username} (display_name={user.display_name!r}, '
                f'{thread_count} thread(s), {post_count} post(s))'
            )

        if dry_run:
            self.stdout.write(self.style.WARNING(
                'Dry run — no changes made. Re-run without --dry-run to delete these '
                'users and restore the affected threads/posts to anonymous.'
            ))
            return

        with transaction.atomic():
            deleted_count, _ = bogus_users.delete()

        self.stdout.write(self.style.SUCCESS(
            f'Deleted {total} misattributed stub user(s). Their threads/posts now show as anonymous.'
        ))
