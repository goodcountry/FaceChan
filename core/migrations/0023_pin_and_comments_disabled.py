from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0022_add_poster_ip'),
    ]

    operations = [
        migrations.AddField(
            model_name='role',
            name='can_pin_threads',
            field=models.BooleanField(
                default=False,
                help_text='Pin/unpin threads and toggle comments disabled on any thread within scope.',
            ),
        ),
        migrations.AddField(
            model_name='thread',
            name='comments_disabled',
            field=models.BooleanField(
                default=False,
                help_text='Disable new comments on this thread. Set automatically when pinned; '
                          'can also be toggled independently to cool down any thread.',
            ),
        ),
    ]
