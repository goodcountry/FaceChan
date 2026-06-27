from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0017_add_thumbnail_fields'),
    ]

    operations = [
        migrations.CreateModel(
            name='WatchedThread',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('last_seen_reply_count', models.PositiveIntegerField(default=0)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('thread', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='watchers', to='core.thread')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='watched_threads', to='core.user')),
            ],
            options={
                'ordering': ['-created_at'],
                'unique_together': {('user', 'thread')},
            },
        ),
    ]
