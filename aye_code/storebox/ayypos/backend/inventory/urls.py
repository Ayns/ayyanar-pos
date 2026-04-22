"""
AYY-34 — Inventory URL routes.
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register(r"events", views.StockEventViewSet, basename="stock-event")
router.register(r"levels", views.StockLevelViewSet, basename="stock-level")
router.register(r"adjustments", views.StockAdjustmentViewSet, basename="stock-adjustment")
router.register(r"transfers", views.StockTransferViewSet, basename="stock-transfer")

urlpatterns = [
    path("", include(router.urls)),
]
