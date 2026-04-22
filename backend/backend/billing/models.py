"""
AYY-34 — Till / POS billing models.

Implements FR-POS-001 through FR-POS-012, FR-RET-001 through FR-RET-007.
Handles bill creation, payments, discounts, returns, and holds.
"""

import uuid
from decimal import Decimal

from django.db import models
from django.conf import settings


# ── Payment tender types ──
TENDER_CASH = "cash"
TENDER_CARD = "card"
TENDER_UPI = "upi"
TENDERWallet = "wallet"
TENDER_GIFT_VOUCHER = "gift_voucher"
TENDER_STORE_CREDIT = "store_credit"
TENDER_LOYALTY_POINTS = "loyalty_points"
TENDER_MIXED = "mixed"

TENDER_CHOICES = [
    (TENDER_CASH, "Cash"),
    (TENDER_CARD, "Credit/Debit Card"),
    (TENDER_UPI, "UPI"),
    (TENDERWallet, "Wallet"),
    (TENDER_GIFT_VOUCHER, "Gift Voucher"),
    (TENDER_STORE_CREDIT, "Store Credit"),
    (TENDER_LOYALTY_POINTS, "Loyalty Points"),
]


class Bill(models.Model):
    """FR-POS-006: A single bill/invoice with tender-wise payment split."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    store_id = models.CharField(max_length=20, default=settings.STORE_ID)
    bill_number = models.CharField(max_length=30, unique=True, editable=False)
    cashier_id = models.CharField(max_length=50)
    customer_id = models.ForeignKey(
        "customers.Customer", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="bills",
    )
    customer_name = models.CharField(max_length=200, blank=True)
    customer_mobile = models.CharField(max_length=10, blank=True)
    customer_gstin = models.CharField(max_length=15, blank=True)

    # Status
    STATUS_DRAFT = "draft"
    STATUS_HELD = "held"
    STATUS_COMPLETED = "completed"
    STATUS_CANCELLED = "cancelled"
    STATUS_RETURNED = "returned"

    status = models.CharField(max_length=20, default=STATUS_DRAFT, db_index=True)
    held_by = models.CharField(max_length=50, blank=True)  # who put it on hold
    held_at = models.DateTimeField(null=True, blank=True)

    # Financials
    subtotal_paise = models.PositiveIntegerField(default=0)
    discount_paise = models.PositiveIntegerField(default=0)
    taxable_value_paise = models.PositiveIntegerField(default=0)

    # GST breakdown
    cgst_rate = models.DecimalField(max_digits=5, decimal_places=2, default=9)  # intra-state
    sgst_rate = models.DecimalField(max_digits=5, decimal_places=2, default=9)
    igst_rate = models.DecimalField(max_digits=5, decimal_places=2, default=18)  # inter-state
    cgst_paise = models.PositiveIntegerField(default=0)
    sgst_paise = models.PositiveIntegerField(default=0)
    igst_paise = models.PositiveIntegerField(default=0)
    cess_paise = models.PositiveIntegerField(default=0)

    total_paise = models.PositiveIntegerField(default=0)
    total_paid_paise = models.PositiveIntegerField(default=0)
    balance_due_paise = models.PositiveIntegerField(default=0)

    # Inter-state flag
    is_inter_state = models.BooleanField(default=False)

    # Remarks
    remarks = models.CharField(max_length=120, blank=True)

    # Offline sync
    outbox_id = models.PositiveBigIntegerField(default=0, editable=False)  # Lamport counter
    is_synced = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "ayy_till_bill"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["store_id", "-created_at"]),
            models.Index(fields=["bill_number"]),
            models.Index(fields=["status"]),
        ]

    def __str__(self):
        return f"Bill #{self.bill_number} — {self.total_paise // 100} Rs"

    def save(self, *args, **kwargs):
        if not self.bill_number:
            # Generate bill number: prefix + YYYYMMDD + sequential
            from datetime import datetime
            today = datetime.utcnow().strftime("%Y%m%d")
            count = Bill.objects.filter(
                store_id=self.store_id,
                bill_number__startswith=f"AYY-{today}-"
            ).count()
            self.bill_number = f"AYY-{today}-{count + 1:06d}"
        super().save(*args, **kwargs)


class BillLine(models.Model):
    """A single line item on a bill."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    bill = models.ForeignKey(Bill, on_delete=models.CASCADE, related_name="lines")
    variant = models.ForeignKey(
        "catalogue.Variant", on_delete=models.PROTECT,
        related_name="bill_lines",
    )
    quantity = models.PositiveIntegerField(default=1)
    unit_price_paise = models.PositiveIntegerField()  # selling price at time of sale
    mrp_paise = models.PositiveIntegerField()  # MRP at time of sale (for compliance)
    line_discount_paise = models.PositiveIntegerField(default=0)
    taxable_value_paise = models.PositiveIntegerField(default=0)

    # GST per line
    hsn_code = models.CharField(max_length=10)
    gst_rate = models.DecimalField(max_digits=5, decimal_places=2)
    cgst_paise = models.PositiveIntegerField(default=0)
    sgst_paise = models.PositiveIntegerField(default=0)
    igst_paise = models.PositiveIntegerField(default=0)

    # Discount override tracking
    discount_override = models.BooleanField(default=False)
    overridden_by = models.CharField(max_length=50, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "ayy_till_bill_line"
        ordering = ["id"]

    @property
    def line_total_paise(self):
        return (self.unit_price_paise * self.quantity) - self.line_discount_paise

    @property
    def full_description(self):
        return f"{self.variant.style.style_name} | {self.variant.colour.name} | {self.variant.size.name}"


class BillPayment(models.Model):
    """FR-POS-005: A tender-wise payment split within a bill."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    bill = models.ForeignKey(Bill, on_delete=models.CASCADE, related_name="payments")
    tender_type = models.CharField(max_length=30, choices=TENDER_CHOICES)
    amount_paise = models.PositiveIntegerField()
    reference = models.CharField(max_length=200, blank=True)  # UPI txn ID, card auth ID, etc.
    metadata = models.JSONField(default=dict, blank=True)  # extra data (gateway response, etc.)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "ayy_till_bill_payment"
        ordering = ["id"]

    def __str__(self):
        tender_labels = dict(TENDER_CHOICES)
        type_label = tender_labels.get(self.tender_type, self.tender_type)
        return f"{type_label}: {Decimal(self.amount_paise) / 100} Rs"


class BillHold(models.Model):
    """FR-POS-008: Parked/resumed bill."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    bill = models.OneToOneField(Bill, on_delete=models.CASCADE, related_name="hold")
    held_by = models.CharField(max_length=50)
    held_at = models.DateTimeField(auto_now_add=True)
    released_at = models.DateTimeField(null=True, blank=True)
    resumed_by = models.CharField(max_length=50, blank=True)
    reason = models.CharField(max_length=200, blank=True)

    class Meta:
        db_table = "ayy_till_bill_hold"


class Return(models.Model):
    """FR-RET-001 through FR-RET-007: Return / exchange / credit note."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    original_bill = models.ForeignKey(Bill, on_delete=models.PROTECT, related_name="returns")
    return_number = models.CharField(max_length=30, unique=True, editable=False)
    reason = models.CharField(max_length=100)  # Defect, wrong size, change of mind, etc.

    refund_mode = models.CharField(
        max_length=20,
        choices=[
            ("original_tender", "Original Tender"),
            ("store_credit", "Store Credit"),
            ("either", "Either"),
        ],
        default="original_tender",
    )

    # Exchange support
    is_exchange = models.BooleanField(default=False)
    exchange_variant = models.ForeignKey(
        "catalogue.Variant", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="exchanges",
    )

    # Store credit
    credit_paise = models.PositiveIntegerField(default=0)
    credit_validity_days = models.PositiveIntegerField(default=90)
    credit_expires_at = models.DateField(null=True, blank=True)

    status = models.CharField(max_length=20, default="pending_qc")
    qc_approved = models.BooleanField(default=False)
    approved_by = models.CharField(max_length=50, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)

    # Credit note (GST)
    credit_note_number = models.CharField(max_length=30, unique=True, blank=True)
    credit_note_cgst_paise = models.PositiveIntegerField(default=0)
    credit_note_sgst_paise = models.PositiveIntegerField(default=0)
    credit_note_igst_paise = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "ayt_returns"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Return #{self.return_number} — {self.reason}"

    def save(self, *args, **kwargs):
        if not self.return_number:
            from datetime import datetime
            today = datetime.utcnow().strftime("%Y%m%d")
            count = Return.objects.filter(
                return_number__startswith=f"RET-{today}-"
            ).count()
            self.return_number = f"RET-{today}-{count + 1:04d}"
        if self.refund_mode == "store_credit" and not self.credit_expires_at:
            from datetime import timedelta
            self.credit_expires_at = (
                datetime.utcnow().date() + timedelta(days=self.credit_validity_days)
            )
        super().save(*args, **kwargs)
