"""
AYY-34 — E2E integration tests for the POS flow.

Covers:
  1. Catalogue CRUD (create products via API)
  2. Cart operations (add, remove, update qty)
  3. Checkout (stock deduction, GST computation, receipt)
  4. Receipt verification (data integrity check)

Run: python3 manage.py test storebox.ayypos.test_e2e
"""

import json
from decimal import Decimal, ROUND_HALF_UP

from django.test import TestCase, override_settings
from django.urls import reverse

from ayypos.backend.catalogue.models import Category, SubCategory, Style, Colour, Size, Variant
from ayypos.backend.billing.models import Bill, BillLine, BillPayment
from sync_core.models import StockEvent


# Use SQLite in-memory for tests
TEST_DB = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}}
CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}


@override_settings(DATABASES=TEST_DB, CACHES=CACHES)
class CatalogueAPITestCase(TestCase):
    """Test: catalogue API returns seeded products."""

    @classmethod
    def setUpTestData(cls):
        cat = Category.objects.create(name="Men", code="MEN")
        sub = SubCategory.objects.create(
            category=cat, name="T-Shirts", code="TS",
            hsn_code="6109", gst_slab=12,
        )
        style = Style.objects.create(
            sub_category=sub, style_name="Classic Tee",
            style_code="CT100",
        )
        red = Colour.objects.create(name="Red", hex_code="#FF0000")
        m = Size.objects.create(name="M", code="M")
        cls.variant = Variant.objects.create(
            style=style, colour=red, size=m,
            mrp_paise=99900, cost_price_paise=45000, selling_price_paise=89900,
        )

    def test_till_home_returns_catalogue(self):
        """FR-POS-001: GET /api/till/ returns all variants."""
        resp = self.client.get(reverse("till:home"))
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["sku"], "CT100-Red-M")
        self.assertEqual(data[0]["mrp_paise"], 99900)

    def test_search_catalogue(self):
        """FR-POS-002: GET /api/catalogue/search/?q=CT100 returns matching variants."""
        from ayypos.backend.catalogue.views import catalogue_search
        resp = self.client.get(reverse("catalogue:search") + "?q=CT100")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["total"], 1)
        self.assertEqual(data["variants"][0]["sku"], "CT100-Red-M")


