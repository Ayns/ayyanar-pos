"""Licence server Django app."""
from django.apps import AppConfig


class LicenceServerConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "licence_server"
    verbose_name = "Licence Server"
