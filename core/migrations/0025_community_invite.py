import uuid
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0024_sitesettings_community_prune_days'),
    ]

    operations = [
        migrations.CreateModel(
            name='CommunityInvite',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('token', models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('expires_at', models.DateTimeField(
                    blank=True, null=True,
                    help_text='Leave blank for a non-expiring link.'
                )),
                ('max_uses', models.PositiveIntegerField(
                    blank=True, null=True,
                    help_text='Leave blank for unlimited uses.'
                )),
                ('use_count', models.PositiveIntegerField(default=0)),
                ('is_active', models.BooleanField(
                    default=True,
                    help_text='Deactivate to revoke the link.'
                )),
                ('community', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='invites',
                    to='core.community',
                )),
                ('created_by', models.ForeignKey(
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='invites_created',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
        ),
    ]
