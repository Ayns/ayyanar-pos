from django.apps import AppConfig


class BillingConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "ayypos.backend.billing"
    verbose_name = "POS Billing"
