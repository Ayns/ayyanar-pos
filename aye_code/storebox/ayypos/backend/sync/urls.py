"""
AYY-34 — Sync URL routes.
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register(r"outbox", views.SyncOutboxViewSet, basename="sync-outbox")
router.register(r"reconciliation", views.ReconciliationViewSet, basename="reconciliation")
router.register(r"sessions", views.ChangeFeedCursorViewSet, basename="sync-session")

urlpatterns = [
    path("", include(router.urls)),
    path("drain/", views.SyncDrainView.as_view({"post": "drain"}), name="sync-drain"),
]
