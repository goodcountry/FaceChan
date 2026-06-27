from django.db import migrations

RULES_CONTENT = """## Rules

*This page has not been set up yet. Visit **Mod → Pages** to edit this content.*

Rules will appear here.
"""

FAQ_CONTENT = """## Frequently Asked Questions

*This page has not been set up yet. Visit **Mod → Pages** to edit this content.*

FAQs will appear here.
"""

def seed_pages(apps, schema_editor):
    SitePage = apps.get_model('core', 'SitePage')
    SitePage.objects.get_or_create(
        slug='rules',
        defaults={
            'title': 'Rules',
            'content': RULES_CONTENT,
            'published': True,
            'show_in_footer': True,
            'display_order': 1,
        },
    )
    SitePage.objects.get_or_create(
        slug='faq',
        defaults={
            'title': 'FAQ',
            'content': FAQ_CONTENT,
            'published': True,
            'show_in_footer': True,
            'display_order': 2,
        },
    )


def remove_pages(apps, schema_editor):
    SitePage = apps.get_model('core', 'SitePage')
    SitePage.objects.filter(slug__in=['rules', 'faq']).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0038_add_sitepage_and_can_manage_pages'),
    ]

    operations = [
        migrations.RunPython(seed_pages, remove_pages),
    ]
