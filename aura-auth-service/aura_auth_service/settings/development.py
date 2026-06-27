"""Configuracion de desarrollo, con DEBUG encendido."""

from .base import *  # noqa: F401, F403

DEBUG = True

INSTALLED_APPS += ['django_extensions']  # noqa: F405
