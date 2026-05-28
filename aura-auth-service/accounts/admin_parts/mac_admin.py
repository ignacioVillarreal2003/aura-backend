"""Admin views for MAC (Mandatory Access Control) — Classification Levels,
Compartments, Document Collections, and User MAC profiles.

All data comes from the Document Collection service REST API via mac_client.
No Django ORM models are used for MAC data.
"""

import json
import logging

from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.urls import path, reverse

from accounts.admin_parts.common import _is_super_admin_user, _is_admin_or_super_user
from accounts.admin_parts.utils.audit import log_audit
from accounts.services.mac_client import MacServiceError, mac_client

logger = logging.getLogger(__name__)


# ── helpers ───────────────────────────────────────────────────────────────────

def _check_superadmin(request):
    if not _is_super_admin_user(request.user):
        raise PermissionDenied


def _check_admin_or_superadmin(request):
    if not _is_admin_or_super_user(request.user):
        raise PermissionDenied


def _ctx(request, **extra):
    return {**admin.site.each_context(request), **extra}


def _get_level_doc_ids(level_id):
    """Return set of document IDs in any collection at this classification level."""
    from django.db import connections
    try:
        with connections['aura_db'].cursor() as cursor:
            cursor.execute(
                """
                SELECT DISTINCT dc_doc.document_id
                FROM document_in_document_collection dc_doc
                JOIN document_collection dc ON dc_doc.document_collection_id = dc.id
                WHERE dc.classification_level_id = %s
                  AND dc_doc.deleted_at IS NULL
                  AND dc.deleted_at IS NULL
                """,
                [level_id],
            )
            return {row[0] for row in cursor.fetchall()}
    except Exception:
        return set()


def _get_comp_doc_ids(compartment_id):
    """Return set of document IDs in any collection that has this compartment."""
    from django.db import connections
    try:
        with connections['aura_db'].cursor() as cursor:
            cursor.execute(
                """
                SELECT DISTINCT dc_doc.document_id
                FROM document_in_document_collection dc_doc
                JOIN document_collection dc ON dc_doc.document_collection_id = dc.id
                JOIN document_collection_compartment dcc
                  ON dcc.document_collection_id = dc.id
                WHERE dcc.compartment_id = %s
                  AND dc_doc.deleted_at IS NULL
                  AND dc.deleted_at IS NULL
                """,
                [compartment_id],
            )
            return {row[0] for row in cursor.fetchall()}
    except Exception:
        return set()


def _get_or_create_admin_collection_for_level(user, level_id, level_name):
    """Find or create the dedicated admin collection for a classification level."""
    admin_name = f'__admin_level_{level_id}__'
    try:
        collections = mac_client.list_document_collections(user)
        for col in collections:
            if col.get('name') == admin_name:
                return col
        return mac_client.create_document_collection(
            user, admin_name,
            classification_level_id=level_id,
            compartment_ids=[],
        )
    except MacServiceError:
        raise


def _get_or_create_admin_collection_for_comp(user, compartment_id):
    """Find or create the dedicated admin collection for a compartment."""
    admin_name = f'__admin_comp_{compartment_id}__'
    try:
        collections = mac_client.list_document_collections(user)
        for col in collections:
            if col.get('name') == admin_name:
                return col
        return mac_client.create_document_collection(
            user, admin_name,
            classification_level_id=None,
            compartment_ids=[compartment_id],
        )
    except MacServiceError:
        raise


def _remove_doc_from_level_collections(user, doc_id, level_id):
    """Remove a document from all collections at the given classification level."""
    from django.db import connections
    try:
        with connections['aura_db'].cursor() as cursor:
            cursor.execute(
                """
                SELECT dc_doc.document_collection_id
                FROM document_in_document_collection dc_doc
                JOIN document_collection dc ON dc_doc.document_collection_id = dc.id
                WHERE dc_doc.document_id = %s
                  AND dc.classification_level_id = %s
                  AND dc_doc.deleted_at IS NULL
                  AND dc.deleted_at IS NULL
                """,
                [doc_id, level_id],
            )
            col_ids = [row[0] for row in cursor.fetchall()]
    except Exception:
        col_ids = []
    errors = []
    for col_id in col_ids:
        try:
            mac_client.remove_document_from_collection(user, col_id, doc_id)
        except MacServiceError as exc:
            errors.append(str(exc))
    return errors


