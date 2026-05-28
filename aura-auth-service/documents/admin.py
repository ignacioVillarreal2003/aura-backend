"""Django Admin for Document model."""

import json
import re

from django import forms
from django.contrib import admin, messages
from django.contrib.admin import helpers
from django.contrib.admin.exceptions import DisallowedModelAdminToField
from django.contrib.admin.options import IS_POPUP_VAR, TO_FIELD_VAR
from django.core.exceptions import PermissionDenied
from django.db import connections, router, transaction
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.utils.translation import gettext as _
from django.utils.html import format_html
from django.conf import settings

from accounts.admin_parts.utils.audit import log_audit, _is_admin_or_super_user
from accounts.services.mac_client import mac_client
from documents.models import Document
from documents.services.document_processing_client import (
    DocumentProcessingServiceError,
    create_document_from_admin,
)

_ADMIN_LEVEL_RE = re.compile(r'^__admin_level_(\d+)__$')
_ADMIN_COMP_RE = re.compile(r'^__admin_comp_(\d+)__$')

# ── Local meta table (default DB) — immune to processing-service overwrites ───

_meta_table_ensured = False


def _ensure_meta_table():
    global _meta_table_ensured
    if _meta_table_ensured:
        return
    try:
        with connections['default'].cursor() as cursor:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS document_admin_meta (
                    document_id BIGINT PRIMARY KEY,
                    admin_name  VARCHAR(255) NOT NULL DEFAULT '',
                    admin_description TEXT NOT NULL DEFAULT ''
                )
            """)
        _meta_table_ensured = True
    except Exception:
        pass


def _save_doc_meta(doc_id, name, description):
    _ensure_meta_table()
    try:
        with connections['default'].cursor() as cursor:
            cursor.execute("""
                INSERT INTO document_admin_meta (document_id, admin_name, admin_description)
                VALUES (%s, %s, %s)
                ON CONFLICT (document_id) DO UPDATE
                SET admin_name = EXCLUDED.admin_name,
                    admin_description = EXCLUDED.admin_description
            """, [doc_id, name or '', description or ''])
    except Exception:
        pass


def _get_doc_meta(doc_id):
    _ensure_meta_table()
    try:
        with connections['default'].cursor() as cursor:
            cursor.execute(
                "SELECT admin_name, admin_description FROM document_admin_meta WHERE document_id = %s",
                [doc_id],
            )
            row = cursor.fetchone()
            return {'name': row[0], 'description': row[1]} if row else None
    except Exception:
        return None


def _batch_get_doc_meta_all():
    _ensure_meta_table()
    try:
        with connections['default'].cursor() as cursor:
            cursor.execute(
                "SELECT document_id, admin_name, admin_description FROM document_admin_meta"
            )
            return {row[0]: {'name': row[1], 'description': row[2]} for row in cursor.fetchall()}
    except Exception:
        return {}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _ensure_admin_chat(actor_user_id: int) -> int:
    admin_chat_id = settings.ADMIN_CHAT_ID
    with connections['aura_db'].cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO chat (id, name, created_by)
            VALUES (%s, %s, %s)
            ON CONFLICT (id) DO NOTHING
            """,
            [admin_chat_id, 'Carga administrativa de documentos', actor_user_id],
        )
    return admin_chat_id


def _get_doc_mac_assignments(doc_id):
    """Return (current_level_id, current_comp_ids_set) for a document."""
    current_level_id = None
    current_comp_ids = set()
    try:
        with connections['aura_db'].cursor() as cursor:
            cursor.execute("""
                SELECT dc.classification_level_id
                FROM document_in_document_collection dic
                JOIN document_collection dc ON dic.document_collection_id = dc.id
                WHERE dic.document_id = %s
                  AND dic.deleted_at IS NULL
                  AND dc.deleted_at IS NULL
                  AND dc.classification_level_id IS NOT NULL
                LIMIT 1
            """, [doc_id])
            row = cursor.fetchone()
            if row:
                current_level_id = row[0]
            cursor.execute("""
                SELECT DISTINCT dcc.compartment_id
                FROM document_in_document_collection dic
                JOIN document_collection dc ON dic.document_collection_id = dc.id
                JOIN document_collection_compartment dcc ON dcc.document_collection_id = dc.id
                WHERE dic.document_id = %s
                  AND dic.deleted_at IS NULL
                  AND dc.deleted_at IS NULL
            """, [doc_id])
            current_comp_ids = {row[0] for row in cursor.fetchall()}
    except Exception:
        pass
    return current_level_id, current_comp_ids


