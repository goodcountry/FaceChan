from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0042_user_can_post_media'),
    ]

    operations = [
        # Board-level per-board toggle
        migrations.AddField(
            model_name='board',
            name='allow_links',
            field=models.BooleanField(
                default=False,
                help_text=(
                    'Allow users to post hyperlinks (http:// or https://) in thread titles, '
                    'thread bodies, and replies on this board. '
                    'Has no effect when the global "allow links" setting is disabled.'
                ),
            ),
        ),
        # Global master switch on SiteSettings
        migrations.AddField(
            model_name='sitesettings',
            name='allow_links',
            field=models.BooleanField(
                default=False,
                help_text=(
                    'Master switch for hyperlinks. When off, no board may allow hyperlinks '
                    'regardless of its own setting. When on, individual boards can enable or '
                    'disable links independently. Links means http:// or https:// URLs — '
                    'bare domain names are always allowed.'
                ),
            ),
        ),
    ]
