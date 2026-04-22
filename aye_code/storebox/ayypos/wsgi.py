"""WSGI config for ayypos store box."""
import os
from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "ayypos.settings")
application = get_wsgi_application()
