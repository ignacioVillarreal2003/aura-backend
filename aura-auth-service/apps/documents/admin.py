"""Admin de Django para el modelo Document."""

import contextvars
import json
import logging
import re

from django import forms
from django.contrib import admin, messages
from django.contrib.admin import helpers
from django.contrib.admin.exceptions import DisallowedModelAdminToField
from django.contrib.admin.options import IS_POPUP_VAR, TO_FIELD_VAR
from django.core.exceptions import PermissionDenied
from django.db import connections, router, transaction
from django.http import Http404, HttpResponseRedirect, StreamingHttpResponse
from django.urls import path, reverse
from django.utils.translation import gettext as _
from django.utils.html import format_html, format_html_join

logger = logging.getLogger(__name__)
from apps.accounts.admin_parts.utils.audit import log_audit, _is_admin_or_super_user, _is_super_admin_user
from apps.accounts.services.mac_client import mac_client
from apps.documents.models import Document
from apps.documents.services.document_processing_client import (
    DocumentProcessingServiceError,
    create_document_from_admin,
    bulk_create_documents_from_admin,
    delete_document as delete_document_remote,
    get_document as get_document_remote,
    update_document as update_document_remote,
    restore_document as restore_document_remote,
    download_document as download_document_remote,
    start_bulk_job as start_bulk_job_remote,
)
from apps.documents.repositories.document_meta_repository import (
    _get_doc_meta,
    _save_doc_meta,
    _batch_get_doc_meta_all,
)
from apps.documents.repositories.document_mac_repository import (
    _get_doc_mac_assignments,
    _db_assign_strict_mac_collection,
)

_ADMIN_LEVEL_RE = re.compile(r'^__admin_level_(\d+)__$')
_ADMIN_COMP_RE = re.compile(r'^__admin_comp_(\d+)__$')

# Uso un ContextVar (no un atributo) porque el DocumentAdmin es una sola
# instancia compartida entre peticiones y necesito el usuario actual por hilo
_current_admin_actor: 'contextvars.ContextVar' = contextvars.ContextVar(
    'document_admin_current_actor', default=None
)



def _format_processing_dt(value):
    """Formatea una fecha ISO para mostrarla; tolera texto, datetime o vacio."""
    if not value:
        return '—'
    try:
        from django.utils import timezone as dj_timezone
        from django.utils.dateparse import parse_datetime

        dt = parse_datetime(value) if isinstance(value, str) else value
        if dt is None:
            return str(value)
        if dj_timezone.is_naive(dt):
            dt = dj_timezone.make_aware(dt, dj_timezone.utc)
        return dj_timezone.localtime(dt).strftime('%d/%m/%Y %H:%M')
    except Exception:
        return str(value)





class DocumentUploadForm(forms.ModelForm):
    name = forms.CharField(max_length=255, label='Nombre')
    raw_collection = forms.FileField(label='Archivo', required=True)
    enrich = forms.BooleanField(
        label='Enriquecer fragmentos (LLM)', required=False, initial=False,
        help_text='Contextualiza los fragmentos con el LLM al procesar el documento.',
    )
    graph_extract = forms.BooleanField(
        label='Extraer grafo de conocimiento', required=False, initial=False,
        help_text='Extrae entidades y relaciones para el grafo de conocimiento.',
    )

    class Meta:
        model = Document
        fields = []

    def _post_clean(self):
        pass


class DocumentBulkUploadForm(forms.Form):
    """Form for the bulk-upload page. The file field accepts many files; the
    processing options (enrich / graph_extract) apply to the whole batch, the
    same way the single-upload form exposes them."""
    enrich = forms.BooleanField(
        label='Enriquecer fragmentos (LLM)', required=False, initial=False,
        help_text='Contextualiza los fragmentos con el LLM al procesar cada documento.',
    )
    graph_extract = forms.BooleanField(
        label='Extraer grafo de conocimiento', required=False, initial=False,
        help_text='Extrae entidades y relaciones para el grafo de conocimiento.',
    )


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



