"""ASGI entry — used by uvicorn locally and any async-capable host."""
import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "strata.settings")

from strata import observability  # noqa: E402, F401

application = get_asgi_application()
