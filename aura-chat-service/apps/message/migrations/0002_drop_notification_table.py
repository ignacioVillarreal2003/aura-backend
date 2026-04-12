from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("message", "0001_initial"),
    ]

    operations = [
        migrations.RunSQL(
            sql='DROP TABLE IF EXISTS "notification" CASCADE;',
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]
