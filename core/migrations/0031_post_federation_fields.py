from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0030_board_allow_federation_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='post',
            name='is_remote',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='post',
            name='remote_ap_id',
            field=models.URLField(
                blank=True,
                null=True,
                unique=True,
                help_text=(
                    'Canonical ActivityPub URL of this post on its origin server. '
                    'Null for local posts. Used for deduplication on inbound delivery.'
                ),
            ),
        ),
        migrations.AddField(
            model_name='post',
            name='remote_actor_url',
            field=models.URLField(
                blank=True,
                null=True,
                help_text=(
                    'AP URL of the remote actor who authored this post. '
                    'Null for local posts.'
                ),
            ),
        ),
    ]
