from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0020_add_activity_tiers'),
    ]

    operations = [
        migrations.AddField(
            model_name='board',
            name='allow_images',
            field=models.BooleanField(
                default=True,
                help_text='Allow users to attach images to threads and posts on this board.',
            ),
        ),
    ]