def _remove_doc_from_comp_collections(user, doc_id, compartment_id):
    """Remove a document from all collections that have the given compartment."""
    from django.db import connections
    try:
        with connections['aura_db'].cursor() as cursor:
            cursor.execute(
                """
                SELECT dc_doc.document_collection_id
                FROM document_in_document_collection dc_doc
                JOIN document_collection dc ON dc_doc.document_collection_id = dc.id
                JOIN document_collection_compartment dcc
                  ON dcc.document_collection_id = dc.id
                WHERE dc_doc.document_id = %s
                  AND dcc.compartment_id = %s
                  AND dc_doc.deleted_at IS NULL
                  AND dc.deleted_at IS NULL
                """,
                [doc_id, compartment_id],
            )
            col_ids = [row[0] for row in cursor.fetchall()]
    except Exception:
        col_ids = []
    errors = []
    for col_id in col_ids:
        try:
            mac_client.remove_document_from_collection(user, col_id, doc_id)
        except MacServiceError as exc:
            errors.append(str(exc))
    return errors


# ── Classification Levels views ───────────────────────────────────────────────

def _cl_list_view(request):
    _check_superadmin(request)

    if request.method == 'POST':
        action = request.POST.get('action', '')
        level_id_raw = request.POST.get('level_id', '').strip()
        try:
            moved_id = int(level_id_raw)
        except (ValueError, TypeError):
            messages.error(request, 'ID inválido.')
            return redirect(reverse('admin:mac_classification_levels_list'))

        try:
            levels = mac_client.list_classification_levels(request.user)
        except MacServiceError as exc:
            messages.error(request, str(exc))
            return redirect(reverse('admin:mac_classification_levels_list'))

        sorted_levels = sorted(levels, key=lambda x: x.get('rank', 0))
        idx = next((i for i, l in enumerate(sorted_levels) if l['id'] == moved_id), None)

        if idx is None:
            messages.error(request, 'Nivel no encontrado.')
        elif action == 'move_up' and idx == 0:
            pass
        elif action == 'move_down' and idx == len(sorted_levels) - 1:
            pass
        else:
            if action == 'move_up':
                sorted_levels[idx], sorted_levels[idx - 1] = sorted_levels[idx - 1], sorted_levels[idx]
            else:
                sorted_levels[idx], sorted_levels[idx + 1] = sorted_levels[idx + 1], sorted_levels[idx]
            try:
                changing = [
                    (new_rank, level)
                    for new_rank, level in enumerate(sorted_levels, start=1)
                    if level.get('rank') != new_rank
                ]
                if changing:
                    temp_base = max(l.get('rank', 0) for l in sorted_levels) + 100
                    for i, (_, level) in enumerate(changing):
                        mac_client.update_classification_level(request.user, level['id'], rank=temp_base + i)
                    for new_rank, level in changing:
                        mac_client.update_classification_level(request.user, level['id'], rank=new_rank)
                messages.success(request, 'Orden actualizado.')
            except MacServiceError as exc:
                messages.error(request, str(exc))

        return redirect(reverse('admin:mac_classification_levels_list'))

    try:
        levels = mac_client.list_classification_levels(request.user)
    except MacServiceError as exc:
        messages.error(request, str(exc))
        levels = []

    levels = sorted(levels, key=lambda x: x.get('rank', 0), reverse=True)

    ctx = _ctx(
        request,
        title='Niveles',
        levels=levels,
    )
    return TemplateResponse(request, 'admin/mac/classification_levels/list.html', ctx)


def _cl_create_view(request):
    _check_superadmin(request)

    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        description = request.POST.get('description', '').strip()
        result = None
        if not name:
            messages.error(request, 'El nombre es obligatorio.')
            return redirect(reverse('admin:mac_classification_levels_create'))
        try:
            existing = mac_client.list_classification_levels(request.user)
            next_rank = max((l.get('rank', 0) for l in existing), default=0) + 1
            result = mac_client.create_classification_level(request.user, name, next_rank, description)
            messages.success(request, f'Nivel "{name}" creado.')
            log_audit(
                actor=request.user, action='CREATE',
                entity_type='classification_level',
                entity_id=result.get('id') if result else None,
                entity_label=name,
                details={'rank': next_rank, 'description': description},
            )
        except MacServiceError as exc:
            messages.error(request, str(exc))
            return redirect(reverse('admin:mac_classification_levels_create'))

        if '_addanother' in request.POST:
            return redirect(reverse('admin:mac_classification_levels_create'))
        elif '_continue' in request.POST and result:
            return redirect(reverse('admin:mac_classification_levels_edit', args=[result['id']]))
        return redirect(reverse('admin:mac_classification_levels_list'))

    ctx = _ctx(request, title='Agregar Nivel')
    return TemplateResponse(request, 'admin/mac/classification_levels/create.html', ctx)


