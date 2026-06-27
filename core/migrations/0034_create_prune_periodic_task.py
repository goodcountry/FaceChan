"""
Data migration — creates the Celery Beat periodic task for community pruning
if it doesn't already exist. Safe to run multiple times (get_or_create).
"""
from django.db import migrations


def create_prune_task(apps, schema_editor):
    try:
        CrontabSchedule = apps.get_model('django_celery_beat', 'CrontabSchedule')
        PeriodicTask = apps.get_model('django_celery_beat', 'PeriodicTask')
    except LookupError:
        # django_celery_beat not installed — skip silently
        return

    schedule, _ = CrontabSchedule.objects.get_or_create(
        minute='0',
        hour='3',
        day_of_week='*',
        day_of_month='*',
        month_of_year='*',
    )

    PeriodicTask.objects.get_or_create(
        name='Prune inactive communities',
        defaults={
            'task': 'core.tasks.prune_inactive_communities',
            'crontab': schedule,
            'enabled': True,
        },
    )


def remove_prune_task(apps, schema_editor):
    try:
        PeriodicTask = apps.get_model('django_celery_beat', 'PeriodicTask')
    except LookupError:
        return
    PeriodicTask.objects.filter(name='Prune inactive communities').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0033_add_avatar_settings'),
        ('django_celery_beat', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(create_prune_task, remove_prune_task),
    ]
