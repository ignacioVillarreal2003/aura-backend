"""User admin form."""

from django import forms
from django.contrib.admin.widgets import FilteredSelectMultiple
from accounts.models import Role, CustomGroup, User, FauRole


class UserAdminForm(forms.ModelForm):
    active = forms.BooleanField(
        required=False,
        initial=True,
        label='Activo',
    )

    custom_groups = forms.ModelMultipleChoiceField(
        queryset=CustomGroup.objects.all(),
        required=False,
        widget=FilteredSelectMultiple('Grupos', is_stacked=False),
        label='',
        help_text='',
    )

    roles = forms.ModelChoiceField(
        queryset=Role.objects.filter(name__in=['ADMIN', 'USER']),
        required=False,
        widget=forms.RadioSelect(),
        label='Rol',
    )

    fau_role = forms.ModelChoiceField(
        queryset=FauRole.objects.order_by('-power', 'name'),
        required=True,
        label='Rol FAU',
        help_text='',
    )

    class Meta:
        model = User
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if 'status' in self.fields:
            self.fields['status'].widget = forms.HiddenInput()
        if self.instance and self.instance.pk:
            self.fields['active'].initial = (self.instance.status == 'active')
            if 'roles' in self.fields:
                self.fields['roles'].initial = Role.objects.filter(
                    user_assignments__user=self.instance,
                    user_assignments__deleted_at__isnull=True,
                ).first()
            if 'custom_groups' in self.fields:
                self.fields['custom_groups'].initial = self.instance.custom_groups.all()
        else:
            if 'roles' in self.fields:
                self.fields['roles'].initial = Role.objects.filter(name='USER').first()
        if self.instance and self.instance.pk:
            if 'fau_role' in self.fields:
                self.fields['fau_role'].initial = self.instance.fau_role_id
        if 'roles' in self.fields:
            def _role_label(role):
                if role.name == 'USER':
                    return 'USUARIO'
                return role.name
            self.fields['roles'].label_from_instance = _role_label
