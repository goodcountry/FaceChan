from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0043_allow_links_toggle'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='age_verified',
            field=models.BooleanField(
                default=False,
                help_text=(
                    'Whether this user has confirmed they meet the minimum age '
                    'requirement to view NSFW boards. Persists across devices once '
                    'set. Has no effect on logged-out/anonymous visitors.'
                ),
            ),
        ),
    ]
