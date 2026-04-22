"""AYY-30 — HO Console multi-tenant data model and change feed tests.

Tests the tenant isolation model (Tenant -> Store -> Terminal) and the
change feed with monotonic cursor for cloud-to-store sync pull.
"""
from django.test import TestCase

from hoc.models import (
    Tenant, Store, HocUser, StockTransfer, CatalogueUpdate,
    ChangeFeedCursor, PendingReconciliation,
)


class TenantIsolationTest(TestCase):
    """Verify Tenant -> Store -> Terminal hierarchy and isolation."""

    def setUp(self):
        self.tenant1 = Tenant.objects.create(name="ApparelCo India")
        self.tenant2 = Tenant.objects.create(name="FashionHub Pvt")

    def test_tenants_isolate_stores(self):
        s1 = Store.objects.create(id="s1", name="Store A", tenant=self.tenant1)
        s2 = Store.objects.create(id="s2", name="Store B", tenant=self.tenant2)

        self.assertEqual(self.tenant1.stores.count(), 1)
        self.assertEqual(self.tenant2.stores.count(), 1)
        self.assertNotEqual(s1.tenant, s2.tenant)

    def test_tenant_cascade_deletes_stores(self):
        Store.objects.create(id="s1", name="Store A", tenant=self.tenant1)
        tenant_id = self.tenant1.pk
        self.tenant1.delete()
        self.assertFalse(Store.objects.filter(pk="s1").exists())

    def test_tenant_str(self):
        self.assertEqual(str(self.tenant1), "ApparelCo India")


class HocUserIsolationTest(TestCase):
    """Test user/role management with tenant scoping."""

    def setUp(self):
        self.tenant = Tenant.objects.create(name="Test Tenant")
        self.user = HocUser.objects.create(
            tenant=self.tenant,
            email="admin@test.com",
            name="Admin",
            role=HocUser.Role.SUPER_ADMIN,
            assigned_stores=["store-1", "store-2"],
        )

    def test_role_assignment(self):
        self.assertEqual(self.user.role, "super_admin")

    def test_assigned_stores(self):
        self.assertEqual(self.user.assigned_stores, ["store-1", "store-2"])

    def test_user_belongs_to_tenant(self):
        self.assertEqual(self.user.tenant, self.tenant)

    def test_email_unique(self):
        with self.assertRaises(Exception):
            HocUser.objects.create(
                tenant=self.tenant, email="admin@test.com",
                name="Dup", role=HocUser.Role.TENANT_ADMIN,
            )


class StockTransferTest(TestCase):
    """Test stock-transfer workflow between stores."""

    def setUp(self):
        self.tenant = Tenant.objects.create(name="Test Tenant")
        self.store_a = Store.objects.create(id="store-a", name="Store A", tenant=self.tenant)
        self.store_b = Store.objects.create(id="store-b", name="Store B", tenant=self.tenant)
        self.transfer = StockTransfer.objects.create(
            tenant=self.tenant,
            from_store=self.store_a,
            to_store=self.store_b,
            items=[{"sku": "TS-BLK-M", "style": "T-Shirt", "size": "M", "color": "Black", "quantity": 20}],
        )

    def test_default_status(self):
        self.assertEqual(self.transfer.status, "draft")

    def test_items_structure(self):
        self.assertEqual(len(self.transfer.items), 1)
        self.assertEqual(self.transfer.items[0]["sku"], "TS-BLK-M")

    def test_store_references(self):
        self.assertEqual(self.transfer.from_store, self.store_a)
        self.assertEqual(self.transfer.to_store, self.store_b)


