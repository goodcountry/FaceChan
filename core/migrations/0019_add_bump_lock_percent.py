from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0018_add_watched_thread'),
    ]

    operations = [
        migrations.AddField(
            model_name='sitesettings',
            name='bump_lock_percent',
            field=models.PositiveIntegerField(
                default=75,
                help_text='Thread stops bumping to the top once reply count reaches this '
                          'percentage of max_posts_per_thread. E.g. 75 means a 500-post '
                          'thread bump-locks at 375 replies. Set to 0 to disable.'
            ),
        ),
    ]
