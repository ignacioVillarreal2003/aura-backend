"""Admin mixins for accounts app."""


class HelpTextStripMixin:
    """Remove help text from admin forms."""

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        formfield = super().formfield_for_dbfield(db_field, request, **kwargs)
        if formfield:
            formfield.help_text = ''
        return formfield

    def formfield_for_manytomany(self, db_field, request, **kwargs):
        formfield = super().formfield_for_manytomany(db_field, request, **kwargs)
        if formfield:
            formfield.help_text = ''
        return formfield


class AuditedAdminMixin:
    """Provides _get_audit_actor() to all ModelAdmin subclasses that mix it in."""

    def _get_audit_actor(self, request):
        """Returns (actor, elevated_by) for use in log_audit calls."""
        if getattr(request, 'is_elevated', False):
            return request.user, request.user.username
        return request.user, None


class HelpTextStripInlineMixin:
    """Remove help text from inline admin forms."""

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        formfield = super().formfield_for_dbfield(db_field, request, **kwargs)
        if formfield:
            formfield.help_text = ''
        return formfield
