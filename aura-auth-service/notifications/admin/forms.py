"""Admin forms for the notifications section in aura-auth-service."""

from django import forms
from django.contrib.admin.widgets import FilteredSelectMultiple
from accounts.models import User, CustomGroup, Role, UserRole, FauRole
from accounts.repositories import group_membership as gm_repo


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
    fau_roles = forms.ModelMultipleChoiceField(
        queryset=FauRole.objects.order_by('power', 'name'),
        widget=FilteredSelectMultiple('Roles FAU', is_stacked=False),
        required=False,
        label='Roles FAU',
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
        fau_roles = cleaned_data.get('fau_roles')
        if (not groups or groups.count() == 0) and (not roles or roles.count() == 0) and (not fau_roles or fau_roles.count() == 0):
            raise forms.ValidationError('Debes seleccionar al menos un grupo, un rol de sistema o un Rol FAU.')
        return cleaned_data

    def resolve_target_user_ids(self) -> list[int]:
        """Resolve final target users from selected groups and roles."""
        cleaned_data = self.cleaned_data
        groups = cleaned_data.get('groups')
        roles = cleaned_data.get('roles')
        fau_roles = cleaned_data.get('fau_roles')

        user_ids = set()
        if groups:
            raw_ids = gm_repo.get_user_ids_for_groups([g.pk for g in groups])
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

        if fau_roles:
            fau_role_user_ids = User.objects.filter(
                fau_role__in=fau_roles,
                deleted_at__isnull=True,
                status='active',
            ).values_list('id', flat=True)
            user_ids.update(fau_role_user_ids)

        return sorted(user_ids)

    def build_target_label(self) -> str:
        groups = self.cleaned_data.get('groups')
        roles = self.cleaned_data.get('roles')
        fau_roles = self.cleaned_data.get('fau_roles')
        labels = []
        if groups and groups.count() > 0:
            labels.append('Grupos: ' + ', '.join(groups.values_list('name', flat=True)))
        if roles and roles.count() > 0:
            labels.append('Roles sistema: ' + ', '.join(roles.values_list('name', flat=True)))
        if fau_roles and fau_roles.count() > 0:
            labels.append('Roles FAU: ' + ', '.join(fau_roles.values_list('name', flat=True)))
        return ' | '.join(labels)
