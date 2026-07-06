import time

from django.core.management.base import BaseCommand

from core.models import User


class Command(BaseCommand):
    help = (
        'Backfill display_name for existing federation stub users (is_remote=True) '
        'that were created before stub users started saving the remote actor\'s '
        'display name. Re-fetches each remote Actor document over the network '
        '(routed through Tor for .onion actors) and updates display_name if the '
        'actor has one set. Safe to re-run — only touches users with a blank '
        'display_name.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be updated without saving changes.',
        )
        parser.add_argument(
            '--delay',
            type=float,
            default=0.5,
            help='Seconds to sleep between fetches, to be polite to remote instances (default: 0.5).',
        )

    def handle(self, *args, **options):
        from federation.fetch import fetch_remote_actor

        dry_run = options['dry_run']
        delay = options['delay']

        stub_users = User.objects.filter(
            is_remote=True,
            display_name='',
        ).exclude(remote_actor_url='').order_by('id')

        total = stub_users.count()
        if total == 0:
            self.stdout.write(self.style.SUCCESS('No remote stub users with a blank display_name found.'))
            return

        self.stdout.write(f'Found {total} remote stub user(s) with a blank display_name.')
        if dry_run:
            self.stdout.write(self.style.WARNING('Dry run — no changes will be saved.'))

        updated = 0
        skipped = 0
        failed = 0

        for i, user in enumerate(stub_users, start=1):
            self.stdout.write(f'[{i}/{total}] {user.username} ({user.remote_actor_url}) ... ', ending='')
            try:
                data = fetch_remote_actor(user.remote_actor_url)
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'fetch failed: {e}'))
                failed += 1
                if i < total:
                    time.sleep(delay)
                continue

            name = data.get('name', '') or data.get('preferredUsername', '')
            if not name:
                self.stdout.write(self.style.WARNING('no name in actor document, skipped'))
                skipped += 1
                if i < total:
                    time.sleep(delay)
                continue

            name = name[:150]
            if dry_run:
                self.stdout.write(self.style.SUCCESS(f'would set display_name={name!r}'))
            else:
                user.display_name = name
                user.save(update_fields=['display_name'])
                self.stdout.write(self.style.SUCCESS(f'set display_name={name!r}'))
            updated += 1

            if i < total:
                time.sleep(delay)

        self.stdout.write('')
        summary = f'Done. {updated} updated, {skipped} skipped (no name), {failed} failed (fetch error).'
        if dry_run:
            summary = f'Done (dry run). {updated} would be updated, {skipped} skipped, {failed} failed.'
        self.stdout.write(self.style.SUCCESS(summary))
