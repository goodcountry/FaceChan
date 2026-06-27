"""
core/management/commands/grant_admin.py

Bootstrap or assign an admin-tier role to a user.

Every fresh instance needs a way to mint its first real admin: a Django
superuser flag alone does NOT grant access to staff tooling (the federation
dashboard, purge, role management), because those are gated on an
admin-tier Role with can_purge — see core.permissions.can_purge_content.

Usage:
    python manage.py grant_admin <username>
    python manage.py grant_admin <username> --role-name "Owner"

Idempotent: re-running for the same user is a no-op beyond ensuring the
role exists and is attached.
"""

from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model

from core.models import Role

User = get_user_model()

# Full capability set for the bootstrap admin role.
ADMIN_FLAGS = dict(
    is_admin_tier=True,
    can_hide=True,
    can_resolve_reports=True,
    can_quarantine=True,
    can_purge=True,
    can_lock_threads=True,
    can_pin_threads=True,
    can_suspend=True,
    can_ban=True,
    can_manage_roles=True,
    can_manage_pages=True,
)


class Command(BaseCommand):
    help = 'Grant an admin-tier staff role to a user (creates the role if needed).'

    def add_arguments(self, parser):
        parser.add_argument('username', help='Username to grant the admin role to.')
        parser.add_argument(
            '--role-name',
            default='Admin',
            help='Name of the admin-tier role to create/reuse (default: "Admin").',
        )

    def handle(self, *args, **options):
        username = options['username']
        role_name = options['role_name']

        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            raise CommandError(f'No user with username {username!r}.')

        role, created = Role.objects.get_or_create(
            name=role_name,
            defaults={'tier': 100, **ADMIN_FLAGS},
        )

        if not created:
            # Ensure an existing role of this name really is admin-tier with
            # purge — otherwise granting it would be a silent no-op for access.
            changed = []
            for flag, value in ADMIN_FLAGS.items():
                if getattr(role, flag) != value:
                    setattr(role, flag, value)
                    changed.append(flag)
            if changed:
                role.save(update_fields=changed)
                self.stdout.write(
                    f'Updated existing role {role_name!r}: set {", ".join(changed)}.'
                )

        user.role = role
        user.save(update_fields=['role'])

        verb = 'Created' if created else 'Reused'
        self.stdout.write(self.style.SUCCESS(
            f'{verb} admin-tier role {role_name!r} and assigned it to {username!r}. '
            f'(is_admin_tier=True, can_purge=True — full staff access.)'
        ))
