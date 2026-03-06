from django.contrib import admin
from django.http import JsonResponse
from django.urls import path

from strata.api import api

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", api.urls),
    path("healthz", lambda r: JsonResponse({"status": "ok"})),
    path("readyz", lambda r: JsonResponse({"status": "ready"})),
]
