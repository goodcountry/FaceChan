from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0021_board_allow_images'),
    ]

    operations = [
        migrations.AddField(
            model_name='thread',
            name='poster_ip',
            field=models.GenericIPAddressField(
                null=True, blank=True, editable=False,
                help_text='IP address of the poster at submission time. Admin-only. Raw address — handle as personal data per your jurisdiction.',
            ),
        ),
        migrations.AddField(
            model_name='post',
            name='poster_ip',
            field=models.GenericIPAddressField(
                null=True, blank=True, editable=False,
                help_text='IP address of the poster at submission time. Admin-only. Raw address — handle as personal data per your jurisdiction.',
            ),
        ),
        migrations.AddField(
            model_name='report',
            name='target_poster_ip',
            field=models.GenericIPAddressField(
                null=True, blank=True,
                help_text='IP of the content author at the time the report was filed. Snapshotted so it survives content purge.',
            ),
        ),
    ]
