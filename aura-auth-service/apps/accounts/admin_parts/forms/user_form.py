"""Formulario del admin de usuarios."""

from django import forms
from apps.accounts.models import Role, User


class RoleRadioSelect(forms.RadioSelect):
    """RadioSelect que agrega data-role-name a cada input para el JS."""

    def create_option(self, name, value, label, selected, index, **kwargs):
        option = super().create_option(name, value, label, selected, index, **kwargs)
        option['attrs']['data-role-name'] = str(label).strip().lower()
        return option


class UserAdminForm(forms.ModelForm):
    password = forms.CharField(
        widget=forms.PasswordInput(render_value=False),
        label='Contraseña',
        required=False,
    )

    active = forms.BooleanField(
        required=False,
        initial=True,
        label='Activo',
    )

    roles = forms.ModelChoiceField(
        queryset=Role.objects.filter(name__in=['admin', 'user']),
        required=False,
        widget=RoleRadioSelect(),
        label='Rol',
    )

    classification_level_id = forms.ChoiceField(
        choices=[('', '-- Sin nivel --')],
        required=False,
        label='Nivel',
    )

    compartment_ids = forms.MultipleChoiceField(
        choices=[],
        required=False,
        label='Agrupaciones',
        widget=forms.CheckboxSelectMultiple(),
    )

    class Meta:
        model = User
        exclude = []

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
        else:
            if 'roles' in self.fields:
                self.fields['roles'].initial = Role.objects.filter(name='user').first()
        if 'roles' in self.fields:
            def _role_label(role):
                if role.name == 'user':
                    return 'user'
                return role.name
            self.fields['roles'].label_from_instance = _role_label

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get('password')
        is_new = not (self.instance and self.instance.pk)
        if is_new and not password:
            self.add_error('password', 'Este campo es obligatorio.')
        return cleaned_data
