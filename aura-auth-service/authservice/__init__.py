"""Authservice package initialization."""

from copy import copy
import sys


def _patch_django_template_context_copy() -> None:
	"""Patch Django 5.1 template context copying for Python 3.14."""

	if sys.version_info < (3, 14):
		return

	from django.template.context import BaseContext

	if getattr(BaseContext.__copy__, "__module__", "") != "django.template.context":
		return

	def _base_context_copy(self):
		duplicate = object.__new__(self.__class__)
		duplicate.__dict__ = self.__dict__.copy()
		duplicate.dicts = self.dicts[:]
		return duplicate

	BaseContext.__copy__ = _base_context_copy


_patch_django_template_context_copy()
