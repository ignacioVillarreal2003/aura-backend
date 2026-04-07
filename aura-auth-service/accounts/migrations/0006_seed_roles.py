from django.db import migrations


def seed_roles(apps, schema_editor):
    Role = apps.get_model('accounts', 'Role')
    roles = [
        {'name': 'ADMIN', 'description': 'Administrador'},
        {'name': 'USER', 'description': 'Usuario'},
    ]
    for role in roles:
        Role.objects.get_or_create(
            name=role['name'],
            defaults={'description': role['description']},
        )


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ('accounts', '0005_custom_group'),
    ]

    operations = [
        migrations.RunPython(seed_roles, reverse_code=noop_reverse),
    ]
