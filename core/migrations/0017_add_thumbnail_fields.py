from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0016_add_pdq_hash_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='thread',
            name='thumbnail',
            field=models.ImageField(
                upload_to='thread_thumbs/', null=True, blank=True,
                help_text='320×180px WebP thumbnail generated at upload time. '
                          'Used in thread list cards and catalog view instead of '
                          'loading the full-size image.'
            ),
        ),
        migrations.AddField(
            model_name='post',
            name='thumbnail',
            field=models.ImageField(
                upload_to='post_thumbs/', null=True, blank=True,
                help_text='320×180px WebP thumbnail generated at upload time.'
            ),
        ),
    ]
