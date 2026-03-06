"""WSGI entry — used by uWSGI in production."""
import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "strata.settings")

# Observability hooks (Sentry, OTel) bind to the app object on import.
from strata import observability  # noqa: E402, F401

application = get_wsgi_application()
