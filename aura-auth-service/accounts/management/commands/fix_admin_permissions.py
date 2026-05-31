"""
Management command: fix_admin_permissions

Adds the permissions that superadmin should have exclusively (capabilities
that admin does NOT have in the admin panel) and assigns them to the
superadmin role.  Nothing is removed from admin.

Based on code-gate analysis:
  - chat.*           → ChatAdmin requires _is_super_admin_user
  - user.list_all    → UserAdmin queryset gated by _is_effective_superadmin
  - user.manage_admin → create/edit/delete admin users
  - role.manage_permissions → edit role-permission assignments
  - notification.send_admin / notification.view_admin
  - notification.edit
  - audit.view_all   → full audit log access
  - user_mac.view_profile → _check_superadmin in mac_admin

Usage:
    python manage.py fix_admin_permissions --list
    python manage.py fix_admin_permissions --dry-run
    python manage.py fix_admin_permissions --execute
"""

from django.core.management.base import BaseCommand, CommandError

from accounts.models import Permission, PermissionInRole, Role


# ── Permissions to add exclusively to superadmin ─────────────────────────────
# (name, description)
_SUPERADMIN_EXCLUSIVE = [
    # Chat section — entire module is superadmin-only
    ('chat.view',            'Ver la sección de chats en el panel'),
    ('chat.list',            'Listar todos los chats del sistema'),
    ('chat.read',            'Leer el historial de mensajes de un chat'),

    # User management — seeing and managing admin users
    ('user.list_all',        'Listar todos los usuarios incluyendo administradores'),
    ('user.manage_admin',    'Crear, editar y eliminar usuarios con rol admin'),

    # Role permissions management
    ('role.manage_permissions', 'Asignar y quitar permisos a los roles del sistema'),

    # Notifications — targeting admin/superadmin users
    ('notification.send_admin',  'Enviar notificaciones a usuarios con rol admin'),
    ('notification.view_admin',  'Ver notificaciones enviadas a administradores'),
    ('notification.edit',        'Editar el contenido de notificaciones existentes'),

    # Audit — full log visibility
    ('audit.view_all', 'Ver el registro de acciones de todos los usuarios (no solo los propios)'),

    # MAC full profile
    ('user_mac.view_profile', 'Ver el perfil MAC completo de cualquier usuario'),
]