def _db_ensure_level_collection(level_id, actor_user_id):
    """Find or create the admin collection for a level, writing directly to the DB."""
    admin_name = f'__admin_level_{level_id}__'
    with connections['aura_db'].cursor() as cursor:
        cursor.execute(
            "SELECT id FROM document_collection WHERE name = %s AND deleted_at IS NULL LIMIT 1",
            [admin_name],
        )
        row = cursor.fetchone()
        if row:
            return row[0]
        cursor.execute(
            """
            INSERT INTO document_collection (name, classification_level_id, created_by, created_at)
            VALUES (%s, %s, %s, NOW()) RETURNING id
            """,
            [admin_name, level_id, actor_user_id],
        )
        return cursor.fetchone()[0]


def _db_ensure_comp_collection(compartment_id, actor_user_id):
    """Find or create the admin collection for a compartment, writing directly to the DB."""
    admin_name = f'__admin_comp_{compartment_id}__'
    with connections['aura_db'].cursor() as cursor:
        cursor.execute(
            "SELECT id FROM document_collection WHERE name = %s AND deleted_at IS NULL LIMIT 1",
            [admin_name],
        )
        row = cursor.fetchone()
        if row:
            return row[0]
        cursor.execute(
            """
            INSERT INTO document_collection (name, classification_level_id, created_by, created_at)
            VALUES (%s, NULL, %s, NOW()) RETURNING id
            """,
            [admin_name, actor_user_id],
        )
        col_id = cursor.fetchone()[0]
        cursor.execute(
            """
            INSERT INTO document_collection_compartment
                (document_collection_id, compartment_id, created_by, created_at)
            VALUES (%s, %s, %s, NOW())
            ON CONFLICT ON CONSTRAINT doc_coll_comp_coll_compartment_unique DO NOTHING
            """,
            [col_id, compartment_id, actor_user_id],
        )
        return col_id