def _cl_edit_view(request, level_id):
    _check_superadmin(request)

    from accounts.models import User as AuthUser
    from documents.models import Document
    from django.db import connections

    try:
        level = mac_client.get_classification_level(request.user, level_id)
    except MacServiceError as exc:
        messages.error(request, str(exc))
        return redirect(reverse('admin:mac_classification_levels_list'))

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'update_all':
            name = request.POST.get('name', '').strip()
            description = request.POST.get('description', '').strip()
            new_user_ids = set(int(uid) for uid in request.POST.getlist('user_ids') if uid)
            new_doc_ids = set(int(d) for d in request.POST.getlist('doc_ids') if d)
            errors = []

            if not name:
                errors.append('El nombre es obligatorio.')
            else:
                try:
                    mac_client.update_classification_level(request.user, level_id, name=name, description=description)
                    log_audit(actor=request.user, action='UPDATE',
                              entity_type='classification_level', entity_id=level_id,
                              entity_label=name, details={'name': name, 'description': description})
                except MacServiceError as exc:
                    errors.append(str(exc))

            try:
                with connections['aura_db'].cursor() as cursor:
                    cursor.execute('SELECT user_id FROM user_clearance WHERE classification_level_id = %s', [level_id])
                    current_ids = {row[0] for row in cursor.fetchall()}
            except Exception:
                current_ids = set()
            try:
                with connections['aura_db'].cursor() as cursor:
                    cursor.execute('SELECT user_id FROM user_clearance WHERE classification_level_id != %s', [level_id])
                    other_level_ids = {row[0] for row in cursor.fetchall()}
            except Exception:
                other_level_ids = set()
            for uid in new_user_ids - current_ids:
                if uid in other_level_ids:
                    continue
                try:
                    mac_client.set_user_clearance(request.user, uid, level_id)
                except MacServiceError as exc:
                    errors.append(str(exc))
            for uid in current_ids - new_user_ids:
                try:
                    mac_client.delete_user_clearance(request.user, uid)
                except MacServiceError as exc:
                    errors.append(str(exc))

            current_doc_ids = _get_level_doc_ids(level_id)
            to_add = new_doc_ids - current_doc_ids
            to_remove = current_doc_ids - new_doc_ids
            if to_add:
                try:
                    admin_col = _get_or_create_admin_collection_for_level(request.user, level_id, name or level.get('name', ''))
                    for doc_id in to_add:
                        try:
                            mac_client.add_document_to_collection(request.user, admin_col['id'], doc_id)
                        except MacServiceError as exc:
                            errors.append(str(exc))
                except MacServiceError as exc:
                    errors.append(str(exc))
            for doc_id in to_remove:
                errors.extend(_remove_doc_from_level_collections(request.user, doc_id, level_id))

            if errors:
                for e in errors:
                    messages.error(request, e)
            else:
                messages.success(request, 'Nivel actualizado correctamente.')

            if '_addanother' in request.POST:
                return redirect(reverse('admin:mac_classification_levels_create'))
            elif '_continue' in request.POST:
                return redirect(reverse('admin:mac_classification_levels_edit', args=[level_id]))
            else:
                return redirect(reverse('admin:mac_classification_levels_list'))

        elif action == 'delete':
            try:
                mac_client.delete_classification_level(request.user, level_id)
                messages.success(request, 'Nivel eliminado.')
                log_audit(actor=request.user, action='DELETE',
                          entity_type='classification_level', entity_id=level_id,
                          entity_label=level.get('name', str(level_id)))
                return redirect(reverse('admin:mac_classification_levels_list'))
            except MacServiceError as exc:
                messages.error(request, str(exc))
                return redirect(reverse('admin:mac_classification_levels_edit', args=[level_id]))

    try:
        with connections['aura_db'].cursor() as cursor:
            cursor.execute(
                'SELECT user_id FROM user_clearance WHERE classification_level_id = %s',
                [level_id],
            )
            assigned_ids = {row[0] for row in cursor.fetchall()}
    except Exception:
        assigned_ids = set()

    try:
        with connections['aura_db'].cursor() as cursor:
            cursor.execute(
                'SELECT user_id FROM user_clearance WHERE classification_level_id != %s',
                [level_id],
            )
            blocked_ids = {row[0] for row in cursor.fetchall()}
    except Exception:
        blocked_ids = set()

    all_users = list(
        AuthUser.objects.filter(deleted_at__isnull=True, status='active').order_by('username')
    )

    assigned_doc_ids = _get_level_doc_ids(level_id)
    all_docs = list(Document.objects.filter(deleted_at__isnull=True).order_by('name'))

    ctx = _ctx(
        request,
        title=f"Nivel - {level.get('name', '')}",
        level=level,
        users_json=json.dumps([
            {
                'id': str(u.pk),
                'label': f"{u.username} ({u.email})",
                'blocked': u.pk in blocked_ids,
            }
            for u in all_users
        ]),
        assigned_ids_json=json.dumps([str(uid) for uid in assigned_ids]),
        docs_json=json.dumps([
            {'id': str(d.pk), 'label': d.name}
            for d in all_docs
        ]),
        assigned_doc_ids_json=json.dumps([str(did) for did in assigned_doc_ids]),
    )
    return TemplateResponse(request, 'admin/mac/classification_levels/edit.html', ctx)


