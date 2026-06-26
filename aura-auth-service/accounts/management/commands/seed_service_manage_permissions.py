"""
Management command: seed_service_manage_permissions

Crea (si faltan) los permisos ``*_MANAGE`` que los servicios downstream
(aura-document-processing-service) ya exigen en sus endpoints de
administración, y los asigna a los roles ``admin`` y/o ``superadmin``.

Por qué hace falta: los servicios validan el token del usuario contra
``GET /auth/validate`` de este servicio y aplican los permisos REALES del
usuario (no hay bypass por API key — el middleware de document-processing
solo acepta Bearer JWT). Para que el panel admin pueda llamar a los
endpoints ``manage`` en nombre del usuario, el permiso correspondiente debe
existir como fila ``Permission`` y estar asignado al rol del usuario.

Notas de diseño:
  - Los nombres se guardan en forma dotted/minúscula (convención existente,
    p. ej. ``chat.view``). ``accounts.utils._normalize_permission_name`` los
    entrega normalizados a UPPER_SNAKE (``DOCUMENT_QUERY_MANAGE``), que es lo
    que comprueba el ``Authorizer`` de document-processing.
  - Un ``superadmin`` (rol que define ``User.is_superuser``) ya recibe TODAS
    las filas ``Permission`` existentes vía ``get_user_permissions``; aun así
    se asignan explícitamente para que el panel de roles muestre el estado
    real.
  - Las operaciones masivas/pesadas (reprocess, reembed, enrich,
    graph-extract) se reservan a ``superadmin``. El resto (consulta, edición,
    borrado, restauración, descarga, stats del grafo) se asigna también a
    ``admin``, alineado con lo que el panel de documentos ya permite a un
    admin.

Uso:
    python manage.py seed_service_manage_permissions --list
    python manage.py seed_service_manage_permissions --dry-run
    python manage.py seed_service_manage_permissions --execute
"""

from django.core.management.base import BaseCommand, CommandError

from accounts.models import Permission, PermissionInRole, Role


# (name, description) — asignados a admin Y superadmin
_ADMIN_AND_SUPER = [
    ('document.query.manage',    'Consultar cualquier documento sin restricción de chat (admin)'),
    ('document.update.manage',   'Editar metadata de cualquier documento (admin)'),
    ('document.delete.manage',   'Eliminar (lógico) cualquier documento (admin)'),
    ('document.restore.manage',  'Restaurar cualquier documento eliminado (admin)'),
    ('document.download.manage', 'Descargar el archivo de cualquier documento (admin)'),
    ('graph.stats.manage',       'Ver estadísticas del grafo de conocimiento (admin)'),
]

# (name, description) — solo superadmin (operaciones masivas/pesadas)
_SUPER_ONLY = [
    ('document.reprocess.manage', 'Reprocesar documentos en masa (superadmin)'),
    ('document.reembed.manage',   'Regenerar embeddings de documentos en masa (superadmin)'),
    ('document.enrich.manage',    'Enriquecer (clasificar) documentos en masa (superadmin)'),
    ('graph.extract.manage',      'Reextraer el grafo de conocimiento en masa (superadmin)'),
]


