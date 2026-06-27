from django.db import migrations


class Migration(migrations.Migration):
    """
    Merge migration — resolves two parallel branches that both depended on 0001_initial:
      - 0002_add_user_tagline_and_display_badge  (added in feature/docker-and-profile-fields)
      - 0004_fix_last_reply_at_not_auto_now_add  (tip of main's 0002→0003→0004 chain)
    No schema changes — this is purely a graph join.
    """

    dependencies = [
        ('core', '0002_add_user_tagline_and_display_badge'),
        ('core', '0004_fix_last_reply_at_not_auto_now_add'),
    ]

    operations = []
