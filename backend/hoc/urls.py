"""AYY-30 — URL routes for HO Console API."""
from django.urls import path
from . import views

app_name = "hoc"

urlpatterns = [
    # Tenants
    path("tenants/", views.tenant_list, name="tenant-list"),
    path("tenants/<uuid:pk>/", views.tenant_detail, name="tenant-detail"),
    # Stores
    path("stores/", views.store_list, name="store-list"),
    path("stores/create/", views.store_create, name="store-create"),
    # Catalogue
    path("catalogue/", views.catalogue_list, name="catalogue-list"),
    path("catalogue/push/", views.catalogue_push, name="catalogue-push"),
    # Users
    path("users/", views.user_list, name="user-list"),
    path("users/create/", views.user_create, name="user-create"),
    path("users/<uuid:pk>/", views.user_detail, name="user-detail"),
    path("users/<uuid:pk>/delete/", views.user_delete, name="user-delete"),
    # Stock transfers
    path("stock-transfers/", views.stock_transfer_list, name="stock-transfer-list"),
    path("stock-transfers/create/", views.stock_transfer_create, name="stock-transfer-create"),
    path("stock-transfers/<uuid:pk>/approve/", views.stock_transfer_approve, name="stock-transfer-approve"),
    path("stock-transfers/<uuid:pk>/reject/", views.stock_transfer_reject, name="stock-transfer-reject"),
    # Reconciliation
    path("reconciliation/", views.reconciliation_list, name="reconciliation-list"),
    path("reconciliation/<uuid:pk>/approve/", views.reconciliation_approve, name="reconciliation-approve"),
    path("reconciliation/<uuid:pk>/dispute/", views.reconciliation_dispute, name="reconciliation-dispute"),
    # Daily sales
    path("daily-sales/", views.daily_sales, name="daily-sales"),
    # Change feed
    path("change-feed/cursors/", views.change_feed_cursors, name="change-feed-cursors"),
]
