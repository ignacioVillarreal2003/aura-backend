"""Admin forms for the notifications section in aura-auth-service."""

from django import forms
from django.contrib.admin.widgets import FilteredSelectMultiple
from django.db import connections
from accounts.models import User, CustomGroup, Role, UserRole


class SendNotificationForm(forms.Form):
    """Form for sending one notification per selected user from the Django admin."""

    recipients = forms.ModelMultipleChoiceField(
        queryset=User.objects.filter(deleted_at__isnull=True, status='active').order_by('username'),
        widget=FilteredSelectMultiple('Usuarios', is_stacked=False),
        label='Usuarios',
        help_text='',
    )
    message = forms.CharField(
        max_length=500,
        widget=forms.Textarea(attrs={'rows': 4}),
        label='Mensaje',
    )


class SendGroupNotificationForm(forms.Form):
    """Create notifications targeting users by groups and/or roles."""

    groups = forms.ModelMultipleChoiceField(
        queryset=CustomGroup.objects.filter(deleted_at__isnull=True).order_by('name'),
        widget=FilteredSelectMultiple('Grupos', is_stacked=False),
        required=False,
        label='Grupos',
        help_text='',
    )
    roles = forms.ModelMultipleChoiceField(
        queryset=Role.objects.order_by('name'),
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

    def clean(self):
        cleaned_data = super().clean()
        groups = cleaned_data.get('groups')
        roles = cleaned_data.get('roles')
        if (not groups or groups.count() == 0) and (not roles or roles.count() == 0):
            raise forms.ValidationError('Debes seleccionar al menos un grupo o un rol de sistema.')
        return cleaned_data

    def resolve_target_user_ids(self) -> list[int]:
        """Resolve final target users from selected groups and roles."""
        cleaned_data = self.cleaned_data
        groups = cleaned_data.get('groups')
        roles = cleaned_data.get('roles')

        user_ids = set()
        if groups:
            # Cross-DB M2M: User (auth_db) ↔ auth_user_custom_groups (aura_db).
            # ORM JOIN would fail; resolve user_ids via raw SQL on aura_db then
            # filter active/non-deleted users from auth_db.
            group_ids = [str(g.pk) for g in groups]
            with connections['aura_db'].cursor() as cursor:
                placeholders = ','.join(['%s::uuid'] * len(group_ids))
                cursor.execute(
                    f'SELECT DISTINCT user_id FROM auth_user_custom_groups WHERE customgroup_id IN ({placeholders})',
                    group_ids,
                )
                raw_ids = [row[0] for row in cursor.fetchall()]
            if raw_ids:
                group_user_ids = User.objects.filter(
                    pk__in=raw_ids,
                    deleted_at__isnull=True,
                    status='active',
                ).values_list('id', flat=True)
                user_ids.update(group_user_ids)

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
        groups = self.cleaned_data.get('groups')
        roles = self.cleaned_data.get('roles')
        labels = []
        if groups and groups.count() > 0:
            labels.append('Grupos: ' + ', '.join(groups.values_list('name', flat=True)))
        if roles and roles.count() > 0:
            labels.append('Roles sistema: ' + ', '.join(roles.values_list('name', flat=True)))
        return ' | '.join(labels)
