from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0019_add_bump_lock_percent'),
    ]

    operations = [
        migrations.CreateModel(
            name='ActivityTier',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('label', models.CharField(max_length=50, help_text='Displayed on the public profile.')),
                ('min_posts', models.PositiveIntegerField(help_text='Minimum post count to reach this tier.')),
                ('order', models.PositiveIntegerField(default=0, help_text='Display order in admin.')),
            ],
            options={
                'ordering': ['order', 'min_posts'],
            },
        ),
    ]
