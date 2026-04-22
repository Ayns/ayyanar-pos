"""AYY-27 — URL routes for sync_core (store API)."""
from django.urls import path
from . import views

app_name = "sync_core"

urlpatterns = [
    path("catalogue/", views.catalogue_list, name="catalogue-list"),
    path("catalogue/<str:variant_id>/", views.catalogue_detail, name="catalogue-detail"),
    path("stock/<str:variant_id>/", views.stock_on_hand, name="stock-on-hand"),
    path("events/", views.stock_events_list, name="events-list"),
    path("outbox/", views.outbox_status, name="outbox-status"),
    path("outbox/drain/", views.drain_outbox, name="drain-outbox"),
    path("reconciliation/", views.pending_reconciliation_list, name="reconciliation-list"),
]
