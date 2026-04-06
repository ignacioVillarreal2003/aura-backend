"""Admin forms for the notifications section in aura-auth-service."""

from django import forms
from accounts.models import User, CustomGroup, Role, UserRole
from notifications.models import NotificationType


class SendNotificationForm(forms.Form):
    """
    Form for sending a notification to one or many users from the Django admin.
    """

    recipients = forms.ModelMultipleChoiceField(
        queryset=User.objects.filter(deleted_at__isnull=True, status='active').order_by('username'),
        widget=forms.SelectMultiple(attrs={'size': 12, 'style': 'width:100%;max-width:500px;'}),
        label='Destinatarios',
        help_text='Mantén Ctrl (o Cmd) presionado para seleccionar múltiples usuarios.',
    )
    message = forms.CharField(
        max_length=500,
        widget=forms.Textarea(attrs={'rows': 4, 'style': 'width:100%;max-width:500px;'}),
        label='Mensaje',
    )
    type = forms.ChoiceField(
        choices=NotificationType.choices,
        label='Tipo',
    )


class SendGroupNotificationForm(forms.Form):
    """Create notifications targeting users by groups and/or roles."""

    groups = forms.ModelMultipleChoiceField(
        queryset=CustomGroup.objects.filter(deleted_at__isnull=True).order_by('name'),
        widget=forms.SelectMultiple(attrs={'size': 10, 'style': 'width:100%;max-width:500px;'}),
        required=False,
        label='Grupos',
    )
    roles = forms.ModelMultipleChoiceField(
        queryset=Role.objects.order_by('name'),
        widget=forms.SelectMultiple(attrs={'size': 10, 'style': 'width:100%;max-width:500px;'}),
        required=False,
        label='Roles de sistema',
    )
    message = forms.CharField(
        max_length=500,
        widget=forms.Textarea(attrs={'rows': 4, 'style': 'width:100%;max-width:500px;'}),
        label='Mensaje',
    )

    def clean(self):
        cleaned_data = super().clean()
        groups = cleaned_data.get('groups')
        roles = cleaned_data.get('roles')
        if (not groups or groups.count() == 0) and (not roles or roles.count() == 0):
            raise forms.ValidationError('Debes seleccionar al menos un grupo o un rol.')
        return cleaned_data

    def resolve_target_user_ids(self) -> list[int]:
        """Resolve final target users from selected groups and roles."""
        cleaned_data = self.cleaned_data
        groups = cleaned_data.get('groups')
        roles = cleaned_data.get('roles')

        user_ids = set()
        if groups:
            group_user_ids = User.objects.filter(
                custom_groups__in=groups,
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
            labels.append('Roles: ' + ', '.join(roles.values_list('name', flat=True)))
        return ' | '.join(labels)


class SendSystemNotificationForm(forms.Form):
    """Create system notifications for all active users."""

    message = forms.CharField(
        max_length=500,
        widget=forms.Textarea(attrs={'rows': 4, 'style': 'width:100%;max-width:500px;'}),
        label='Mensaje de sistema',
    )