class DeletedDocumentsFilter(admin.SimpleListFilter):
    """Filtro lateral para ver los documentos eliminados (y restaurarlos)."""
    title = 'Mostrar'
    parameter_name = 'deleted'

    def lookups(self, request, model_admin):
        return (('1', 'Eliminados'),)

    def queryset(self, request, queryset):
        return queryset


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    change_form_template = 'admin/documents/document/change_form.html'
    change_list_template = 'admin/documents/document/change_list.html'
    list_display = (
        'name_display',
        'description_short',
        'size_display',
        'status_badge',
        'nivel_display',
        'agrupaciones_count',
    )
    list_display_links = ('name_display',)
    list_filter = (DeletedDocumentsFilter,)
    search_fields = ('name', 'description')
    readonly_fields = (
        'size_display',
        'status',
        'mime_type_display',
        'storage_url',
        'created_at',
        'created_by',
        'processing_status_display',
        'download_link',
    )
    actions = ['action_restore', 'action_reprocess', 'action_reembed', 'action_enrich', 'action_graph_extract']
    actions_selection_counter = True

    fieldsets = (
        ('Información Básica', {
            'fields': ('name', 'description', 'size_display', 'status', 'mime_type_display', 'storage_url'),
        }),
        ('Estado de procesamiento', {
            'fields': ('processing_status_display', 'download_link'),
        }),
        ('Auditoría', {
            'fields': ('created_at', 'created_by'),
            'classes': ('collapse',),
        }),
    )

    def get_queryset(self, request):
        qs = super().get_queryset(request).filter(chat_id__isnull=True)
        if request.GET.get('deleted') == '1':
            return qs.filter(deleted_at__isnull=False)
        return qs.filter(deleted_at__isnull=True)

    def get_actions(self, request):
        actions = super().get_actions(request)
        actions.pop('delete_selected', None)
        if not _is_super_admin_user(request.user):
            for name in ('action_reprocess', 'action_reembed', 'action_enrich', 'action_graph_extract'):
                actions.pop(name, None)
        return actions

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path(
                'bulk-upload/',
                self.admin_site.admin_view(self.bulk_upload_view),
                name='documents_document_bulk_upload',
            ),
            path(
                '<int:document_id>/download-file/',
                self.admin_site.admin_view(self.download_file_view),
                name='documents_document_download_file',
            ),
        ]
        return custom + urls

    def get_form(self, request, obj=None, **kwargs):
        return DocumentUploadForm if obj is None else DocumentChangeForm

    def get_fieldsets(self, request, obj=None):
        if obj is None:
            return (
                ('Subir documento', {
                    'fields': ('name', 'raw_collection'),
                }),
                ('Procesamiento', {
                    'fields': ('enrich', 'graph_extract'),
                    'description': 'Opciones de procesamiento del documento al crearlo.',
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
        """Toma nombre y descripcion del meta local para mostrarlos en el form."""
        obj = super().get_object(request, object_id, from_field)
        if obj is not None:
            meta = _get_doc_meta(obj.pk)
            if meta:
                obj.name = meta['name']
                obj.description = meta['description']
        return obj


    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context['title'] = 'Documentos'

        self._doc_meta_map = _batch_get_doc_meta_all()

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
            from apps.accounts.models import User
            self._user_map = {u.pk: u.username for u in User.objects.only('id', 'username')}
        except Exception:
            self._user_map = {}

        return super().changelist_view(request, extra_context)


    def changeform_view(self, request, object_id=None, form_url='', extra_context=None):
        extra_context = extra_context or {}
        _current_admin_actor.set(request.user)

        if object_id:
            doc_id = int(object_id)

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

            if request.method == 'POST':
                name = request.POST.get('name', '').strip()
                description = request.POST.get('description', '') or ''

                if not name:
                    messages.error(request, 'El nombre es obligatorio.')
                    return HttpResponseRedirect(
                        reverse('admin:documents_document_change', args=[object_id])
                    )

                prev_name = meta['name'] if meta else ''
                prev_description = (meta['description'] if meta else '') or ''

                _save_doc_meta(doc_id, name, description)

                try:
                    update_document_remote(doc_id, request.user, name=name, description=description)
                except DocumentProcessingServiceError as exc:
                    messages.warning(
                        request,
                        'El documento se guardó en el panel, pero el servicio de '
                        f'procesamiento no aplicó el cambio: {exc}',
                    )

                new_level_id_raw = request.POST.get('classification_level_id', '').strip()
                new_level_id = int(new_level_id_raw) if new_level_id_raw else None
                new_comp_ids = set(int(c) for c in request.POST.getlist('compartment_ids') if c)
                
                if new_level_id is not None:
                    _db_assign_strict_mac_collection(doc_id, new_level_id, new_comp_ids, request.user.pk)

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
        enrich_from_form = bool(form.cleaned_data.get('enrich', False))
        graph_extract_from_form = bool(form.cleaned_data.get('graph_extract', False))

        # Description is no longer set on creation: it is generated automatically
        # by the processing service (enrichment). The admin only provides the name.
        try:
            response_payload = create_document_from_admin(
                raw_document=raw_collection,
                actor_user=request.user,
                name=name_from_form or None,
                enrich=enrich_from_form,
                graph_extract=graph_extract_from_form,
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

        # Persist only the admin-chosen name on aura_db. Description is generated
        # automatically downstream, so it is not written here (and no local meta
        # row is saved, to avoid masking the auto-generated description).
        if name_from_form:
            try:
                with connections['aura_db'].cursor() as cursor:
                    cursor.execute(
                        'UPDATE document SET name = %s WHERE id = %s',
                        [name_from_form, document_id],
                    )
            except Exception:
                pass

        try:
            new_object = Document.objects.get(pk=document_id)
        except Document.DoesNotExist:
            new_object = Document(pk=document_id, name=name_from_form)

        cl_id_raw = request.POST.get('classification_level_id', '').strip()
        comp_ids_raw_list = [int(c) for c in request.POST.getlist('compartment_ids') if c]
        if cl_id_raw:
            _db_assign_strict_mac_collection(document_id, int(cl_id_raw), comp_ids_raw_list, request.user.pk)

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
        if enrich_from_form:
            audit_details['enriquecer'] = True
        if graph_extract_from_form:
            audit_details['extraer_grafo'] = True
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

    def processing_status_display(self, obj):
        """Estado de procesamiento, consultado al servicio de documentos.

        Solo se usa en el detalle, nunca en el listado, para no hacer una
        llamada HTTP por fila.
        """
        if obj is None or obj.pk is None:
            return '-'

        actor = _current_admin_actor.get()
        if actor is None or not getattr(actor, 'pk', None):
            return format_html('<span style="color:#888">Estado desconocido</span>')

        try:
            data = get_document_remote(obj.pk, actor)
        except DocumentProcessingServiceError as exc:
            logger.warning(
                'No se pudo obtener el estado de procesamiento del documento %s: %s', obj.pk, exc,
            )
            return format_html('<span style="color:#888">Estado desconocido</span>')
        except Exception:
            logger.exception(
                'Error inesperado al consultar el estado de procesamiento del documento %s', obj.pk,
            )
            return format_html('<span style="color:#888">Estado desconocido</span>')

        rows = (
            ('Estado', data.get('status') or '—'),
            ('Enriquecimiento', data.get('enrichment_status') or '—'),
            ('Grafo', data.get('graph_status') or '—'),
            ('Procesamiento iniciado', _format_processing_dt(data.get('processing_started_at'))),
            ('Procesamiento finalizado', _format_processing_dt(data.get('processing_finished_at'))),
        )
        return format_html_join(
            '',
            '<div style="margin-bottom:2px;"><strong>{}:</strong> {}</div>',
            rows,
        )
    processing_status_display.short_description = 'Estado de procesamiento'


    def download_link(self, obj):
        if obj is None or obj.pk is None:
            return '—'
        url = reverse('admin:documents_document_download_file', args=[obj.pk])
        return format_html('<a class="button" href="{}">Descargar archivo</a>', url)
    download_link.short_description = 'Archivo'

    def download_file_view(self, request, document_id):
        if not self.has_view_permission(request):
            raise PermissionDenied
        if not self.get_queryset(request).filter(pk=document_id).exists():
            raise Http404('Documento no encontrado.')
        try:
            upstream = download_document_remote(document_id, request.user)
        except DocumentProcessingServiceError as exc:
            messages.error(request, f'No se pudo descargar el documento: {exc}')
            return HttpResponseRedirect(
                reverse('admin:documents_document_change', args=[document_id])
            )

        response = StreamingHttpResponse(
            upstream.iter_content(chunk_size=8192),
            content_type=upstream.headers.get('Content-Type', 'application/octet-stream'),
        )
        disposition = upstream.headers.get('Content-Disposition')
        response['Content-Disposition'] = disposition or f'attachment; filename="documento_{document_id}"'
        content_length = upstream.headers.get('Content-Length')
        if content_length:
            response['Content-Length'] = content_length
        return response

    # ── Bulk operations (manage) — changelist actions ───────────────────────────

    def _run_bulk(self, request, queryset, operation, label):
        document_ids = list(queryset.values_list('id', flat=True))
        if not document_ids:
            messages.warning(request, 'No se seleccionaron documentos.')
            return
        try:
            result = start_bulk_job_remote(operation, request.user, document_ids=document_ids)
        except DocumentProcessingServiceError as exc:
            messages.error(request, f'No se pudo iniciar {label}: {exc}')
            return
        result = result or {}
        job_id = result.get('job_id', '—')
        total = result.get('total', len(document_ids))
        messages.success(request, f'{label.capitalize()} encolado (job {job_id}) para {total} documento(s).')
        log_audit(
            actor=request.user, action='UPDATE', entity_type='Document',
            entity_id=','.join(str(i) for i in document_ids[:50]),
            entity_label=f'{request.user.username} encoló {label} para {total} documento(s)',
            details={'operation': operation, 'job_id': job_id, 'count': total},
            source='admin', request=request,
        )

    def action_restore(self, request, queryset):
        restored, failed = 0, []
        for obj in queryset:
            try:
                restore_document_remote(obj.pk, request.user)
            except DocumentProcessingServiceError:
                failed.append(str(obj.pk))
                continue
            restored += 1
            log_audit(
                actor=request.user, action='UPDATE', entity_type='Document',
                entity_id=str(obj.pk),
                entity_label=f'{request.user.username} restauró el documento {obj.pk}',
                source='admin', request=request,
            )
        if restored:
            messages.success(request, f'{restored} documento(s) restaurado(s).')
        if failed:
            messages.error(request, f'No se pudieron restaurar: {", ".join(failed)}.')
    action_restore.short_description = 'Restaurar documentos seleccionados'

    def action_reprocess(self, request, queryset):
        self._run_bulk(request, queryset, 'reprocess', 'reprocesamiento')
    action_reprocess.short_description = 'Reprocesar documentos seleccionados'

    def action_reembed(self, request, queryset):
        self._run_bulk(request, queryset, 'reembed', 're-embedding')
    action_reembed.short_description = 'Regenerar embeddings de los documentos seleccionados'

    def action_enrich(self, request, queryset):
        self._run_bulk(request, queryset, 'enrich', 'enriquecimiento')
    action_enrich.short_description = 'Enriquecer los documentos seleccionados'

    def action_graph_extract(self, request, queryset):
        self._run_bulk(request, queryset, 'graph_extract', 'extracción de grafo')
    action_graph_extract.short_description = 'Reextraer el grafo de los documentos seleccionados'

    def get_deleted_objects(self, objs, request):
        """Evita el colector de cascada de Django en la pagina de confirmacion.

        Aca el borrado es logico y delegado al servicio de documentos, no una
        cascada real, asi que devuelvo solo el documento como vista previa y
        respeto los permisos de borrado.
        """
        objs = list(objs)
        deletable_objects = []
        for obj in objs:
            meta = _get_doc_meta(obj.pk)
            display_name = meta['name'] if meta else obj.name
            deletable_objects.append(
                format_html('{}: {}', self.model._meta.verbose_name, display_name)
            )
        model_count = {self.model._meta.verbose_name_plural: len(objs)}
        perms_needed = set()
        if not all(self.has_delete_permission(request, obj) for obj in objs):
            perms_needed.add(self.model._meta.verbose_name)
        protected = []
        return deletable_objects, model_count, perms_needed, protected

    def delete_model(self, request, obj):
        try:
            delete_document_remote(obj.pk, request.user)
        except DocumentProcessingServiceError as exc:
            messages.error(
                request,
                f'No se pudo eliminar el documento "{obj.name}" en el servicio de procesamiento '
                f'({exc}). El registro no fue eliminado localmente; intenta nuevamente.',
            )
            logger.warning('Document delete aborted for doc %s (upstream failure): %s', obj.pk, exc)
            return

        obj.soft_delete(deleted_by=request.user.pk)
        log_audit(
            actor=request.user, action='DELETE',
            entity_type='Document', entity_id=str(obj.pk),
            entity_label=obj.name,
            details={'deleted_at': str(obj.deleted_at)}, source='admin', request=request,
        )

    def delete_queryset(self, request, queryset):
        failed_names = []
        for obj in queryset:
            try:
                delete_document_remote(obj.pk, request.user)
            except DocumentProcessingServiceError as exc:
                failed_names.append(obj.name)
                logger.warning(
                    'Bulk document delete: doc %s failed upstream, local record kept: %s', obj.pk, exc,
                )
                continue

            obj.soft_delete(deleted_by=request.user.pk)
            log_audit(
                actor=request.user, action='DELETE',
                entity_type='Document', entity_id=str(obj.pk),
                entity_label=obj.name,
                details={'deleted_at': str(obj.deleted_at)}, source='admin',
            )

        if failed_names:
            messages.error(
                request,
                'No se pudo eliminar en el servicio de procesamiento (registro local conservado '
                'para reintentar): ' + ', '.join(failed_names),
            )

    def history_view(self, request, object_id, extra_context=None):
        from django.core.exceptions import PermissionDenied
        from django.template.response import TemplateResponse
        from apps.accounts.admin_parts.utils.history import build_entity_history

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
            'title': f'Historial - {entity_name}',
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
