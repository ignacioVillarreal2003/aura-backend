"""Formularios del admin para la seccion de notificaciones."""

from django import forms
from django.contrib.admin.widgets import FilteredSelectMultiple
from django.db import connections
from apps.accounts.models import User, Role, UserRole


class SendNotificationForm(forms.Form):
    """Formulario para enviar una notificacion a cada usuario elegido."""

    recipients = forms.ModelMultipleChoiceField(
        queryset=User.objects.none(),
        widget=FilteredSelectMultiple('Usuarios', is_stacked=False),
        label='Usuarios',
        help_text='',
    )
    message = forms.CharField(
        max_length=500,
        widget=forms.Textarea(attrs={'rows': 4}),
        label='Mensaje',
    )

    def __init__(self, *args, recipients_queryset=None, **kwargs):
        super().__init__(*args, **kwargs)
        if recipients_queryset is not None:
            self.fields['recipients'].queryset = recipients_queryset
        else:
            self.fields['recipients'].queryset = (
                User.objects.filter(deleted_at__isnull=True, status='active').order_by('username')
            )


class SendGroupNotificationForm(forms.Form):
    """Crea notificaciones segmentadas por niveles, agrupaciones o roles."""

    levels = forms.MultipleChoiceField(
        choices=[],
        required=False,
        label='Niveles',
        widget=forms.SelectMultiple(),
    )
    compartments = forms.MultipleChoiceField(
        choices=[],
        required=False,
        label='Agrupaciones',
        widget=forms.SelectMultiple(),
    )
    roles = forms.ModelMultipleChoiceField(
        queryset=Role.objects.filter(name='user'),
        widget=FilteredSelectMultiple('Roles de sistema', is_stacked=False),
        required=False,
        label='Roles de sistema',
        help_text='',
    )
    message = forms.CharField(
        max_length=500,
        widget=forms.Textarea(attrs={'rows': 4}),
        label='Mensaje',
    )

    def __init__(self, *args, level_choices=None, compartment_choices=None, **kwargs):
        super().__init__(*args, **kwargs)
        if level_choices:
            self.fields['levels'].choices = level_choices
        if compartment_choices:
            self.fields['compartments'].choices = compartment_choices

    def clean(self):
        cleaned_data = super().clean()
        levels = cleaned_data.get('levels')
        compartments = cleaned_data.get('compartments')
        roles = cleaned_data.get('roles')
        if not levels and not compartments and (not roles or roles.count() == 0):
            raise forms.ValidationError(
                'Debes seleccionar al menos un nivel, una agrupación o un rol de sistema.'
            )
        return cleaned_data

    def resolve_target_user_ids(self) -> list[int]:
        """Resuelve los usuarios segun los niveles, agrupaciones y roles elegidos."""
        level_ids = [int(lid) for lid in (self.cleaned_data.get('levels') or [])]
        compartment_ids = [int(cid) for cid in (self.cleaned_data.get('compartments') or [])]
        roles = self.cleaned_data.get('roles')

        user_ids = set()

        if level_ids:
            with connections['aura_db'].cursor() as cursor:
                for lid in level_ids:
                    cursor.execute("""
                        SELECT DISTINCT uc.user_id
                        FROM user_clearance uc
                        JOIN classification_level cl_user
                            ON uc.classification_level_id = cl_user.id
                        JOIN classification_level cl_target
                            ON cl_target.id = %s
                        WHERE cl_user.rank >= cl_target.rank
                    """, [lid])
                    user_ids.update(row[0] for row in cursor.fetchall())

        if compartment_ids:
            with connections['aura_db'].cursor() as cursor:
                for cid in compartment_ids:
                    cursor.execute("""
                        SELECT DISTINCT user_id
                        FROM user_compartment
                        WHERE compartment_id = %s
                    """, [cid])
                    user_ids.update(row[0] for row in cursor.fetchall())

        if user_ids:
            user_ids = set(
                User.objects.filter(
                    pk__in=user_ids,
                    deleted_at__isnull=True,
                    status='active',
                ).values_list('id', flat=True)
            )

        if roles:
            role_user_ids = UserRole.objects.filter(
                role__in=roles,
                deleted_at__isnull=True,
                user__deleted_at__isnull=True,
                user__status='active',
            ).values_list('user_id', flat=True)
            user_ids.update(role_user_ids)

        return sorted(user_ids)

    def build_target_label(self) -> str:
        level_ids = set(str(lid) for lid in (self.cleaned_data.get('levels') or []))
        compartment_ids = set(str(cid) for cid in (self.cleaned_data.get('compartments') or []))
        roles = self.cleaned_data.get('roles')
        labels = []
        if level_ids:
            names = [
                label for value, label in self.fields['levels'].choices
                if str(value) in level_ids
            ]
            if names:
                labels.append('Niveles: ' + ', '.join(names))
        if compartment_ids:
            names = [
                label for value, label in self.fields['compartments'].choices
                if str(value) in compartment_ids
            ]
            if names:
                labels.append('Agrupaciones: ' + ', '.join(names))
        if roles and roles.count() > 0:
            labels.append('Roles sistema: ' + ', '.join(roles.values_list('name', flat=True)))
        return ' | '.join(labels)
