"""Mixins del admin para la app accounts."""


class HelpTextStripMixin:
    """Saca los textos de ayuda de los formularios del admin."""

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


class HelpTextStripInlineMixin:
    """Saca los textos de ayuda de los formularios inline."""

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        formfield = super().formfield_for_dbfield(db_field, request, **kwargs)
        if formfield:
            formfield.help_text = ''
        return formfield
