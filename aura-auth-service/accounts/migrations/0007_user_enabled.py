from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0006_seed_roles'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    sql="""
                    ALTER TABLE auth_user
                    ADD COLUMN IF NOT EXISTS enabled boolean DEFAULT TRUE;

                    UPDATE auth_user
                    SET enabled = TRUE
                    WHERE enabled IS NULL;

                    ALTER TABLE auth_user
                    ALTER COLUMN enabled SET NOT NULL;
                    """,
                    reverse_sql="""
                    ALTER TABLE auth_user
                    DROP COLUMN IF EXISTS enabled;
                    """,
                ),
            ],
            state_operations=[
                migrations.AddField(
                    model_name='user',
                    name='enabled',
                    field=models.BooleanField(default=True),
                ),
            ],
        ),
    ]