def _db_link_doc(collection_id, document_id, actor_user_id):
    """Link a document to a collection (idempotent) via direct DB insert."""
    with connections['aura_db'].cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO document_in_document_collection
                (document_collection_id, document_id, created_by, created_at)
            SELECT %s, %s, %s, NOW()
            WHERE NOT EXISTS (
                SELECT 1 FROM document_in_document_collection
                WHERE document_collection_id = %s AND document_id = %s AND deleted_at IS NULL
            )
            """,
            [collection_id, document_id, actor_user_id, collection_id, document_id],
        )


def _db_unlink_doc_from_level(doc_id, level_id, actor_user_id):
    """Soft-delete all active links from a document to collections at a given level."""
    with connections['aura_db'].cursor() as cursor:
        cursor.execute(
            """
            UPDATE document_in_document_collection
            SET deleted_at = NOW(), deleted_by = %s
            WHERE document_id = %s
              AND deleted_at IS NULL
              AND document_collection_id IN (
                SELECT id FROM document_collection
                WHERE classification_level_id = %s AND deleted_at IS NULL
              )
            """,
            [actor_user_id, doc_id, level_id],
        )


def _db_unlink_doc_from_comp(doc_id, compartment_id, actor_user_id):
    """Soft-delete all active links from a document to collections for a given compartment."""
    with connections['aura_db'].cursor() as cursor:
        cursor.execute(
            """
            UPDATE document_in_document_collection
            SET deleted_at = NOW(), deleted_by = %s
            WHERE document_id = %s
              AND deleted_at IS NULL
              AND document_collection_id IN (
                SELECT dc.id FROM document_collection dc
                JOIN document_collection_compartment dcc ON dcc.document_collection_id = dc.id
                WHERE dcc.compartment_id = %s AND dc.deleted_at IS NULL
              )
            """,
            [actor_user_id, doc_id, compartment_id],
        )


# ── Forms ─────────────────────────────────────────────────────────────────────

class DocumentUploadForm(forms.ModelForm):
    name = forms.CharField(max_length=255, label='Nombre')
    description = forms.CharField(
        label='Descripción', required=False,
        widget=forms.Textarea(attrs={'rows': 4}),
    )
    raw_collection = forms.FileField(label='Archivo', required=True)

    class Meta:
        model = Document
        fields = []

    def _post_clean(self):
        pass


class DocumentChangeForm(forms.ModelForm):
    name = forms.CharField(max_length=255, label='Nombre')
    description = forms.CharField(
        label='Descripción', required=False,
        widget=forms.Textarea(attrs={'rows': 3}),
    )

    class Meta:
        model = Document
        fields = ['name', 'description']

    def _post_clean(self):
        pass


# ── Admin ─────────────────────────────────────────────────────────────────────

@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    change_form_template = 'admin/documents/document/change_form.html'
    list_display = (
        'name_display',
        'description_short',
        'size_display',
        'status_badge',
        'nivel_display',
        'agrupaciones_count',
        'created_by_display',
    )
    list_display_links = ('name_display',)
    list_filter = ()
    search_fields = ('name', 'description')
    readonly_fields = (
        'size_display',
        'status',
        'mime_type_display',
        'storage_url',
        'created_at',
        'created_by',
    )
    actions = None
    actions_selection_counter = False

    fieldsets = (
        ('Información Básica', {
            'fields': ('name', 'description', 'size_display', 'status', 'mime_type_display', 'storage_url'),
        }),
        ('Auditoría', {
            'fields': ('created_at', 'created_by'),
            'classes': ('collapse',),
        }),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).filter(deleted_at__isnull=True)

    def get_form(self, request, obj=None, **kwargs):
        return DocumentUploadForm if obj is None else DocumentChangeForm

    def get_fieldsets(self, request, obj=None):
        if obj is None:
            return (
                ('Subir documento', {
                    'fields': ('name', 'description', 'raw_collection'),
                }),
            )
        return self.fieldsets

    def has_module_permission(self, request):
        return _is_admin_or_super_user(request.user)

    def has_view_permission(self, request, obj=None):
        return _is_admin_or_super_user(request.user)

    def has_add_permission(self, request):
        return _is_admin_or_super_user(request.user)

    def has_change_permission(self, request, obj=None):
        return _is_admin_or_super_user(request.user)

    def has_delete_permission(self, request, obj=None):
        return _is_admin_or_super_user(request.user)

    def get_readonly_fields(self, request, obj=None):
        if obj is not None:
            return self.readonly_fields
        return ('id',)

    def get_object(self, request, object_id, from_field=None):
        """Patch name/description from local meta so form shows admin values."""
        obj = super().get_object(request, object_id, from_field)
        if obj is not None:
            meta = _get_doc_meta(obj.pk)
            if meta:
                obj.name = meta['name']
                obj.description = meta['description']
        return obj

    # ── List view ────────────────────────────────────────────────────────────

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context['title'] = 'Documentos'

        self._doc_meta_map = _batch_get_doc_meta_all()

        # Batch-fetch collection assignments using direct column queries.
        try:
            with connections['aura_db'].cursor() as cursor:
                cursor.execute("""
                    SELECT dic.document_id, MAX(dc.classification_level_id)
                    FROM document_in_document_collection dic
                    JOIN document_collection dc ON dic.document_collection_id = dc.id
                    WHERE dic.deleted_at IS NULL
                      AND dc.deleted_at IS NULL
                      AND dc.classification_level_id IS NOT NULL
                    GROUP BY dic.document_id
                """)
                level_ids_by_doc = {row[0]: row[1] for row in cursor.fetchall()}
                cursor.execute("""
                    SELECT dic.document_id, COUNT(DISTINCT dcc.compartment_id)
                    FROM document_in_document_collection dic
                    JOIN document_collection dc ON dic.document_collection_id = dc.id
                    JOIN document_collection_compartment dcc ON dcc.document_collection_id = dc.id
                    WHERE dic.deleted_at IS NULL
                      AND dc.deleted_at IS NULL
                    GROUP BY dic.document_id
                """)
                comp_counts = {row[0]: row[1] for row in cursor.fetchall()}
        except Exception:
            level_ids_by_doc = {}
            comp_counts = {}

        try:
            all_levels = mac_client.list_classification_levels(request.user)
            level_names = {l['id']: l['name'] for l in all_levels}
        except Exception:
            level_names = {}

        self._doc_level_names = {
            doc_id: level_names.get(lvl_id, str(lvl_id))
            for doc_id, lvl_id in level_ids_by_doc.items()
        }
        self._doc_comp_counts = comp_counts

        try:
            from accounts.models import User
            self._user_map = {u.pk: u.username for u in User.objects.only('id', 'username')}
        except Exception:
            self._user_map = {}

        return super().changelist_view(request, extra_context)

    # ── Change / add view ─────────────────────────────────────────────────────

    def changeform_view(self, request, object_id=None, form_url='', extra_context=None):
        extra_context = extra_context or {}

        if object_id:
            doc_id = int(object_id)

            # Title uses meta name when available.
            meta = _get_doc_meta(doc_id)
            if meta:
                display_name = meta['name']
            else:
                try:
                    display_name = Document.objects.get(pk=doc_id).name
                except Document.DoesNotExist:
                    display_name = str(doc_id)
            extra_context['title'] = f'Modificar documento - {display_name}'
            extra_context['subtitle'] = None

            # Current MAC assignments.
            current_level_id, current_comp_ids = _get_doc_mac_assignments(doc_id)

            try:
                all_levels = sorted(
                    mac_client.list_classification_levels(request.user),
                    key=lambda x: x.get('rank', 0),
                )
            except Exception:
                all_levels = []
            try:
                all_compartments = mac_client.list_compartments(request.user)
            except Exception:
                all_compartments = []

            extra_context.update({
                'current_level_id': str(current_level_id) if current_level_id else '',
                'levels_for_doc': all_levels,
                'compartments_json_doc': json.dumps([
                    {'id': str(c['id']), 'label': c['name']}
                    for c in all_compartments
                ]),
                'assigned_comp_ids_doc': json.dumps([str(c) for c in current_comp_ids]),
                'show_change_groups_panel': True,
            })

            # Handle change POST.
            if request.method == 'POST':
                name = request.POST.get('name', '').strip()
                description = request.POST.get('description', '') or ''

                if not name:
                    messages.error(request, 'El nombre es obligatorio.')
                    return HttpResponseRedirect(
                        reverse('admin:documents_document_change', args=[object_id])
                    )

                # Capture before-state for audit (meta already fetched above for title).
                prev_name = meta['name'] if meta else ''
                prev_description = (meta['description'] if meta else '') or ''

                # Save to local meta (survives processing-service overwrites).
                _save_doc_meta(doc_id, name, description)

                # Also update the document table directly.
                try:
                    with connections['aura_db'].cursor() as cursor:
                        cursor.execute(
                            'UPDATE document SET name = %s, description = %s WHERE id = %s',
                            [name, description, doc_id],
                        )
                except Exception:
                    pass

                # Level change (direct DB — API rejects None level or empty compartments).
                new_level_id_raw = request.POST.get('classification_level_id', '').strip()
                new_level_id = int(new_level_id_raw) if new_level_id_raw else None
                if new_level_id != current_level_id:
                    if current_level_id:
                        _db_unlink_doc_from_level(doc_id, current_level_id, request.user.pk)
                    if new_level_id:
                        col_id = _db_ensure_level_collection(new_level_id, request.user.pk)
                        _db_link_doc(col_id, doc_id, request.user.pk)

                # Compartments change (direct DB).
                new_comp_ids = set(int(c) for c in request.POST.getlist('compartment_ids') if c)
                for comp_id in new_comp_ids - current_comp_ids:
                    col_id = _db_ensure_comp_collection(comp_id, request.user.pk)
                    _db_link_doc(col_id, doc_id, request.user.pk)
                for comp_id in current_comp_ids - new_comp_ids:
                    _db_unlink_doc_from_comp(doc_id, comp_id, request.user.pk)

                # Build audit details — only include fields that actually changed.
                level_name_map = {l['id']: l['name'] for l in all_levels}
                comp_name_map = {c['id']: c['name'] for c in all_compartments}
                changes = {}
                if name != prev_name:
                    changes['nombre'] = {'antes': prev_name, 'después': name}
                if description != prev_description:
                    changes['descripción'] = {
                        'antes': prev_description or None,
                        'después': description or None,
                    }
                if new_level_id != current_level_id:
                    changes['nivel'] = {
                        'antes': level_name_map.get(current_level_id) if current_level_id else None,
                        'después': level_name_map.get(new_level_id) if new_level_id else None,
                    }
                if new_comp_ids != current_comp_ids:
                    changes['agrupaciones'] = {
                        'antes': sorted(comp_name_map.get(c, str(c)) for c in current_comp_ids),
                        'después': sorted(comp_name_map.get(c, str(c)) for c in new_comp_ids),
                    }

                log_audit(
                    actor=request.user, action='UPDATE',
                    entity_type='Document', entity_id=str(doc_id),
                    entity_label=f'{request.user.username} modificó documento {name}',
                    details=changes if changes else None,
                    source='admin', request=request,
                )
                messages.success(request, 'Documento actualizado correctamente.')

                if '_continue' in request.POST:
                    return HttpResponseRedirect(
                        reverse('admin:documents_document_change', args=[object_id])
                    )
                return HttpResponseRedirect(reverse('admin:documents_document_changelist'))

        else:
            # Add view context.
            try:
                all_levels = sorted(
                    mac_client.list_classification_levels(request.user),
                    key=lambda x: x.get('rank', 0),
                )
            except Exception:
                all_levels = []
            try:
                all_compartments_doc = mac_client.list_compartments(request.user)
            except Exception:
                all_compartments_doc = []
            extra_context.update({
                'levels_for_doc': all_levels,
                'compartments_json_doc': json.dumps([
                    {'id': str(c['id']), 'label': c['name']}
                    for c in all_compartments_doc
                ]),
                'show_groups_panel': True,
            })

        with transaction.atomic(using=router.db_for_write(self.model)):
            return self._changeform_view(request, object_id, form_url, extra_context)

    def _changeform_view(self, request, object_id, form_url, extra_context):
        if object_id is not None:
            return super()._changeform_view(request, object_id, form_url, extra_context)

        if request.method != 'POST':
            return super()._changeform_view(request, object_id, form_url, extra_context)

        to_field = request.POST.get(TO_FIELD_VAR, request.GET.get(TO_FIELD_VAR))
        if to_field and not self.to_field_allowed(request, to_field):
            raise DisallowedModelAdminToField('The field %s cannot be referenced.' % to_field)
        if not self.has_add_permission(request):
            raise PermissionDenied

        form_class = self.get_form(request, None)
        form = form_class(request.POST, request.FILES)

        if not form.is_valid():
            fieldsets = self.get_fieldsets(request, None)
            admin_form = helpers.AdminForm(form, list(fieldsets), {}, (), model_admin=self)
            context = {
                **self.admin_site.each_context(request),
                'title': _('Add %s') % self.opts.verbose_name,
                'subtitle': None,
                'adminform': admin_form,
                'object_id': None,
                'original': None,
                'is_popup': IS_POPUP_VAR in request.POST or IS_POPUP_VAR in request.GET,
                'to_field': to_field,
                'media': self.media + admin_form.media,
                'inline_admin_formsets': [],
                'errors': helpers.AdminErrorList(form, []),
                'preserved_filters': self.get_preserved_filters(request),
            }
            context.update(extra_context or {})
            return self.render_change_form(
                request, context, add=True, change=False, obj=None, form_url=form_url
            )

        raw_collection = form.cleaned_data['raw_collection']
        name_from_form = form.cleaned_data.get('name', '').strip()
        description_from_form = form.cleaned_data.get('description', '') or ''

        try:
            chat_id = _ensure_admin_chat(request.user.pk)
            response_payload = create_document_from_admin(
                raw_document=raw_collection,
                chat_id=chat_id,
                actor_user=request.user,
                name=name_from_form or None,
                description=description_from_form or None,
            )
        except DocumentProcessingServiceError as exc:
            form.add_error(None, str(exc))
            fieldsets = self.get_fieldsets(request, None)
            admin_form = helpers.AdminForm(form, list(fieldsets), {}, (), model_admin=self)
            context = {
                **self.admin_site.each_context(request),
                'title': _('Add %s') % self.opts.verbose_name,
                'subtitle': None,
                'adminform': admin_form,
                'object_id': None,
                'original': None,
                'is_popup': IS_POPUP_VAR in request.POST or IS_POPUP_VAR in request.GET,
                'to_field': to_field,
                'media': self.media + admin_form.media,
                'inline_admin_formsets': [],
                'errors': helpers.AdminErrorList(form, []),
                'preserved_filters': self.get_preserved_filters(request),
            }
            return self.render_change_form(
                request, context, add=True, change=False, obj=None, form_url=form_url
            )

        document_id = response_payload.get('id')

        # Save to local meta so processing-service overwrites don't affect us.
        if name_from_form or description_from_form:
            _save_doc_meta(document_id, name_from_form, description_from_form)
            # Best-effort update on aura_db too.
            try:
                with connections['aura_db'].cursor() as cursor:
                    cursor.execute(
                        'UPDATE document SET name = %s, description = %s WHERE id = %s',
                        [name_from_form, description_from_form, document_id],
                    )
            except Exception:
                pass

        try:
            new_object = Document.objects.get(pk=document_id)
        except Document.DoesNotExist:
            new_object = Document(pk=document_id, name=name_from_form)

        # Assign MAC groups (direct DB — API rejects None level or empty compartments).
        cl_id_raw = request.POST.get('classification_level_id', '').strip()
        if cl_id_raw:
            col_id = _db_ensure_level_collection(int(cl_id_raw), request.user.pk)
            _db_link_doc(col_id, document_id, request.user.pk)
        comp_ids_raw_list = [int(c) for c in request.POST.getlist('compartment_ids') if c]
        for comp_id_int in comp_ids_raw_list:
            col_id = _db_ensure_comp_collection(comp_id_int, request.user.pk)
            _db_link_doc(col_id, document_id, request.user.pk)

        # Build audit details with resolved names.
        try:
            _audit_levels = mac_client.list_classification_levels(request.user)
            _level_name_map = {l['id']: l['name'] for l in _audit_levels}
        except Exception:
            _level_name_map = {}
        try:
            _audit_comps = mac_client.list_compartments(request.user)
            _comp_name_map = {c['id']: c['name'] for c in _audit_comps}
        except Exception:
            _comp_name_map = {}

        doc_name = name_from_form or new_object.name
        audit_details = {'nombre': doc_name}
        if description_from_form:
            audit_details['descripción'] = description_from_form
        if cl_id_raw:
            audit_details['nivel'] = _level_name_map.get(int(cl_id_raw), cl_id_raw)
        if comp_ids_raw_list:
            audit_details['agrupaciones'] = [
                _comp_name_map.get(c, str(c)) for c in comp_ids_raw_list
            ]

        log_audit(
            actor=request.user, action='CREATE',
            entity_type='Document', entity_id=str(document_id),
            entity_label=f'{request.user.username} creó documento {doc_name}',
            details=audit_details,
            source='admin', request=request,
        )

        return self.response_add(request, new_object)

    # ── List display helpers ──────────────────────────────────────────────────

    def name_display(self, obj):
        meta = getattr(self, '_doc_meta_map', {}).get(obj.pk)
        return meta['name'] if meta else obj.name
    name_display.short_description = 'Nombre'
    name_display.admin_order_field = 'name'

    def description_short(self, obj):
        meta = getattr(self, '_doc_meta_map', {}).get(obj.pk)
        desc = meta['description'] if meta else obj.description
        if not desc:
            return '-'
        return desc[:80] + ('…' if len(desc) > 80 else '')
    description_short.short_description = 'Descripción'

    def size_display(self, obj):
        if not obj.file_size_bytes:
            return '-'
        size = float(obj.file_size_bytes)
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size < 1024.0:
                return f"{size:.2f} {unit}"
            size /= 1024.0
        return f"{size:.2f} PB"
    size_display.short_description = 'Tamaño'
    size_display.admin_order_field = 'file_size_bytes'

    def mime_type_display(self, obj):
        return obj.mime_type or '-'
    mime_type_display.short_description = 'Tipo'

    def status_badge(self, obj):
        status = (obj.status or '').lower()
        if status == 'processed':
            return format_html('<span style="color:#2e7d32;font-weight:600">&#10003; Procesado</span>')
        if status == 'failed':
            return format_html('<span style="color:#c62828;font-weight:600">&#10007; Fallido</span>')
        if status == 'uploaded':
            return format_html('<span style="color:#757575">&#9201; Cargado</span>')
        return format_html('<span style="color:#888">{}</span>', obj.status or '-')
    status_badge.short_description = 'Estado'

    def nivel_display(self, obj):
        name = getattr(self, '_doc_level_names', {}).get(obj.pk)
        if name:
            return format_html(
                '<span style="background-color:#417690;color:white;padding:3px 10px;border-radius:3px;">{}</span>',
                name,
            )
        return format_html('<span style="color:#bbb">—</span>')
    nivel_display.short_description = 'Nivel'

    def agrupaciones_count(self, obj):
        count = getattr(self, '_doc_comp_counts', {}).get(obj.pk, 0)
        return format_html(
            '<span style="background-color:#417690;color:white;padding:3px 10px;border-radius:3px;">{}</span>',
            count,
        )
    agrupaciones_count.short_description = 'Agrupaciones'

    def created_by_display(self, obj):
        if not obj.created_by:
            return '-'
        username = getattr(self, '_user_map', {}).get(obj.created_by)
        return username or str(obj.created_by)
    created_by_display.short_description = 'Subido por'

    def delete_model(self, request, obj):
        obj.soft_delete(deleted_by=request.user.pk)
        log_audit(
            actor=request.user, action='DELETE',
            entity_type='Document', entity_id=str(obj.pk),
            entity_label=obj.name,
            details={'deleted_at': str(obj.deleted_at)}, source='admin', request=request,
        )

    def delete_queryset(self, request, queryset):
        for obj in queryset:
            obj.soft_delete(deleted_by=request.user.pk)
            log_audit(
                actor=request.user, action='DELETE',
                entity_type='Document', entity_id=str(obj.pk),
                entity_label=obj.name,
                details={'deleted_at': str(obj.deleted_at)}, source='admin',
            )

    def history_view(self, request, object_id, extra_context=None):
        from django.core.exceptions import PermissionDenied
        from django.template.response import TemplateResponse
        from accounts.admin_parts.utils.history import build_entity_history

        if not self.has_view_permission(request):
            raise PermissionDenied

        try:
            obj = self.get_object(request, object_id)
        except Exception:
            obj = None

        if obj is not None:
            meta = _get_doc_meta(obj.pk)
            entity_name = meta['name'] if meta else obj.name
        else:
            entity_name = str(object_id)

        entries = build_entity_history('Document', object_id)
        back_url = reverse('admin:documents_document_change', args=[object_id])

        context = {
            **self.admin_site.each_context(request),
            'title': f'Historial — {entity_name}',
            'entries': entries,
            'back_url': back_url,
            'entity_name': entity_name,
            'object_id': object_id,
            'opts': self.model._meta,
            'original': obj,
            'breadcrumb_list_url': reverse('admin:documents_document_changelist'),
            'breadcrumb_list_label': 'Documentos',
        }
        if extra_context:
            context.update(extra_context)
        return TemplateResponse(request, 'admin/history/entity_history.html', context)
