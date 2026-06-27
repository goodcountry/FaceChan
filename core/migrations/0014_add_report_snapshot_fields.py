import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def backfill_target_type(apps, schema_editor):
    """
    target_type becomes a required field, but pre-existing Report rows
    don't have it. Derive it from whichever of thread_id/post_id is set —
    this is safe inference from data the row already has, NOT the kind of
    backfill Ed asked us to skip (that was about reconstructing
    author/board/preview for content that may already be gone, which we
    deliberately leave blank on old rows).

    For the rare pre-existing row where BOTH thread_id and post_id are
    already null (content was purged before this migration existed, back
    when that meant losing the distinction entirely) there's genuinely no
    way to recover which it was. Default to 'thread' for those — it's a
    coin flip either way, and it only affects the few real reports made
    during development before this fix existed.
    """
    Report = apps.get_model('core', 'Report')
    Report.objects.filter(thread_id__isnull=False).update(target_type='thread')
    Report.objects.filter(thread_id__isnull=True, post_id__isnull=False).update(target_type='post')
    Report.objects.filter(thread_id__isnull=True, post_id__isnull=True).update(target_type='thread')


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0013_relax_report_target_constraint'),
    ]

    operations = [
        migrations.AddField(
            model_name='report',
            name='target_author',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='reports_against', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name='report',
            name='target_author_username',
            field=models.CharField(blank=True, max_length=150),
        ),
        migrations.AddField(
            model_name='report',
            name='target_board_slug',
            field=models.CharField(blank=True, max_length=100),
        ),
        migrations.AddField(
            model_name='report',
            name='target_preview_snapshot',
            field=models.CharField(blank=True, max_length=200),
        ),
        # Added nullable first so existing rows don't error on creation,
        # then backfilled, then a second migration step (below) would
        # normally tighten it — but SQLite (dev) can't alter column
        # nullability in place easily via Django's migration framework in
        # a single step here, so we keep target_type nullable at the DB
        # level and treat "required" as an application-level rule enforced
        # in _create_report instead. Every NEW row gets one explicitly.
        migrations.AddField(
            model_name='report',
            name='target_type',
            field=models.CharField(blank=True, choices=[('thread', 'Thread'), ('post', 'Post')], max_length=10, null=True),
        ),
        migrations.RunPython(backfill_target_type, noop_reverse),
    ]