# ── Compartments views ────────────────────────────────────────────────────────

def _comp_list_view(request):
    _check_superadmin(request)

    try:
        compartments = mac_client.list_compartments(request.user)
    except MacServiceError as exc:
        messages.error(request, str(exc))
        compartments = []

    ctx = _ctx(
        request,
        title='Agrupaciones',
        compartments=compartments,
    )
    return TemplateResponse(request, 'admin/mac/compartments/list.html', ctx)


def _comp_create_view(request):
    _check_superadmin(request)

    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        description = request.POST.get('description', '').strip()
        result = None
        if not name:
            messages.error(request, 'El nombre es obligatorio.')
            return redirect(reverse('admin:mac_compartments_create'))
        try:
            result = mac_client.create_compartment(request.user, name, description)
            messages.success(request, f'Agrupación "{name}" creada.')
            log_audit(
                actor=request.user, action='CREATE',
                entity_type='compartment',
                entity_id=result.get('id') if result else None,
                entity_label=name,
                details={'description': description} if description else None,
            )
        except MacServiceError as exc:
            messages.error(request, str(exc))
            return redirect(reverse('admin:mac_compartments_create'))

        if '_addanother' in request.POST:
            return redirect(reverse('admin:mac_compartments_create'))
        elif '_continue' in request.POST and result:
            return redirect(reverse('admin:mac_compartments_edit', args=[result['id']]))
        return redirect(reverse('admin:mac_compartments_list'))

    ctx = _ctx(request, title='Agregar Agrupación')
    return TemplateResponse(request, 'admin/mac/compartments/create.html', ctx)