class Command(BaseCommand):
    help = (
        'Crea los permisos *_MANAGE de los servicios downstream y los asigna a '
        'los roles admin/superadmin.'
    )

    def add_arguments(self, parser):
        group = parser.add_mutually_exclusive_group(required=True)
        group.add_argument(
            '--list', action='store_true',
            help='Muestra el estado actual de cada permiso (en DB / asignado).',
        )
        group.add_argument(
            '--dry-run', action='store_true',
            help='Muestra qué se crearía/asignaría sin aplicar cambios.',
        )
        group.add_argument(
            '--execute', action='store_true',
            help='Crea los permisos faltantes y los asigna a los roles.',
        )

    def handle(self, *args, **options):
        try:
            superadmin_role = Role.objects.get(name='superadmin')
        except Role.DoesNotExist:
            raise CommandError(
                'Rol "superadmin" no encontrado. La BD debe estar inicializada con su '
                'esquema y semilla (docker/database/auth-db/init.sql + data.sql).'
            )

        admin_role = Role.objects.filter(name='admin').first()
        if admin_role is None:
            self.stdout.write(self.style.WARNING(
                'Rol "admin" no encontrado: los permisos de nivel admin solo se '
                'asignarán a superadmin.'
            ))

        existing = set(Permission.objects.values_list('name', flat=True))
        super_assigned = set(
            PermissionInRole.objects.filter(role=superadmin_role)
            .values_list('permission__name', flat=True)
        )
        admin_assigned = set(
            PermissionInRole.objects.filter(role=admin_role)
            .values_list('permission__name', flat=True)
        ) if admin_role else set()

        if options['list']:
            self._cmd_list(existing, super_assigned, admin_assigned)
        elif options['dry_run']:
            self._cmd_dry_run(existing, super_assigned, admin_assigned, admin_role)
        elif options['execute']:
            self._cmd_execute(superadmin_role, admin_role)

    # ── --list ──────────────────────────────────────────────────────────────
    def _cmd_list(self, existing, super_assigned, admin_assigned):
        self.stdout.write('\n=== PERMISOS *_MANAGE DE SERVICIOS ===\n')
        self.stdout.write(f'  {"Permiso":<30} {"En DB":<7} {"Admin":<7} {"Superadmin"}\n')
        self.stdout.write('-' * 60 + '\n')

        for name, _desc in _ADMIN_AND_SUPER:
            self._print_row(name, existing, admin_assigned, super_assigned, admin_expected=True)
        for name, _desc in _SUPER_ONLY:
            self._print_row(name, existing, admin_assigned, super_assigned, admin_expected=False)

    def _print_row(self, name, existing, admin_assigned, super_assigned, *, admin_expected):
        in_db = '✓' if name in existing else '—'
        in_admin = '✓' if name in admin_assigned else ('—' if admin_expected else 'n/a')
        in_super = '✓' if name in super_assigned else '—'
        self.stdout.write(f'  {name:<30} {in_db:<7} {in_admin:<7} {in_super}\n')

    # ── --dry-run ───────────────────────────────────────────────────────────
    def _cmd_dry_run(self, existing, super_assigned, admin_assigned, admin_role):
        to_create = [
            n for n, _ in (_ADMIN_AND_SUPER + _SUPER_ONLY) if n not in existing
        ]
        to_assign_super = [
            n for n, _ in (_ADMIN_AND_SUPER + _SUPER_ONLY) if n not in super_assigned
        ]
        to_assign_admin = [
            n for n, _ in _ADMIN_AND_SUPER if n not in admin_assigned
        ] if admin_role else []

        self.stdout.write(self.style.WARNING(
            f'\n[DRY-RUN] Permisos a crear: {len(to_create)}\n'
        ))
        for n in to_create:
            self.stdout.write(f'  + {n}\n')
        self.stdout.write(self.style.WARNING(
            f'\n[DRY-RUN] A asignar a superadmin: {len(to_assign_super)} | '
            f'a admin: {len(to_assign_admin)}\n'
        ))
        self.stdout.write('\nEjecutá --execute para aplicar.\n')

    # ── --execute ───────────────────────────────────────────────────────────
    def _cmd_execute(self, superadmin_role, admin_role):
        created = 0
        assigned = 0

        def _ensure(name, desc, roles):
            nonlocal created, assigned
            perm, was_created = Permission.objects.get_or_create(
                name=name, defaults={'description': desc},
            )
            if was_created:
                created += 1
                self.stdout.write(self.style.SUCCESS(f'  ✓ Permiso creado: {name}'))
            for role in roles:
                if role is None:
                    continue
                _, was_assigned = PermissionInRole.objects.get_or_create(
                    role=role, permission=perm,
                )
                if was_assigned:
                    assigned += 1
                    self.stdout.write(self.style.SUCCESS(
                        f'  → Asignado a {role.name}: {name}'
                    ))

        for name, desc in _ADMIN_AND_SUPER:
            _ensure(name, desc, [superadmin_role, admin_role])
        for name, desc in _SUPER_ONLY:
            _ensure(name, desc, [superadmin_role])

        self.stdout.write(self.style.SUCCESS(
            f'\n✓ Listo. Permisos creados: {created} | Asignaciones nuevas: {assigned}\n'
        ))
