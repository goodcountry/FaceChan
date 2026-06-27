from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0015_add_username_change_audit'),
    ]

    operations = [
        # Thread image PDQ hash
        migrations.AddField(
            model_name='thread',
            name='image_pdq_hash',
            field=models.CharField(
                max_length=64, null=True, blank=True, editable=False,
                help_text='PDQ perceptual hash of the thread image. Used for CSAM hash-matching. '
                          'Null if no image attached or if hashing failed.'
            ),
        ),
        # Post image PDQ hash
        migrations.AddField(
            model_name='post',
            name='image_pdq_hash',
            field=models.CharField(
                max_length=64, null=True, blank=True, editable=False,
                help_text='PDQ perceptual hash of the post image. Used for CSAM hash-matching. '
                          'Null if no image attached or if hashing failed.'
            ),
        ),
        # User avatar PDQ hash
        migrations.AddField(
            model_name='user',
            name='avatar_pdq_hash',
            field=models.CharField(
                max_length=64, null=True, blank=True, editable=False,
                help_text='PDQ perceptual hash of the avatar image. Used for CSAM hash-matching. '
                          'Null until an avatar is uploaded or if hashing failed.'
            ),
        ),
    ]