class Command(BaseCommand):
    help = (
        'Agrega los permisos exclusivos de superadmin a la tabla de permisos '
        'y los asigna al rol superadmin.'
    )

    def add_arguments(self, parser):
        group = parser.add_mutually_exclusive_group(required=True)
        group.add_argument(
            '--list',
            action='store_true',
            help='Muestra el estado actual: qué permisos exclusivos ya existen y cuáles faltan.',
        )
        group.add_argument(
            '--dry-run',
            action='store_true',
            help='Muestra qué permisos se crearían/asignarían sin aplicar cambios.',
        )
        group.add_argument(
            '--execute',
            action='store_true',
            help='Crea los permisos faltantes y los asigna al rol superadmin.',
        )

    def handle(self, *args, **options):
        try:
            superadmin_role = Role.objects.get(name='superadmin')
        except Role.DoesNotExist:
            raise CommandError('Rol "superadmin" no encontrado.')

        try:
            admin_role = Role.objects.get(name='admin')
        except Role.DoesNotExist:
            admin_role = None

        existing_perm_names = set(Permission.objects.values_list('name', flat=True))
        superadmin_perm_names = set(
            PermissionInRole.objects.filter(role=superadmin_role)
            .values_list('permission__name', flat=True)
        )
        admin_perm_names = set(
            PermissionInRole.objects.filter(role=admin_role)
            .values_list('permission__name', flat=True)
        ) if admin_role else set()

        if options['list']:
            self._cmd_list(existing_perm_names, superadmin_perm_names, admin_perm_names)
        elif options['dry_run']:
            self._cmd_dry_run(existing_perm_names, superadmin_perm_names, admin_perm_names)
        elif options['execute']:
            self._cmd_execute(superadmin_role, existing_perm_names, superadmin_perm_names, admin_perm_names)

    # ── --list ────────────────────────────────────────────────────────────────

    def _cmd_list(self, existing, superadmin_perms, admin_perms):
        self.stdout.write('\n=== PERMISOS EXCLUSIVOS DE SUPERADMIN ===\n')
        self.stdout.write(
            f'  {"Permiso":<40} {"En DB":<8} {"Superadmin":<12} {"Admin":<8} {"Estado"}\n'
        )
        self.stdout.write('-' * 90 + '\n')

        needs_create = 0
        needs_assign = 0

        for name, desc in _SUPERADMIN_EXCLUSIVE:
            in_db = name in existing
            in_super = name in superadmin_perms
            in_admin = name in admin_perms

            if not in_db:
                status = self.style.ERROR('FALTA EN DB')
                needs_create += 1
            elif not in_super:
                status = self.style.WARNING('FALTA EN ROL')
                needs_assign += 1
            elif in_admin:
                status = self.style.WARNING('TAMBIÉN EN ADMIN (ok si es intencional)')
            else:
                status = self.style.SUCCESS('OK — solo superadmin')

            self.stdout.write(
                f'  {name:<40} {"✓" if in_db else "—":<8} '
                f'{"✓" if in_super else "—":<12} {"✓" if in_admin else "—":<8} {status}\n'
            )

        self.stdout.write(f'\nTotal de permisos exclusivos definidos: {len(_SUPERADMIN_EXCLUSIVE)}\n')
        if needs_create or needs_assign:
            self.stdout.write(self.style.WARNING(
                f'→ Permisos a crear: {needs_create} | A asignar al rol: {needs_assign}\n'
                f'  Ejecutá --execute para aplicar.\n'
            ))
        else:
            self.stdout.write(self.style.SUCCESS('→ Todo en orden.\n'))

    # ── --dry-run ─────────────────────────────────────────────────────────────

    def _cmd_dry_run(self, existing, superadmin_perms, admin_perms):
        to_create = [(n, d) for n, d in _SUPERADMIN_EXCLUSIVE if n not in existing]
        to_assign = [(n, d) for n, d in _SUPERADMIN_EXCLUSIVE if n in existing and n not in superadmin_perms]

        if not to_create and not to_assign:
            self.stdout.write(self.style.SUCCESS(
                'Nada que hacer: superadmin ya tiene todos sus permisos exclusivos.'
            ))
            return

        if to_create:
            self.stdout.write(self.style.WARNING(
                f'\n[DRY-RUN] Se crearían {len(to_create)} permisos nuevos:\n'
            ))
            for name, desc in to_create:
                self.stdout.write(f'  + {name:<40}  "{desc}"\n')

        if to_assign:
            self.stdout.write(self.style.WARNING(
                f'\n[DRY-RUN] Se asignarían {len(to_assign)} permisos existentes a superadmin:\n'
            ))
            for name, desc in to_assign:
                self.stdout.write(f'  → {name}\n')

        self.stdout.write('\nEjecutá --execute para aplicar los cambios.\n')

    # ── --execute ─────────────────────────────────────────────────────────────

    def _cmd_execute(self, superadmin_role, existing, superadmin_perms, admin_perms):
        created_count = 0
        assigned_count = 0

        for name, desc in _SUPERADMIN_EXCLUSIVE:
            perm, created = Permission.objects.get_or_create(
                name=name,
                defaults={'description': desc},
            )
            if created:
                created_count += 1
                self.stdout.write(self.style.SUCCESS(f'  ✓ Permiso creado: {name}'))

            _, assigned = PermissionInRole.objects.get_or_create(
                role=superadmin_role,
                permission=perm,
            )
            if assigned:
                assigned_count += 1
                self.stdout.write(self.style.SUCCESS(f'  → Asignado a superadmin: {name}'))

        total_super = PermissionInRole.objects.filter(role=superadmin_role).count()
        self.stdout.write(self.style.SUCCESS(
            f'\n✓ Listo. Creados: {created_count} | Asignados: {assigned_count}\n'
            f'  Superadmin ahora tiene {total_super} permisos en total.\n'
        ))
        self.stdout.write(
            'Ejecutá --list para verificar el resultado final.\n'
        )
