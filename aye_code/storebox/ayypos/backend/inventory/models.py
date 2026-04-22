"""
AYY-34 — Inventory models.

Implements FR-LED-001 through FR-LED-005 (stock ledger),
FR-ADJ-001 through FR-ADJ-005 (adjustments),
FR-PI-001 through FR-PI-008 (physical inventory),
FR-BIN-001 through FR-BIN-004 (bin/location),
FR-KIT-001 through FR-KIT-004 (kits/bundles),
FR-NEG-001 through FR-NEG-004 (negative stock guards).
"""

import uuid
from decimal import Decimal

from django.db import models
from django.conf import settings


# ── Stock event types ──
EVENT_INWARD = "inward"       # GRN
EVENT_OUTWARD = "outward"     # Sale
EVENT_RETURN = "return"       # Return to stock
EVENT_ADJUSTMENT = "adjustment"
EVENT_PHYSICAL_COUNT = "physical_count"
EVENT_TRANSFER_OUT = "transfer_out"
EVENT_TRANSFER_IN = "transfer_in"
EVENT_KIT_BUILD = "kit_build"
EVENT_KIT_DEBUILD = "kit_debuild"
EVENT_QC_HOLD = "qc_hold"
EVENT_QC_RELEASE = "qc_release"

EVENT_TYPES = [
    (EVENT_INWARD, "Inward (GRN)"),
    (EVENT_OUTWARD, "Outward (Sale)"),
    (EVENT_RETURN, "Return"),
    (EVENT_ADJUSTMENT, "Adjustment"),
    (EVENT_PHYSICAL_COUNT, "Physical Count"),
    (EVENT_TRANSFER_OUT, "Transfer Out"),
    (EVENT_TRANSFER_IN, "Transfer In"),
    (EVENT_KIT_BUILD, "Kit Build"),
    (EVENT_KIT_DEBUILD, "Kit Debuild"),
    (EVENT_QC_HOLD, "QC Hold"),
    (EVENT_QC_RELEASE, "QC Release"),
]

# ── Adjustment reason codes ──
REASON_DAMAGE = "damage"
REASON_THEFT = "theft"
REASON_SAMPLE = "sample"
REASON_INTERNAL = "internal_consumption"
REASON_FOUND = "found"
REASON_SYSTEM_CORRECTION = "system_correction"
REASON_PI_VARIANCE = "pi_variance"

REASON_CODES = [
    (REASON_DAMAGE, "Damage"),
    (REASON_THEFT, "Theft/Shrinkage"),
    (REASON_SAMPLE, "Sample Issue"),
    (REASON_INTERNAL, "Internal Consumption"),
    (REASON_FOUND, "Found"),
    (REASON_SYSTEM_CORRECTION, "System Correction"),
    (REASON_PI_VARIANCE, "PI Variance"),
]

# ── Stock buckets ──
BUCKET_SELLABLE = "sellable"
BUCKET_PENDING_QC = "pending_qc"
BUCKET_VENDOR_RETURN = "vendor_return_pending"
BUCKET_IN_TRANSIT = "in_transit"
BUCKET_HELD = "held"
BUCKET_ALLOCATED = "allocated"

BUCKET_CHOICES = [
    (BUCKET_SELLABLE, "Sellable"),
    (BUCKET_PENDING_QC, "Pending QC"),
    (BUCKET_VENDOR_RETURN, "Vendor Return Pending"),
    (BUCKET_IN_TRANSIT, "In Transit"),
    (BUCKET_HELD, "Held/Block"),
    (BUCKET_ALLOCATED, "Allocated"),
]

# ── Stock valuation methods ──
VALUATION_WAC = "weighted_average_cost"
VALUATION_FIFO = "fifo"
VALUATION_MRP = "mrp_based"

VALUATION_METHODS = [
    (VALUATION_WAC, "Weighted Average Cost"),
    (VALUATION_FIFO, "First-In-First-Out"),
    (VALUATION_MRP, "MRP-Based"),
]


class StockEvent(models.Model):
    """
    FR-LED-001: Append-only stock ledger entry.

    Every stock movement generates one entry.
    Immutable — once written, never modified.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    store_id = models.CharField(max_length=20, default=settings.STORE_ID)
    variant = models.ForeignKey("catalogue.Variant", on_delete=models.PROTECT, related_name="stock_events")

    event_type = models.CharField(max_length=30, choices=EVENT_TYPES)
    quantity = models.BigIntegerField()  # positive for inward, negative for outward

    # Context for the event
    reference_type = models.CharField(max_length=50, blank=True)  # "bill", "grn", "po", etc.
    reference_id = models.UUIDField(null=True, blank=True)  # FK to the source document
    reason_code = models.CharField(max_length=50, blank=True)

    # Timestamps (Lamport-style for ordering)
    lamport_timestamp = models.PositiveBigIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    # Audit
    created_by = models.CharField(max_length=50, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        db_table = "ayy_inventory_stock_event"
        ordering = ["lamport_timestamp", "id"]
        indexes = [
            models.Index(fields=["store_id", "variant", "lamport_timestamp"]),
            models.Index(fields=["store_id", "event_type"]),
            models.Index(fields=["reference_type", "reference_id"]),
        ]

    def __str__(self):
        direction = "+" if self.quantity > 0 else "-"
        return f"{self.variant.sku}: {direction}{abs(self.quantity)} ({self.event_type})"


class StockLevel(models.Model):
    """
    FR-LED-001, FR-LED-002: Materialised stock level per SKU per store.

    Computed from StockEvent ledger. Regenerated on demand or via cron.
    Never updated directly — always rebuilt from events.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    store = models.ForeignKey(
        "hoc.Store", on_delete=models.CASCADE, related_name="stock_levels", null=True, blank=True,
    )
    org_store_id = models.CharField(max_length=20, default=settings.STORE_ID)
    variant = models.ForeignKey("catalogue.Variant", on_delete=models.PROTECT, related_name="stock_levels")

    on_hand = models.BigIntegerField(default=0)         # Total physical stock
    reserved = models.BigIntegerField(default=0)        # Held / customer reservations
    allocated = models.BigIntegerField(default=0)       # Pending dispatches
    in_transit = models.BigIntegerField(default=0)      # STO out, STI not yet
    pending_qc = models.BigIntegerField(default=0)      # Received but not QC-approved

    # Derived
    sellable = models.BigIntegerField(default=0)        # on_hand - reserved
    valued_at_paise = models.PositiveIntegerField(default=0)  # valuation (WAC/FIFO/MRP)

    # Tracking
    last_event_lamport = models.PositiveBigIntegerField(default=0)
    last_recomputed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "ayy_inventory_stock_level"
        unique_together = [("org_store_id", "variant")]
        indexes = [models.Index(fields=["org_store_id", "sellable"])]

    def __str__(self):
        return f"{self.org_store_id}/{self.variant.sku}: {self.sellable} sellable"

    def save(self, *args, **kwargs):
        self.sellable = max(0, self.on_hand - self.reserved - self.allocated)
        super().save(*args, **kwargs)


