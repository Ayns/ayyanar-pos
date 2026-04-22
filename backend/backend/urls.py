"""
AYY-34 — Main URL configuration for the ayypos backend.
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter

# Reporting views
from ayypos.backend.reporting.views import DailySalesView, ZReportView
# Tally views
from ayypos.backend.tally.urls import TallyExportView
# Tally URL router
from ayypos.backend.tally import urls as tally_urls

urlpatterns = [
    path("catalogue/", include("ayypos.backend.catalogue.urls")),
    path("till/", include("ayypos.backend.billing.urls")),
    path("inventory/", include("ayypos.backend.inventory.urls")),
    path("sync/", include("ayypos.backend.sync.urls")),
    path("reporting/daily-sales/", DailySalesView.as_view(), name="daily-sales"),
    path("reporting/z-report/", ZReportView.as_view(), name="z-report"),
    path("tally/export/", TallyExportView.as_view(), name="tally-export"),
]
