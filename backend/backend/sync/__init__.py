from django.apps import AppConfig

class SyncConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "ayypos.backend.sync"
    verbose_name = "Offline Sync (Store <-> Cloud)"
