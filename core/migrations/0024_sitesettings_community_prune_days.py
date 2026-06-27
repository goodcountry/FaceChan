from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0023_pin_and_comments_disabled'),
    ]

    operations = [
        migrations.AddField(
            model_name='sitesettings',
            name='community_prune_days',
            field=models.PositiveIntegerField(
                default=30,
                help_text='Automatically delete communities (and all their threads and posts) '
                          'that have had no new posts for this many days. '
                          'No exceptions — all communities are subject to this rule. '
                          '0 = pruning disabled.',
            ),
        ),
    ]
