from django.db import migrations, models


def backfill_chat_message_created_by(apps, schema_editor):
    ChatMessage = apps.get_model("message", "ChatMessage")
    ChatMessage.objects.filter(created_by__isnull=True).update(created_by=0)


class Migration(migrations.Migration):

    dependencies = [
        ("message", "0002_drop_notification_table"),
    ]

    operations = [
        migrations.RunPython(
            backfill_chat_message_created_by,
            reverse_code=migrations.RunPython.noop,
        ),
        migrations.AlterField(
            model_name="chatmessage",
            name="created_by",
            field=models.BigIntegerField(),
        ),
    ]