def _comp_edit_view(request, compartment_id):
    _check_superadmin(request)

    from accounts.models import User as AuthUser
    from documents.models import Document
    from django.db import connections

    try:
        compartment = mac_client.get_compartment(request.user, compartment_id)
    except MacServiceError as exc:
        messages.error(request, str(exc))
        return redirect(reverse('admin:mac_compartments_list'))

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'update_all':
            name = request.POST.get('name', '').strip()
            description = request.POST.get('description', '').strip()
            new_user_ids = set(int(uid) for uid in request.POST.getlist('user_ids') if uid)
            new_doc_ids = set(int(d) for d in request.POST.getlist('doc_ids') if d)
            errors = []

            if not name:
                errors.append('El nombre es obligatorio.')
            else:
                try:
                    mac_client.update_compartment(request.user, compartment_id,
                                                  name=name, description=description)
                    log_audit(actor=request.user, action='UPDATE',
                              entity_type='compartment', entity_id=compartment_id,
                              entity_label=name,
                              details={'name': name, 'description': description})
                except MacServiceError as exc:
                    errors.append(str(exc))

            try:
                with connections['aura_db'].cursor() as cursor:
                    cursor.execute(
                        'SELECT user_id FROM user_compartment WHERE compartment_id = %s',
                        [compartment_id],
                    )
                    current_ids = {row[0] for row in cursor.fetchall()}
            except Exception:
                current_ids = set()
            added_users = new_user_ids - current_ids
            removed_users = current_ids - new_user_ids
            for uid in added_users:
                try:
                    mac_client.add_user_compartment(request.user, uid, compartment_id)
                except MacServiceError as exc:
                    errors.append(str(exc))
            for uid in removed_users:
                try:
                    mac_client.remove_user_compartment(request.user, uid, compartment_id)
                except MacServiceError as exc:
                    errors.append(str(exc))

            current_doc_ids = _get_comp_doc_ids(compartment_id)
            to_add = new_doc_ids - current_doc_ids
            to_remove = current_doc_ids - new_doc_ids
            if to_add:
                try:
                    admin_col = _get_or_create_admin_collection_for_comp(
                        request.user, compartment_id
                    )
                    for doc_id in to_add:
                        try:
                            mac_client.add_document_to_collection(request.user, admin_col['id'], doc_id)
                        except MacServiceError as exc:
                            errors.append(str(exc))
                except MacServiceError as exc:
                    errors.append(str(exc))
            for doc_id in to_remove:
                errors.extend(_remove_doc_from_comp_collections(request.user, doc_id, compartment_id))

            if errors:
                for e in errors:
                    messages.error(request, e)
            else:
                messages.success(request, 'Agrupación actualizada correctamente.')
                log_audit(actor=request.user, action='UPDATE',
                          entity_type='compartment', entity_id=compartment_id,
                          entity_label=name or compartment.get('name', str(compartment_id)),
                          details={
                              'name': name, 'description': description,
                              'users_added': list(added_users), 'users_removed': list(removed_users),
                              'docs_added': list(to_add), 'docs_removed': list(to_remove),
                          })

            if '_addanother' in request.POST:
                return redirect(reverse('admin:mac_compartments_create'))
            elif '_continue' in request.POST:
                return redirect(reverse('admin:mac_compartments_edit', args=[compartment_id]))
            else:
                return redirect(reverse('admin:mac_compartments_list'))

        elif action == 'delete':
            try:
                mac_client.delete_compartment(request.user, compartment_id)
                messages.success(request, 'Agrupación eliminada.')
                log_audit(actor=request.user, action='DELETE',
                          entity_type='compartment', entity_id=compartment_id,
                          entity_label=compartment.get('name', str(compartment_id)))
                return redirect(reverse('admin:mac_compartments_list'))
            except MacServiceError as exc:
                messages.error(request, str(exc))
                return redirect(reverse('admin:mac_compartments_edit', args=[compartment_id]))

    try:
        with connections['aura_db'].cursor() as cursor:
            cursor.execute(
                'SELECT user_id FROM user_compartment WHERE compartment_id = %s',
                [compartment_id],
            )
            assigned_ids = {row[0] for row in cursor.fetchall()}
    except Exception:
        assigned_ids = set()

    all_users = list(
        AuthUser.objects.filter(deleted_at__isnull=True, status='active').order_by('username')
    )

    assigned_doc_ids = _get_comp_doc_ids(compartment_id)
    all_docs = list(Document.objects.filter(deleted_at__isnull=True).order_by('name'))

    ctx = _ctx(
        request,
        title=f"Agrupación - {compartment.get('name', '')}",
        compartment=compartment,
        users_json=json.dumps([
            {'id': str(u.pk), 'label': f"{u.username} ({u.email})"}
            for u in all_users
        ]),
        assigned_ids_json=json.dumps([str(uid) for uid in assigned_ids]),
        docs_json=json.dumps([
            {'id': str(d.pk), 'label': d.name}
            for d in all_docs
        ]),
        assigned_doc_ids_json=json.dumps([str(did) for did in assigned_doc_ids]),
    )
    return TemplateResponse(request, 'admin/mac/compartments/edit.html', ctx)


# ── User MAC profile view ─────────────────────────────────────────────────────