class StockAdjustment(models.Model):
    """FR-ADJ-001 through FR-ADJ-005: Stock adjustments with approval."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    store_id = models.CharField(max_length=20, default=settings.STORE_ID)
    variant = models.ForeignKey("catalogue.Variant", on_delete=models.PROTECT)

    adjustment_type = models.CharField(max_length=10, choices=[("positive", "+"), ("negative", "-")])
    quantity = models.PositiveIntegerField()
    reason_code = models.CharField(max_length=50, choices=REASON_CODES)
    notes = models.TextField(blank=True)

    # Approval
    initiated_by = models.CharField(max_length=50)
    approved_by = models.CharField(max_length=50, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)

    status = models.CharField(max_length=20, default="pending")

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "ayy_inventory_adjustment"
        ordering = ["-created_at"]


class StockHold(models.Model):
    """FR-BIN-002, FR-BIN-003: Stock hold/block with auto-release."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    store_id = models.CharField(max_length=20, default=settings.STORE_ID)
    variant = models.ForeignKey("catalogue.Variant", on_delete=models.PROTECT)
    quantity = models.PositiveIntegerField()

    reason = models.CharField(max_length=50, choices=[
        ("customer_reservation", "Customer Reservation"),
        ("alteration", "Alteration"),
        ("display_piece", "Display Piece"),
        ("legal_hold", "Legal Hold"),
    ])
    held_by = models.CharField(max_length=50)
    notes = models.TextField(blank=True)

    # Auto-release
    auto_release_at = models.DateTimeField(null=True, blank=True)
    released = models.BooleanField(default=False)
    released_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "ayy_inventory_stock_hold"


class StockTransfer(models.Model):
    """FR-STO-001 through FR-STO-010, FR-STI-001 through FR-STI-008: Inter-store transfers."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    transfer_number = models.CharField(max_length=30, unique=True, editable=False)

    source_store_id = models.CharField(max_length=20)
    destination_store_id = models.CharField(max_length=20)

    # Stages: indent -> approved -> dispatched -> in_transit -> received
    STATUS_DRAFT = "draft"
    STATUS_APPROVED = "approved"
    STATUS_DISPATCHED = "dispatched"
    STATUS_IN_TRANSIT = "in_transit"
    STATUS_RECEIVED = "received"
    STATUS_REJECTED = "rejected"
    STATUS_CANCELLED = "cancelled"

    status = models.CharField(max_length=20, default=STATUS_DRAFT)

    # Transport details (FR-STO-006)
    transporter = models.CharField(max_length=100, blank=True)
    vehicle_number = models.CharField(max_length=20, blank=True)
    lr_number = models.CharField(max_length=50, blank=True)
    dispatch_date = models.DateField(null=True, blank=True)
    receipt_date = models.DateField(null=True, blank=True)

    # Transfer rate
    transfer_rate_type = models.CharField(
        max_length=30,
        choices=[
            ("at_cost", "At Cost"),
            ("at_landed_cost", "At Landed Cost"),
            ("at_mrp", "At MRP"),
            ("at_transfer_price", "At Transfer Price"),
        ],
        default="at_cost",
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "ayy_inventory_transfer"


class Kit(models.Model):
    """FR-KIT-001, FR-KIT-002: Kit/Bundle — consume N components, produce 1 bundle SKU."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    store_id = models.CharField(max_length=20, default=settings.STORE_ID)
    bundle_variant = models.ForeignKey(
        "catalogue.Variant", on_delete=models.PROTECT, related_name="kits",
        limit_choices_to={"style__sub_category__hsn_code": ""},  # placeholder
    )
    kit_name = models.CharField(max_length=200)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "ayy_inventory_kit"

    def __str__(self):
        return f"{self.kit_name} ({self.bundle_variant.sku})"


class KitComponent(models.Model):
    """Component of a kit."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    kit = models.ForeignKey(Kit, on_delete=models.CASCADE, related_name="components")
    variant = models.ForeignKey("catalogue.Variant", on_delete=models.PROTECT)
    quantity = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "ayy_inventory_kit_component"
        unique_together = [("kit", "variant")]


class StockValuationMethod(models.Model):
    """FR-LED-003: Organisation-level valuation method setting."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    store_id = models.CharField(max_length=20, unique=True)
    method = models.CharField(max_length=30, choices=VALUATION_METHODS, default=VALUATION_WAC)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "ayy_inventory_valuation_method"
