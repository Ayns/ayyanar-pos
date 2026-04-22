import os

# Celery: set up the app before Django apps load
if os.getenv("DJANGO_ENV") == "store":
    from celery import Celery

    app = Celery("ayypos")
    app.config_from_object("django.conf:settings", namespace="CELERY")
    app.autodiscover_tasks()
