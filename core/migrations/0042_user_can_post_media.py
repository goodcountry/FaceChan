from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0041_remove_max_boards'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='can_post_media',
            field=models.BooleanField(
                default=False,
                help_text=(
                    'Allow this user to attach images and videos even when site-wide '
                    'media uploads are disabled. Set by an operator; has no effect '
                    'when uploads are globally enabled.'
                ),
            ),
        ),
    ]
