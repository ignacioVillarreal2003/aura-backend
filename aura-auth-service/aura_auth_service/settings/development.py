"""Development settings — verbose and permissive. DEBUG is on."""

from .base import *  # noqa: F401, F403

DEBUG = True

# Developer tooling (shell_plus, runserver_plus, etc.) — dev only.
INSTALLED_APPS += ['django_extensions']  # noqa: F405
