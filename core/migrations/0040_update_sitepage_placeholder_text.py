from django.db import migrations

OLD = 'The instance operator should edit this page in Django admin.'
NEW = 'Visit **Mod → Pages** to edit this content.'

def update_placeholders(apps, schema_editor):
    SitePage = apps.get_model('core', 'SitePage')
    for page in SitePage.objects.all():
        if OLD in page.content:
            page.content = page.content.replace(OLD, NEW)
            page.save(update_fields=['content'])

class Migration(migrations.Migration):
    dependencies = [
        ('core', '0039_seed_default_site_pages'),
    ]
    operations = [
        migrations.RunPython(update_placeholders, migrations.RunPython.noop),
    ]
