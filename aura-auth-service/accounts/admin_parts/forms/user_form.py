"""User admin form."""

from django import forms
from django.contrib.admin.widgets import FilteredSelectMultiple
from django.db import connections
from accounts.models import Role, CustomGroup, User, FauRole


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

    custom_groups = forms.ModelMultipleChoiceField(
        queryset=CustomGroup.objects.all(),
        required=False,
        widget=FilteredSelectMultiple('Grupos', is_stacked=False),
        label='',
        help_text='',
    )

    roles = forms.ModelChoiceField(
        queryset=Role.objects.filter(name__in=['admin', 'user']),
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
        # custom_groups is not a model field — it is a manual cross-DB relation
        # managed via raw SQL on aura_db (see UserAdmin.save_related).
        # The form field below is declared explicitly and populated/saved manually.
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
            if 'custom_groups' in self.fields:
                # Cross-DB M2M: load current group membership via raw SQL on aura_db.
                # Raw SQL: SELECT customgroup_id FROM auth_user_custom_groups WHERE user_id = %s
                with connections['aura_db'].cursor() as cursor:
                    cursor.execute(
                        'SELECT customgroup_id FROM auth_user_custom_groups WHERE user_id = %s',
                        [self.instance.pk],
                    )
                    group_ids = [row[0] for row in cursor.fetchall()]
                self.initial['custom_groups'] = group_ids
        else:
            if 'roles' in self.fields:
                self.fields['roles'].initial = Role.objects.filter(name='user').first()
        if self.instance and self.instance.pk:
            if 'fau_role' in self.fields:
                self.fields['fau_role'].initial = self.instance.fau_role_id
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
