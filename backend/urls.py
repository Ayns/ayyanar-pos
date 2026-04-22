"""AYY-34 — URL configuration for the AYY POS store box.

Routes:
  /admin/          — Django admin
  /api/            — AYY-34 backend (catalogue, billing, inventory, sync, tally, reporting)
  /api/hoc/        — HO Console API
  /pos-app/        — React POS frontend (served by nginx)
"""
from django.contrib import admin
from django.urls import path, include, re_path
from django.views.generic import TemplateView

urlpatterns = [
    path("admin/", admin.site.urls),
    # AYY-34 new backend
    path("api/", include("ayypos.backend.urls")),
    # Legacy storebox routes
    path("api/", include("sync_core.urls")),
    path("api/hoc/", include("hoc.urls")),
]

# Serve React frontend in development (nginx handles in production)
urlpatterns += [
    re_path(
        r"^pos-app/$",
        TemplateView.as_view(template_name="index.html"),
        name="pos-app",
    ),
]
