"""User admin form."""

from django import forms
from django.contrib.admin.widgets import FilteredSelectMultiple
from django.db import connections
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
        # Exclude custom_groups from Django's automatic M2M handling.
        # User (auth_db) ↔ auth_user_custom_groups (aura_db) is cross-DB:
        # ModelForm.__init__ would call value_from_object which forces a query
        # on auth_db where neither custom_groups nor auth_user_custom_groups exist.
        # We populate initial values via raw SQL and save via UserAdmin.save_related.
        exclude = ['custom_groups']

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