class CatalogueChangeFeedTest(TestCase):
    """
    Test the cloud-to-store change feed with monotonic cursor.

    Per AYY-24 spec: CatalogUpdate rows ordered by feed_cursor (BigAutoField,
    monotonically increasing PK). Stores pull via ChangeFeedCursor and replay
    updates in order.
    """

    def setUp(self):
        self.tenant = Tenant.objects.create(name="Test Tenant")

    def test_feed_cursor_monotonic(self):
        u1 = CatalogueUpdate.objects.create(
            tenant=self.tenant, variant_id="TS-BLK-M",
            field="mrp_paise", new_value=199900,
        )
        u2 = CatalogueUpdate.objects.create(
            tenant=self.tenant, variant_id="TS-BLK-M",
            field="season_tag", new_value="FW26",
        )
        u3 = CatalogueUpdate.objects.create(
            tenant=self.tenant, variant_id="TS-BLK-M",
            field="mrp_paise", new_value=219900,
        )
        self.assertLess(u1.feed_cursor, u2.feed_cursor)
        self.assertLess(u2.feed_cursor, u3.feed_cursor)

    def test_feed_cursor_starts_at_one(self):
        u = CatalogueUpdate.objects.create(
            tenant=self.tenant, variant_id="X",
            field="created", new_value={"v": 1},
        )
        self.assertEqual(u.feed_cursor, 1)

    def test_pull_updates_since_cursor(self):
        """Simulate a store pulling updates since its last cursor position."""
        u1 = CatalogueUpdate.objects.create(
            tenant=self.tenant, variant_id="TS-BLK-M",
            field="mrp_paise", new_value=199900,
        )
        u2 = CatalogueUpdate.objects.create(
            tenant=self.tenant, variant_id="TS-BLK-M",
            field="season_tag", new_value="FW26",
        )
        u3 = CatalogueUpdate.objects.create(
            tenant=self.tenant, variant_id="PP-RED-L",
            field="mrp_paise", new_value=349900,
        )

        # Store at cursor position 1 — should get updates 2 and 3
        updates = CatalogueUpdate.objects.filter(
            feed_cursor__gt=1, tenant=self.tenant
        ).order_by("feed_cursor")
        self.assertEqual(updates.count(), 2)
        self.assertEqual(updates[0].variant_id, "TS-BLK-M")
        self.assertEqual(updates[1].variant_id, "PP-RED-L")

    def test_replayer_flow(self):
        """Simulate the full replayer: pull, apply, advance cursor."""
        # Emit updates
        for mrp in [199900, 209900, 219900]:
            CatalogueUpdate.objects.create(
                tenant=self.tenant, variant_id="TS-BLK-M",
                field="mrp_paise", new_value=mrp,
            )

        # Store starts at cursor 0
        store = Store.objects.create(id="replay-store", name="Replay Store", tenant=self.tenant)
        cursor_obj = ChangeFeedCursor.objects.create(store=store, cursor=0)

        # Pull and apply
        applied = 0
        while True:
            updates = CatalogueUpdate.objects.filter(
                feed_cursor__gt=cursor_obj.cursor, tenant=self.tenant
            ).order_by("feed_cursor")
            if not updates.exists():
                break
            cursor_obj.cursor = updates.last().feed_cursor
            cursor_obj.save()
            applied += updates.count()

        self.assertEqual(applied, 3)
        self.assertEqual(cursor_obj.cursor, 3)


class ChangeFeedCursorTest(TestCase):
    """Test per-store cursor state."""

    def setUp(self):
        self.tenant = Tenant.objects.create(name="Test Tenant")
        self.store = Store.objects.create(id="c1", name="C1", tenant=self.tenant)

    def test_initial_cursor(self):
        cursor_obj = ChangeFeedCursor.objects.create(store=self.store, cursor=0)
        self.assertEqual(cursor_obj.cursor, 0)

    def test_cursor_advances(self):
        cursor_obj = ChangeFeedCursor.objects.create(store=self.store, cursor=42)
        cursor_obj.cursor = 100
        cursor_obj.save()
        self.assertEqual(ChangeFeedCursor.objects.get(store=self.store).cursor, 100)


class PendingReconciliationTest(TestCase):
    """Test reconciliation anomaly tracking."""

    def setUp(self):
        self.tenant = Tenant.objects.create(name="Test Tenant")
        self.store = Store.objects.create(id="r1", name="R1", tenant=self.tenant)
        self.recon = PendingReconciliation.objects.create(
            tenant=self.tenant, store=self.store,
            variant_id="TS-BLK-M", reason="negative_stock",
            detail={"store_count": 5, "system_count": 0},
        )

    def test_unresolved(self):
        self.assertIsNone(self.recon.resolved_at)

    def test_resolve(self):
        import datetime
        self.recon.resolved_at = datetime.datetime.now(datetime.timezone.utc)
        self.recon.save()
        self.assertIsNotNone(PendingReconciliation.objects.get(pk=self.recon.pk).resolved_at)

    def test_dispute_updates_reason(self):
        self.recon.reason = "negative_stock (disputed)"
        self.recon.save()
        self.assertEqual(PendingReconciliation.objects.get(pk=self.recon.pk).reason,
                         "negative_stock (disputed)")
