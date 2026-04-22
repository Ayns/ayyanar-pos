"""
AYY-34 — Till / POS URL routes.
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register(r"", views.TillViewSet, basename="till")

urlpatterns = [
    path("", include(router.urls)),
    path("receipt/<str:invoice_id>/", views.ReceiptView.as_view(), name="receipt"),
]
