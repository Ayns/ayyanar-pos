"""AYY-30 — HO Console model and API tests."""
import json
from django.test import TestCase, Client
from .models import Tenant, Store, HocUser, StockTransfer, CatalogueUpdate, ChangeFeedCursor, PendingReconciliation


class TenantModelTest(TestCase):
    """Test Tenant model and RLS scoping."""

    def setUp(self):
        self.tenant1 = Tenant.objects.create(name="ApparelCo India", active=True)
        self.tenant2 = Tenant.objects.create(name="FashionHub Pvt", active=True)

    def test_str_representation(self):
        self.assertEqual(str(self.tenant1), "ApparelCo India")

    def test_default_active(self):
        t = Tenant.objects.create(name="New Tenant")
        self.assertTrue(t.active)


class StoreModelTest(TestCase):
    """Test Store model with tenant FK."""

    def setUp(self):
        self.tenant = Tenant.objects.create(name="Test Tenant")
        self.store = Store.objects.create(
            id="store-001", name="Bangalore Store", tenant=self.tenant, city="Bangalore"
        )

    def test_str_representation(self):
        self.assertIn("Bangalore Store", str(self.store))
        self.assertIn("Test Tenant", str(self.store))

    def test_tenant_cascade(self):
        tenant_id = self.tenant.pk
        self.tenant.delete()
        self.assertFalse(Store.objects.filter(pk=self.store.pk).exists())


class HocUserModelTest(TestCase):
    """Test HocUser model with role choices."""

    def setUp(self):
        self.tenant = Tenant.objects.create(name="Test Tenant")
        self.user = HocUser.objects.create(
            tenant=self.tenant,
            email="test@example.com",
            name="Test User",
            role=HocUser.Role.TENANT_ADMIN,
        )

    def test_role_choices(self):
        self.assertEqual(self.user.role, "tenant_admin")

    def test_assigned_stores_default(self):
        self.assertEqual(self.user.assigned_stores, [])


class StockTransferModelTest(TestCase):
    """Test stock transfer between stores."""

    def setUp(self):
        self.tenant = Tenant.objects.create(name="Test Tenant")
        self.store_a = Store.objects.create(id="store-a", name="Store A", tenant=self.tenant)
        self.store_b = Store.objects.create(id="store-b", name="Store B", tenant=self.tenant)
        self.transfer = StockTransfer.objects.create(
            tenant=self.tenant,
            from_store=self.store_a,
            to_store=self.store_b,
            items=[{"sku": "TS-BLK-M", "quantity": 10}],
        )

    def test_default_status(self):
        self.assertEqual(self.transfer.status, "draft")

    def test_items_json(self):
        self.assertEqual(self.transfer.items[0]["sku"], "TS-BLK-M")


class CatalogueUpdateModelTest(TestCase):
    """Test catalogue change feed entries with monotonic cursor."""

    def setUp(self):
        self.tenant = Tenant.objects.create(name="Test Tenant")

    def test_feed_cursor_monotonic(self):
        u1 = CatalogueUpdate.objects.create(
            tenant=self.tenant, variant_id="TS-BLK-M", field="mrp_paise", new_value=199900
        )
        u2 = CatalogueUpdate.objects.create(
            tenant=self.tenant, variant_id="TS-BLK-M", field="season_tag", new_value="FW26"
        )
        self.assertGreater(u2.feed_cursor, u1.feed_cursor)

    def test_feed_cursor_pk(self):
        u = CatalogueUpdate.objects.create(
            tenant=self.tenant, variant_id="X", field="test", new_value={"v": 1}
        )
        self.assertIsInstance(u.feed_cursor, int)
        self.assertEqual(u.feed_cursor, 1)


class ChangeFeedCursorModelTest(TestCase):
    """Test per-store change feed cursor position."""

    def setUp(self):
        self.tenant = Tenant.objects.create(name="Test Tenant")
        self.store = Store.objects.create(id="s1", name="S1", tenant=self.tenant)
        self.cursor = ChangeFeedCursor.objects.create(
            store=self.store, cursor=42
        )

    def test_cursor_value(self):
        self.assertEqual(self.cursor.cursor, 42)


class PendingReconciliationModelTest(TestCase):
    """Test reconciliation anomalies."""

    def setUp(self):
        self.tenant = Tenant.objects.create(name="Test Tenant")
        self.store = Store.objects.create(id="s1", name="S1", tenant=self.tenant)
        self.recon = PendingReconciliation.objects.create(
            tenant=self.tenant, store=self.store,
            variant_id="TS-BLK-M", reason="negative_stock",
        )

    def test_unresolved(self):
        self.assertIsNone(self.recon.resolved_at)

    def test_resolve(self):
        self.recon.resolved_at = __import__("datetime").datetime(2026, 4, 21, tzinfo=__import__("datetime").timezone.utc)
        self.recon.save()
        refreshed = PendingReconciliation.objects.get(pk=self.recon.pk)
        self.assertIsNotNone(refreshed.resolved_at)


# ── API View Tests ──

class HocApiTest(TestCase):
    """Test HO Console REST API endpoints."""

    def setUp(self):
        self.client = Client()
        self.tenant = Tenant.objects.create(name="Test Tenant")
        self.user = HocUser.objects.create(
            tenant=self.tenant, email="a@b.com", name="A", role=HocUser.Role.SUPER_ADMIN
        )

    def test_tenant_list(self):
        resp = self.client.get("/api/hoc/tenants/")
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.content)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["name"], "Test Tenant")

    def test_tenant_create(self):
        resp = self.client.post(
            "/api/hoc/tenants/",
            data=json.dumps({"name": "New Tenant"}),
            content_type="application/json"
        )
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(Tenant.objects.count(), 2)

    def test_user_list(self):
        resp = self.client.get("/api/hoc/users/")
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.content)
        self.assertEqual(len(data), 1)

    def test_change_feed_cursors(self):
        store = Store.objects.create(id="c1", name="C1", tenant=self.tenant)
        ChangeFeedCursor.objects.create(store=store, cursor=10)
        resp = self.client.get("/api/hoc/change-feed/cursors/")
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.content)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["cursor"], 10)

    def test_stock_transfer_list(self):
        store_a = Store.objects.create(id="sa", name="A", tenant=self.tenant)
        store_b = Store.objects.create(id="sb", name="B", tenant=self.tenant)
        StockTransfer.objects.create(
            tenant=self.tenant, from_store=store_a, to_store=store_b, items=[{"sku": "X", "quantity": 1}]
        )
        resp = self.client.get("/api/hoc/stock-transfers/")
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.content)
        self.assertEqual(len(data), 1)

    def test_reconciliation_list(self):
        store = Store.objects.create(id="s1", name="S1", tenant=self.tenant)
        PendingReconciliation.objects.create(
            tenant=self.tenant, store=store, variant_id="TS-BLK-M", reason="negative_stock"
        )
        resp = self.client.get("/api/hoc/reconciliation/")
        self.assertEqual(resp.status_code, 200)
