"""
AYY-34 — Customer and loyalty models.

Implements FR-CRM-001 through FR-CRM-008.
"""

import uuid
import re
from django.db import models


# ── Customer ──
class Customer(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    mobile = models.CharField(max_length=10, unique=True, db_index=True)
    name = models.CharField(max_length=200, blank=True)
    email = models.EmailField(blank=True)
    dob = models.DateField(null=True, blank=True)
    anniversary = models.DateField(null=True, blank=True)
    address = models.JSONField(default=dict, blank=True)
    gstin = models.CharField(max_length=15, blank=True)

    # Loyalty
    points_balance = models.PositiveIntegerField(default=0)
    tier = models.CharField(max_length=20, default="silver")  # silver, gold, platinum
    trailing_12m_spend_paise = models.PositiveIntegerField(default=0)

    # DPDP compliance
    consent_given = models.BooleanField(default=False)
    consent_given_at = models.DateTimeField(null=True, blank=True)
    consent_channel = models.CharField(max_length=50, blank=True)  # "bill", "website", "app"
    consent_withdrawn = models.BooleanField(default=False)
    consent_withdrawn_at = models.DateTimeField(null=True, blank=True)
    data_erased = models.BooleanField(default=False)

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "ayy_customers_customer"

    def __str__(self):
        return f"{self.name or self.mobile}"

    @staticmethod
    def validate_mobile(mobile):
        """FR-CRM-002: Validate 10-digit Indian mobile number."""
        return bool(re.match(r"^[6-9]\d{9}$", mobile))


# ── Customer Merge Audit ──
class CustomerMerge(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    primary_customer = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name="merges_as_primary")
    merged_customer = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name="merges_as_merged")
    reason = models.CharField(max_length=100, blank=True)
    merged_at = models.DateTimeField(auto_now_add=True)
    merged_by = models.CharField(max_length=50, blank=True)

    class Meta:
        db_table = "ayy_customers_merge"
        unique_together = [("primary_customer", "merged_customer")]


# ── Loyalty Transaction ──
class LoyaltyTransaction(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name="loyalty_transactions")

    TRANSACTION_EARN = "earn"
    TRANSACTION_REDEEM = "redeem"
    TRANSACTION_EXPIRE = "expire"
    TRANSACTION_BONUS = "bonus"

    TYPE_CHOICES = [
        (TRANSACTION_EARN, "Earn"),
        (TRANSACTION_REDEEM, "Redeem"),
        (TRANSACTION_EXPIRE, "Expired"),
        (TRANSACTION_BONUS, "Bonus"),
    ]

    transaction_type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    points = models.IntegerField()  # positive for earn/bonus, negative for redeem/expiry
    balance_after = models.PositiveIntegerField()
    reference_type = models.CharField(max_length=50, blank=True)  # "bill", "manual", "expiring"
    reference_id = models.UUIDField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "ayy_customers_loyalty_transaction"
        ordering = ["-created_at"]


# ── Coupon ──
class Coupon(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=30, unique=True)
    description = models.CharField(max_length=200, blank=True)
    coupon_type = models.CharField(max_length=20, choices=[
        ("flat_pct", "Flat % Discount"),
        ("flat_rs", "Flat Rs Discount"),
        ("buy_x_get_y", "Buy X Get Y"),
        ("bundle_price", "Bundle Price"),
    ])
    value = models.DecimalField(max_digits=10, decimal_places=2)
    min_purchase_paise = models.PositiveIntegerField(default=0)
    max_discount_paise = models.PositiveIntegerField(default=0)

    # Validity
    valid_from = models.DateField()
    valid_to = models.DateField()
    usage_limit = models.PositiveIntegerField(null=True, blank=True)  # None = unlimited
    usage_count = models.PositiveIntegerField(default=0)

    # Customer-specific
    customer_specific = models.BooleanField(default=False)
    assigned_to = models.ForeignKey(Customer, on_delete=models.SET_NULL, null=True, blank=True)

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "ayy_customers_coupon"
