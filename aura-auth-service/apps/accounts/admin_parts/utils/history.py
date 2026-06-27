"""Arma las paginas de historial de una entidad a partir del audit_log."""

_ACTION_LABELS = {
    'CREATE': ('Creó',     '#16a34a'),
    'UPDATE': ('Modificó', '#2563eb'),
    'DELETE': ('Eliminó',  '#dc2626'),
}

_KEY_LABELS = {
    'usuario':              'Usuario',
    'nombre':               'Nombre',
    'correo':               'Correo',
    'activo':               'Activo',
    'rol':                  'Rol',
    'nivel':                'Nivel',
    'agrupaciones':         'Agrupaciones',
    'descripción':          'Descripción',
    'posición':             'Posición',
    'usuarios_asignados':   'Usuarios asignados',
    'documentos_asignados': 'Documentos asignados',
}


def _fmt(v):
    if v is None:
        return '—'
    if isinstance(v, bool):
        return 'Sí' if v else 'No'
    if isinstance(v, list):
        return ', '.join(str(x) for x in v) if v else '—'
    return str(v)


def build_entity_history(entity_type, entity_id):
    """Devuelve las entradas del audit_log listas para la plantilla de historial."""
    from apps.accounts.models import AuditLog

    raw = list(
        AuditLog.objects.filter(
            entity_type=entity_type,
            entity_id=str(entity_id),
        ).order_by('-timestamp').values(
            'timestamp', 'actor_username', 'action',
            'entity_label', 'details', 'source',
        )
    )

    for entry in raw:
        label, color = _ACTION_LABELS.get(entry['action'], (entry['action'], '#374151'))
        entry['action_label'] = label
        entry['action_color'] = color

        rows = []
        for key, value in (entry.get('details') or {}).items():
            display_key = _KEY_LABELS.get(key, key)
            if isinstance(value, dict) and 'antes' in value and 'después' in value:
                rows.append({
                    'key':       display_key,
                    'is_change': True,
                    'before':    _fmt(value['antes']),
                    'after':     _fmt(value['después']),
                })
            else:
                rows.append({
                    'key':       display_key,
                    'is_change': False,
                    'value':     _fmt(value),
                })
        entry['detail_rows'] = rows

    return raw
