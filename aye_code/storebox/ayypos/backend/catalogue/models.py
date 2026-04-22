"""
AYY-34 — Catalogue models (FR-CAT-001 through FR-CAT-010).

Matrix-based product catalogue: Category -> Sub-category -> Style -> Colour x Size -> SKU.
"""

import uuid
import binascii
from decimal import Decimal, ROUND_HALF_UP

from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator


# ── GST HSN codes with standard slabs ──
HSN_SLABS = {
    "0906": "Spices",
    "6109": "T-shirts & singlets",
    "6110": "Sweaters & pullovers",
    "6203": "Men's garments (woven)",
    "6204": "Women's garments (woven)",
    "6103": "Men's garments (knitted)",
    "6104": "Women's garments (knitted)",
    "6115": "Pantyhose & tights",
    "6217": "Made-up accessories",
    "5111": "Sarees & dhotis (silk)",
    "6117": "Fashion accessories",
    "6403": "Footwear (sports)",
    "6404": "Footwear (casual)",
}


class Category(models.Model):
    """FR-CAT-001: Top-level category (e.g. Men, Women, Kids, Accessories)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, unique=True)
    code = models.CharField(max_length=20, unique=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "ayy_catalogue_category"
        ordering = ["code"]

    def __str__(self):
        return f"{self.code} — {self.name}"


class SubCategory(models.Model):
    """FR-CAT-001: Sub-category within a category (e.g. T-Shirts, Jeans, Kurtas)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name="subcategories")
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=30)
    hsn_code = models.CharField(max_length=10, choices=HSN_SLABS, default="6109")
    gst_slab = models.DecimalField(max_digits=5, decimal_places=2, default=12)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "ayy_catalogue_subcategory"
        unique_together = [("category", "code")]
        ordering = ["code"]

    def __str__(self):
        return f"{self.category.code}/{self.code} — {self.name}"


class Style(models.Model):
    """FR-CAT-001, FR-CAT-004, FR-CAT-007: A product design with colour x size matrix."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    sub_category = models.ForeignKey(SubCategory, on_delete=models.PROTECT, related_name="styles")
    style_name = models.CharField(max_length=200)
    style_code = models.CharField(max_length=50)
    description = models.TextField(blank=True)
    images = models.JSONField(default=list, blank=True)  # list of image URLs (up to 10)
    season = models.CharField(max_length=50, blank=True)
    collection = models.CharField(max_length=100, blank=True)
    launch_date = models.DateField(null=True, blank=True)
    end_of_life_date = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "ayy_catalogue_style"
        unique_together = [("sub_category", "style_code")]
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.style_code} — {self.style_name}"

    @property
    def variant_count(self):
        return self.variants.count()

    @property
    def hsn_code(self):
        return self.sub_category.hsn_code

    @property
    def gst_slab(self):
        return self.sub_category.gst_slab


class Colour(models.Model):
    """Allowed colours for the style matrix."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=50, unique=True)
    hex_code = models.CharField(max_length=7, blank=True)  # optional for UI display

    class Meta:
        db_table = "ayy_catalogue_colour"
        ordering = ["name"]

    def __str__(self):
        return self.name


class Size(models.Model):
    """Allowed sizes for the style matrix."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=20, unique=True)  # S, M, L, XL, 38, etc.
    code = models.CharField(max_length=10, unique=True)
    unit = models.CharField(max_length=10, default="piece")  # piece, dozen, meter

    class Meta:
        db_table = "ayy_catalogue_size"
        ordering = ["code"]

    def __str__(self):
        return self.name


class Variant(models.Model):
    """FR-CAT-002, FR-CAT-003: A single colour x size combination (one SKU)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    style = models.ForeignKey(Style, on_delete=models.PROTECT, related_name="variants")
    colour = models.ForeignKey(Colour, on_delete=models.PROTECT)
    size = models.ForeignKey(Size, on_delete=models.PROTECT)

    sku = models.CharField(max_length=30, unique=True, editable=False)
    barcode = models.CharField(max_length=13, unique=True, editable=False)  # EAN-13

    mrp_paise = models.PositiveIntegerField(help_text="MRP in paise (Rs * 100)")
    cost_price_paise = models.PositiveIntegerField(help_text="Cost price in paise")
    selling_price_paise = models.PositiveIntegerField(help_text="Selling price in paise")

    # Dual-MRP support (FR-CAT-010): old MRP during transition period
    old_mrp_paise = models.PositiveIntegerField(null=True, blank=True)

    # Stock tracking
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "ayy_catalogue_variant"
        unique_together = [("style", "colour", "size")]
        ordering = ["style", "colour", "size"]
        indexes = [
            models.Index(fields=["barcode"]),
            models.Index(fields=["style", "colour", "size"]),
        ]

    def __str__(self):
        return f"{self.style.style_code} | {self.colour.name} | {self.size.name} | {self.sku}"

    def save(self, *args, **kwargs):
        # Auto-generate SKU: style_code-colour_name-size_code
        if not self.sku:
            self.sku = f"{self.style.style_code}-{self.colour.name}-{self.size.code}"
        # Auto-generate EAN-13 barcode if not set
        if not self.barcode:
            self.barcode = self._generate_ean13()
        super().save(*args, **kwargs)

    def _generate_ean13(self):
        """FR-CAT-003: Auto-generate EAN-13 barcode from UUID."""
        raw = str(uuid.uuid4().int)[:12]
        # EAN-13 check digit calculation
        total = 0
        for i, d in enumerate(raw):
            if i % 2 == 0:
                total += int(d) * 1
            else:
                total += int(d) * 3
        check = (10 - (total % 10)) % 10
        return raw + str(check)

    @property
    def mrp_rupees(self):
        return Decimal(self.mrp_paise) / 100

    @property
    def selling_price_rupees(self):
        return Decimal(self.selling_price_paise) / 100

    @property
    def full_label(self):
        return f"{self.style.style_name} | {self.colour.name} | {self.size.name}"


class StatePriceOverride(models.Model):
    """FR-CAT-005: Different MRPs and selling prices per state (GSTIN group)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    variant = models.ForeignKey(Variant, on_delete=models.CASCADE, related_name="state_prices")
    gstin_state_code = models.CharField(max_length=2, help_text="2-digit GSTIN state code")
    mrp_paise = models.PositiveIntegerField()
    selling_price_paise = models.PositiveIntegerField()
    effective_from = models.DateField()
    effective_to = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "ayy_catalogue_state_price"
        unique_together = [("variant", "gstin_state_code")]

    def __str__(self):
        return f"{self.variant.sku} @ state {self.gstin_state_code}"
