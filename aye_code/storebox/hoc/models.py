"""
AYY-30 — HO Console models: multi-tenant data model with RLS schema.

Architecture:
  Tenant -> Store -> Terminal

  Each row carries a `tenant_id`. In production, Postgres RLS enforces
  isolation:

    ALTER TABLE hoc_tenant ENABLE ROW LEVEL SECURITY;
    CREATE POLICY tenant_isolate ON hoc_tenant FOR ALL
      USING (tenant_id = current_setting('app.current_tenant')::text);

  The ORM layer also scopes all queries by tenant (defence-in-depth).
  This prototype runs everything in a single database for simplicity.
"""
from django.db import models


class Tenant(models.Model):
    """A customer org. All data below this tenant_id is isolated."""

    class Meta:
        db_table = "hoc_tenant"

    id = models.UUIDField(primary_key=True, default=__import__("uuid").uuid4)
    name = models.CharField(max_length=128)
    active = models.BooleanField(default=True)
    licence_expiry = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class Store(models.Model):
    """A physical or virtual store belonging to a tenant."""

    class Meta:
        db_table = "hoc_store"

    id = models.CharField(max_length=32, primary_key=True)
    tenant = models.ForeignKey(Tenant, models.CASCADE, related_name="stores")
    name = models.CharField(max_length=128)
    city = models.CharField(max_length=64, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.tenant.name})"


class HocUser(models.Model):
    """HO Console user with role-based access scoped to a tenant."""

    class Role(models.TextChoices):
        SUPER_ADMIN = "super_admin", "Super Admin"
        TENANT_ADMIN = "tenant_admin", "Tenant Admin"
        CATALOGUE_EDITOR = "catalogue_editor", "Catalogue Editor"
        RECONCILIATION = "reconciliation", "Reconciliation"
        STORE_MANAGER = "store_manager", "Store Manager"

    class Meta:
        db_table = "hoc_user"

    id = models.UUIDField(primary_key=True, default=__import__("uuid").uuid4)
    tenant = models.ForeignKey(Tenant, models.CASCADE, related_name="users")
    email = models.EmailField(unique=True)
    name = models.CharField(max_length=128)
    role = models.CharField(max_length=32, choices=Role.choices)
    assigned_stores = models.JSONField(default=list, blank=True)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.role})"


class StockTransfer(models.Model):
    """Stock transfer between stores, managed by HO."""

    class Status(models.TextChoices):
        DRAFT = "draft"
        APPROVED = "approved"
        SHIPPED = "shipped"
        RECEIVED = "received"
        REJECTED = "rejected"

    class Meta:
        db_table = "hoc_stock_transfer"

    id = models.UUIDField(primary_key=True, default=__import__("uuid").uuid4)
    tenant = models.ForeignKey(Tenant, models.CASCADE, related_name="stock_transfers")
    from_store = models.ForeignKey(Store, models.CASCADE, related_name="outbound_transfers")
    to_store = models.ForeignKey(Store, models.CASCADE, related_name="inbound_transfers")
    items = models.JSONField(default=list)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.DRAFT)
    created_at = models.DateTimeField(auto_now_add=True)


class PendingReconciliation(models.Model):
    """Anomalies surfaced for HO operator resolution."""

    class Reason(models.TextChoices):
        STOCK_MISMATCH = "stock_mismatch"
        RETURN_NOT_SYNCED = "return_not_synced"
        NEGATIVE_STOCK = "negative_stock"
        PAYLOAD_DIVERGENCE = "payload_divergence"

    class Meta:
        db_table = "hoc_reconciliation"

    id = models.UUIDField(primary_key=True, default=__import__("uuid").uuid4)
    tenant = models.ForeignKey(Tenant, models.CASCADE, related_name="reconciliations")
    store = models.ForeignKey(Store, models.CASCADE, related_name="reconciliations")
    variant_id = models.CharField(max_length=64, blank=True, default="")
    reason = models.CharField(max_length=32, choices=Reason.choices)
    detail = models.JSONField(default=dict)
    resolved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class CatalogueUpdate(models.Model):
    """
    Cloud-authoritative catalogue change event.
    Stores pull these via monotonic `feed_cursor`.
    """

    class Meta:
        db_table = "hoc_catalogue_update"

    feed_cursor = models.BigAutoField(primary_key=True)
    tenant = models.ForeignKey(Tenant, models.CASCADE, related_name="catalog_updates")
    variant_id = models.CharField(max_length=64)
    field = models.CharField(max_length=32)
    new_value = models.JSONField()
    emitted_at = models.DateTimeField(auto_now_add=True)


class ChangeFeedCursor(models.Model):
    """Per-store position in the cloud catalogue change feed."""

    class Meta:
        db_table = "hoc_change_feed_cursor"

    store = models.OneToOneField(Store, models.CASCADE, primary_key=True, related_name="change_feed_cursor")
    cursor = models.BigIntegerField(default=0)
    last_sync = models.DateTimeField(null=True, blank=True)
