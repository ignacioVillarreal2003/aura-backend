import pytest
from unittest.mock import MagicMock, patch
from django.contrib.admin.sites import AdminSite
from django.test import RequestFactory
from django.utils import timezone
from apps.accounts.models import User
from apps.accounts.admin_parts.user_admin import UserAdmin

class TestUserAdminFixes:
    def test_permission_loophole_fixed(self):
        site = AdminSite()
        user_admin = UserAdmin(User, site)
        rf = RequestFactory()
        
        request = rf.get('/admin/accounts/user/')
        request.user = MagicMock()
        request.user.is_staff = True
        
        with patch('apps.accounts.admin_parts.user_admin.has_permission', return_value=False):
            assert not user_admin.has_add_permission(request)
            assert not user_admin.has_view_permission(request)
            assert not user_admin.has_change_permission(request, None)
            assert not user_admin.has_delete_permission(request, None)

    def test_name_is_readonly_on_edit(self):
        site = AdminSite()
        user_admin = UserAdmin(User, site)
        rf = RequestFactory()
        
        request = rf.get('/admin/accounts/user/1/change/')
        request.user = MagicMock()
        
        mock_obj = MagicMock()
        
        readonly = user_admin.get_readonly_fields(request, mock_obj)
        assert 'name' in readonly
        
        readonly_new = user_admin.get_readonly_fields(request, None)
        assert 'name' not in readonly_new

    def test_soft_deleted_users_visible_to_regular_admin(self):
        site = AdminSite()
        user_admin = UserAdmin(User, site)
        rf = RequestFactory()
        
        request = rf.get('/admin/accounts/user/')
        request.user = MagicMock()
        
        mock_qs = MagicMock()
        mock_qs.filter.return_value = mock_qs
        mock_qs.prefetch_related.return_value = mock_qs
        mock_qs.order_by.return_value = mock_qs
        
        with patch('django.contrib.admin.ModelAdmin.get_queryset', return_value=mock_qs), \
             patch('apps.accounts.admin_parts.user_admin.has_permission', return_value=False), \
             patch('apps.accounts.admin_parts.user_admin._is_effective_superadmin', return_value=False):
            
            user_admin.get_queryset(request)
            
            mock_qs.filter.assert_any_call(user_roles__role__name='user')

    def test_bulk_actions_permissions(self):
        site = AdminSite()
        user_admin = UserAdmin(User, site)
        rf = RequestFactory()
        
        request = rf.post('/admin/accounts/user/')
        request.user = MagicMock()
        
        with patch('apps.accounts.admin_parts.user_admin.has_permission', return_value=True), \
             patch('apps.accounts.admin_parts.user_admin._is_effective_superadmin', return_value=True):
            actions = user_admin.get_actions(request)
            assert 'bulk_soft_delete' in actions
            assert 'bulk_deactivate' in actions
            assert 'bulk_activate' in actions
            assert 'force_logout' in actions

        with patch('apps.accounts.admin_parts.user_admin.has_permission', return_value=False), \
             patch('apps.accounts.admin_parts.user_admin._is_effective_superadmin', return_value=False):
            actions = user_admin.get_actions(request)
            assert 'bulk_soft_delete' not in actions
            assert 'bulk_deactivate' not in actions
            assert 'bulk_activate' not in actions
            assert 'force_logout' not in actions

    def test_get_assignable_users_mac(self):
        from apps.accounts.admin_parts.mac_admin import _get_assignable_users
        rf = RequestFactory()
        request = rf.get('/admin/mac/classification-levels/')
        request.user = MagicMock()
        
        mock_qs = MagicMock()
        mock_qs.filter.return_value = mock_qs
        mock_qs.exclude.return_value = mock_qs
        mock_qs.distinct.return_value = mock_qs
        mock_qs.order_by.return_value = mock_qs
        
        with patch('apps.accounts.models.User.objects.filter', return_value=mock_qs):
            # Scenario 1: Regular admin (no ADMIN_USERS_EDIT_ADMIN perms)
            with patch('apps.accounts.admin_parts.mac_admin.has_permission', return_value=False), \
                 patch('apps.accounts.admin_parts.mac_admin._is_effective_superadmin', return_value=False):
                _get_assignable_users(request)
                
                mock_qs.exclude.assert_any_call(user_roles__role__name='superadmin', user_roles__deleted_at__isnull=True)
                mock_qs.exclude.assert_any_call(user_roles__role__name='admin', user_roles__deleted_at__isnull=True)

            mock_qs.exclude.reset_mock()

            # Scenario 2: Requester has ADMIN_USERS_EDIT_ADMIN
            with patch('apps.accounts.admin_parts.mac_admin.has_permission') as mock_has, \
                 patch('apps.accounts.admin_parts.mac_admin._is_effective_superadmin', return_value=False):
                mock_has.side_effect = lambda req, perm: perm == 'ADMIN_USERS_EDIT_ADMIN'
                _get_assignable_users(request)
                
                mock_qs.exclude.assert_any_call(user_roles__role__name='superadmin', user_roles__deleted_at__isnull=True)
                for call_args in mock_qs.exclude.call_args_list:
                    kwargs = call_args[1]
                    assert kwargs.get('user_roles__role__name') != 'admin'