def _user_mac_view(request, user_id):
    _check_superadmin(request)

    from accounts.models import User as AuthUser

    try:
        target_user = AuthUser.objects.get(pk=user_id)
    except AuthUser.DoesNotExist:
        messages.error(request, 'Usuario no encontrado.')
        return redirect(reverse('admin:accounts_user_changelist'))

    try:
        levels = mac_client.list_classification_levels(request.user)
        levels = sorted(levels, key=lambda x: x.get('rank', 0))
    except MacServiceError as exc:
        messages.error(request, str(exc))
        levels = []

    try:
        all_compartments = mac_client.list_compartments(request.user)
    except MacServiceError as exc:
        messages.error(request, str(exc))
        all_compartments = []

    try:
        auth_data = mac_client.get_user_authorization(request.user, user_id)
    except MacServiceError:
        auth_data = {}

    clearance = auth_data.get('clearance') if auth_data else None
    user_compartments = auth_data.get('compartments', []) if auth_data else []

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'set_clearance':
            cl_id_raw = request.POST.get('classification_level_id', '').strip()
            if not cl_id_raw:
                messages.error(request, 'Seleccione un nivel de clasificación.')
            else:
                try:
                    mac_client.set_user_clearance(request.user, user_id, int(cl_id_raw))
                    messages.success(request, 'Habilitación actualizada correctamente.')
                    log_audit(
                        actor=request.user, action='UPDATE',
                        entity_type='user_clearance',
                        entity_id=user_id,
                        entity_label=target_user.username,
                        details={'classification_level_id': int(cl_id_raw)},
                    )
                except (ValueError, TypeError):
                    messages.error(request, 'ID inválido.')
                except MacServiceError as exc:
                    messages.error(request, str(exc))

        elif action == 'delete_clearance':
            try:
                mac_client.delete_user_clearance(request.user, user_id)
                messages.success(request, 'Habilitación eliminada.')
                log_audit(
                    actor=request.user, action='DELETE',
                    entity_type='user_clearance',
                    entity_id=user_id,
                    entity_label=target_user.username,
                )
            except MacServiceError as exc:
                messages.error(request, str(exc))

        elif action == 'add_compartment':
            comp_id_raw = request.POST.get('compartment_id', '').strip()
            if not comp_id_raw:
                messages.error(request, 'Seleccione un compartimento.')
            else:
                try:
                    mac_client.add_user_compartment(request.user, user_id, int(comp_id_raw))
                    messages.success(request, 'Compartimento agregado.')
                    log_audit(
                        actor=request.user, action='UPDATE',
                        entity_type='user_compartment',
                        entity_id=user_id,
                        entity_label=target_user.username,
                        details={'added_compartment_id': int(comp_id_raw)},
                    )
                except (ValueError, TypeError):
                    messages.error(request, 'ID inválido.')
                except MacServiceError as exc:
                    messages.error(request, str(exc))

        elif action == 'remove_compartment':
            comp_id_raw = request.POST.get('compartment_id', '').strip()
            if comp_id_raw:
                try:
                    mac_client.remove_user_compartment(request.user, user_id, int(comp_id_raw))
                    messages.success(request, 'Compartimento removido.')
                    log_audit(
                        actor=request.user, action='UPDATE',
                        entity_type='user_compartment',
                        entity_id=user_id,
                        entity_label=target_user.username,
                        details={'removed_compartment_id': int(comp_id_raw)},
                    )
                except (ValueError, TypeError):
                    messages.error(request, 'ID inválido.')
                except MacServiceError as exc:
                    messages.error(request, str(exc))

        return redirect(reverse('admin:mac_user_mac', args=[user_id]))

    assigned_comp_ids = {
        uc.get('compartment', {}).get('id') for uc in user_compartments
    }
    available_compartments = [
        c for c in all_compartments if c.get('id') not in assigned_comp_ids
    ]

    ctx = _ctx(
        request,
        title=f'Perfil MAC — {target_user.username}',
        subtitle='Habilitación y compartimentos del usuario',
        target_user=target_user,
        clearance=clearance,
        user_compartments=user_compartments,
        levels=levels,
        available_compartments=available_compartments,
    )
    return TemplateResponse(request, 'admin/mac/user_mac.html', ctx)


# ── URL registration ──────────────────────────────────────────────────────────

_prev_get_urls = admin.site.get_urls


def _mac_get_urls(self):
    urls = _prev_get_urls()
    custom_urls = [
        # Classification Levels
        path(
            'mac/classification-levels/',
            self.admin_view(_cl_list_view),
            name='mac_classification_levels_list',
        ),
        path(
            'mac/classification-levels/create/',
            self.admin_view(_cl_create_view),
            name='mac_classification_levels_create',
        ),
        path(
            'mac/classification-levels/<int:level_id>/edit/',
            self.admin_view(_cl_edit_view),
            name='mac_classification_levels_edit',
        ),
        # Compartments
        path(
            'mac/compartments/',
            self.admin_view(_comp_list_view),
            name='mac_compartments_list',
        ),
        path(
            'mac/compartments/create/',
            self.admin_view(_comp_create_view),
            name='mac_compartments_create',
        ),
        path(
            'mac/compartments/<int:compartment_id>/edit/',
            self.admin_view(_comp_edit_view),
            name='mac_compartments_edit',
        ),
        # User MAC
        path(
            'mac/user/<int:user_id>/',
            self.admin_view(_user_mac_view),
            name='mac_user_mac',
        ),
    ]
    return custom_urls + urls


admin.site.get_urls = _mac_get_urls.__get__(admin.site, admin.AdminSite)