@override_settings(DATABASES=TEST_DB, CACHES=CACHES)
class CartAPITestCase(TestCase):
    """Test: cart add/remove operations."""

    @classmethod
    def setUpTestData(cls):
        cat = Category.objects.create(name="Men", code="MEN")
        sub = SubCategory.objects.create(
            category=cat, name="T-Shirts", code="TS",
            hsn_code="6109", gst_slab=12,
        )
        style = Style.objects.create(
            sub_category=sub, style_name="Classic Tee",
            style_code="CT100",
        )
        red = Colour.objects.create(name="Red", hex_code="#FF0000")
        m = Size.objects.create(name="M", code="M")
        cls.variant = Variant.objects.create(
            style=style, colour=red, size=m,
            mrp_paise=99900, cost_price_paise=45000, selling_price_paise=89900,
        )

    def test_cart_add(self):
        """Cart: add item with variant_id."""
        resp = self.client.post(
            reverse("till:cart-add"),
            data=json.dumps({"variant_id": self.variant.variant_id, "qty": 2}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(len(data["cart"]), 1)
        self.assertEqual(data["cart"][0]["qty"], 2)

    def test_cart_add_duplicate_increments(self):
        """Cart: adding same item increments qty."""
        self.client.post(
            reverse("till:cart-add"),
            data=json.dumps({"variant_id": self.variant.variant_id, "qty": 1}),
            content_type="application/json",
        )
        resp = self.client.post(
            reverse("till:cart-add"),
            data=json.dumps({"variant_id": self.variant.variant_id, "qty": 3}),
            content_type="application/json",
        )
        data = resp.json()
        self.assertEqual(data["cart"][0]["qty"], 4)

    def test_cart_remove(self):
        """Cart: remove item."""
        self.client.post(
            reverse("till:cart-add"),
            data=json.dumps({"variant_id": self.variant.variant_id, "qty": 1}),
            content_type="application/json",
        )
        resp = self.client.post(
            reverse("till:cart-remove"),
            data=json.dumps({"variant_id": self.variant.variant_id}),
            content_type="application/json",
        )
        self.assertEqual(resp.json()["cart"], [])

    def test_cart_add_404(self):
        """Cart: add non-existent variant returns 404."""
        resp = self.client.post(
            reverse("till:cart-add"),
            data=json.dumps({"variant_id": "nonexistent", "qty": 1}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 404)


@override_settings(DATABASES=TEST_DB, CACHES=CACHES)
class CheckoutAPITestCase(TestCase):
    """Test: end-to-end checkout flow."""

    @classmethod
    def setUpTestData(cls):
        cat = Category.objects.create(name="Men", code="MEN")
        sub = SubCategory.objects.create(
            category=cat, name="T-Shirts", code="TS",
            hsn_code="6109", gst_slab=12,
        )
        style = Style.objects.create(
            sub_category=sub, style_name="Classic Tee",
            style_code="CT100",
        )
        red = Colour.objects.create(name="Red", hex_code="#FF0000")
        m = Size.objects.create(name="M", code="M")
        cls.variant = Variant.objects.create(
            style=style, colour=red, size=m,
            mrp_paise=99900, cost_price_paise=45000, selling_price_paise=89900,
        )

    def _add_to_cart(self, variant_id, qty=1):
        self.client.session["cart"] = []
        resp = self.client.post(
            reverse("till:cart-add"),
            data=json.dumps({"variant_id": variant_id, "qty": qty}),
            content_type="application/json",
        )
        return resp.json()

    def test_full_checkout(self):
        """
        Full checkout flow:
          1. Add item to cart
          2. Checkout with CASH payment
          3. Verify Bill + BillLine + BillPayment created
          4. Verify StockEvent emitted
          5. Verify receipt data integrity
        """
        # Step 1: Add to cart
        cart = self._add_to_cart(self.variant.variant_id, 2)
        self.assertEqual(len(cart["cart"]), 1)
        self.assertEqual(cart["cart"][0]["qty"], 2)

        # Step 2: Checkout
        payments = [{"method": "CASH", "amount_paise": 229788}]  # enough to cover MRP*2*1.12
        resp = self.client.post(
            reverse("till:checkout"),
            data=json.dumps({
                "payments": payments,
                "discount_paise": 0,
                "customer_name": "Test Customer",
                "customer_gstin": "",
            }),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "ok")
        self.assertIsNotNone(data["invoice_no"])
        self.assertEqual(data["cart"], [])  # cart cleared

        # Step 3: Verify Bill created
        bill = Bill.objects.first()
        self.assertIsNotNone(bill)
        self.assertEqual(bill.status, Bill.STATUS_COMPLETED)
        self.assertEqual(bill.lines.count(), 1)

        # Step 4: Verify BillLine
        line = bill.lines.first()
        self.assertEqual(line.variant, self.variant)
        self.assertEqual(line.qty, 2)
        self.assertEqual(line.line_total_paise, 99900 * 2)  # MRP * qty

        # Step 5: Verify BillPayment
        pay = BillPayment.objects.filter(bill=bill).first()
        self.assertIsNotNone(pay)
        self.assertEqual(pay.amount_paise, 229788)
        self.assertEqual(pay.tender_type, "cash")

        # Step 6: Verify StockEvent
        events = StockEvent.objects.filter(
            store_id="store-0001", variant=self.variant
        )
        self.assertTrue(events.exists())

        # Step 7: Verify GST computation
        gst_line = data["gst_lines"][0]
        self.assertEqual(gst_line["hsn_code"], "6109")
        # MRP = 99900 * 2 = 199800 paise
        # Base = 199800 / 1.12 = 178393 (rounded)
        # GST = 199800 - 178393 = 21407 paise
        self.assertGreater(gst_line["gst_total_paise"], 0)
        total_tax = gst_line["cgst_paise"] + gst_line["sgst_paise"] + gst_line["igst_paise"]
        self.assertEqual(total_tax, gst_line["gst_total_paise"])

    def test_checkout_empty_cart_returns_400(self):
        """Checkout with empty cart returns 400."""
        self.client.session["cart"] = []
        resp = self.client.post(
            reverse("till:checkout"),
            data=json.dumps({"payments": [], "discount_paise": 0}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 400)

    def test_receipt_view(self):
        """Verify receipt API returns bill data."""
        cart = self._add_to_cart(self.variant.variant_id, 1)
        self.client.post(
            reverse("till:checkout"),
            data=json.dumps({
                "payments": [{"method": "CASH", "amount_paise": 99900 * 112 // 100 + 1}],
                "discount_paise": 0,
                "customer_name": "Receipt Test",
            }),
            content_type="application/json",
        )
        bill = Bill.objects.first()
        invoice_no = bill.outbox_id

        resp = self.client.get(reverse("till:receipt", kwargs={"invoice_id": invoice_no}))
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["invoice_id"], invoice_no)
        self.assertIn("events", data)


@override_settings(DATABASES=TEST_DB, CACHES=CACHES)
class GSTComputationTestCase(TestCase):
    """Test: GST intra-state vs inter-state auto-detection."""

    def test_intra_state_cgst_sgst(self):
        """FR-TAX-001: Karnataka seller + Karnataka buyer = CGST + SGST."""
        from ayypos.backend.billing.views import _compute_gst
        result = _compute_gst(99900, 1, "6109", "29AAAAA0000A1Z5")
        self.assertEqual(result["cgst_paise"], result["sgst_paise"])
        self.assertEqual(result["igst_paise"], 0)
        self.assertEqual(result["cgst_paise"] + result["sgst_paise"], result["gst_total_paise"])

    def test_inter_state_igst(self):
        """FR-TAX-002: Karnataka seller + Maharashtra buyer = IGST."""
        from ayypos.backend.billing.views import _compute_gst
        result = _compute_gst(99900, 1, "6109", "27AAAAA0000A1Z5")
        self.assertEqual(result["igst_paise"], result["gst_total_paise"])
        self.assertEqual(result["cgst_paise"], 0)
        self.assertEqual(result["sgst_paise"], 0)

    def test_gst_amount_accuracy(self):
        """GST math must not lose paise due to float truncation."""
        from ayypos.backend.billing.views import _compute_gst
        # 99900 paise = Rs 999.00
        result = _compute_gst(99900, 1, "6109", "")
        # Base + GST = 99900
        base_plus_gst = result["base_paise"] + result["gst_total_paise"]
        self.assertEqual(base_plus_gst, 99900)
