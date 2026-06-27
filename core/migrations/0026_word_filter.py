import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0025_community_invite'),
    ]

    operations = [
        migrations.CreateModel(
            name='WordFilter',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('pattern', models.CharField(
                    max_length=500,
                    help_text='Word, phrase, or regex pattern to match (case-insensitive).',
                )),
                ('replacement', models.CharField(
                    max_length=500,
                    default='quack',
                    help_text='Text to substitute in place of the matched pattern.',
                )),
                ('scope', models.CharField(
                    max_length=10,
                    choices=[('site', 'Site-wide'), ('board', 'Board-specific')],
                    default='site',
                    help_text='Site-wide applies everywhere. Board-specific applies only to the selected board.',
                )),
                ('board', models.ForeignKey(
                    null=True, blank=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='word_filters',
                    to='core.board',
                    help_text='Required when scope is "board". Ignored for site-wide filters.',
                )),
                ('is_regex', models.BooleanField(
                    default=False,
                    help_text='Treat pattern as a Python regex. If off, plain substring match.',
                )),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'ordering': ['scope', 'pattern'],
            },
        ),
    ]
