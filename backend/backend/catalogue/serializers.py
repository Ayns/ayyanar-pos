"""
AYY-34 — Catalogue serializers.
"""

from rest_framework import serializers
from .models import (
    Category, SubCategory, Style, Colour, Size, Variant, StatePriceOverride,
)


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ["id", "name", "code", "description", "is_active", "created_at"]


class SubCategorySerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source="category.name", read_only=True)

    class Meta:
        model = SubCategory
        fields = ["id", "category", "category_name", "name", "code", "hsn_code", "gst_slab", "is_active", "created_at"]


class StyleSerializer(serializers.ModelSerializer):
    sub_category_name = serializers.CharField(source="sub_category.name", read_only=True)
    sub_category_code = serializers.CharField(source="sub_category.code", read_only=True)
    hsn_code = serializers.CharField(source="sub_category.hsn_code", read_only=True)
    gst_slab = serializers.DecimalField(source="sub_category.gst_slab", max_digits=5, decimal_places=2, read_only=True)
    variant_count = serializers.ReadOnlyField()

    class Meta:
        model = Style
        fields = [
            "id", "sub_category", "sub_category_name", "sub_category_code",
            "style_name", "style_code", "description", "images",
            "season", "collection", "launch_date", "end_of_life_date",
            "hsn_code", "gst_slab", "is_active", "variant_count",
            "created_at", "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at", "variant_count", "hsn_code", "gst_slab"]


class ColourSerializer(serializers.ModelSerializer):
    class Meta:
        model = Colour
        fields = ["id", "name", "hex_code"]


class SizeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Size
        fields = ["id", "name", "code", "unit"]


class VariantSerializer(serializers.ModelSerializer):
    style_name = serializers.CharField(source="style.style_name", read_only=True)
    style_code = serializers.CharField(source="style.style_code", read_only=True)
    colour_name = serializers.CharField(source="colour.name", read_only=True)
    size_name = serializers.CharField(source="size.name", read_only=True)
    hsn_code = serializers.CharField(source="style.hsn_code", read_only=True)
    gst_slab = serializers.DecimalField(source="style.gst_slab", max_digits=5, decimal_places=2, read_only=True)
    mrp_rupees = serializers.SerializerMethodField()
    full_label = serializers.ReadOnlyField()

    class Meta:
        model = Variant
        fields = [
            "id", "style", "colour", "size", "sku", "barcode",
            "mrp_paise", "mrp_rupees", "cost_price_paise", "selling_price_paise",
            "old_mrp_paise", "full_label",
            "style_name", "style_code", "colour_name", "size_name",
            "hsn_code", "gst_slab",
            "is_active", "created_at",
        ]
        read_only_fields = ["id", "sku", "barcode", "created_at", "full_label"]

    def get_mrp_rupees(self, obj):
        from decimal import Decimal
        return Decimal(obj.mrp_paise) / 100


class VariantMatrixSerializer(serializers.ModelSerializer):
    """Variant serializer optimised for matrix grid display."""
    colour_name = serializers.CharField(source="colour.name", read_only=True)
    size_name = serializers.CharField(source="size.name", read_only=True)
    mrp_rupees = serializers.SerializerMethodField()

    class Meta:
        model = Variant
        fields = [
            "id", "sku", "barcode", "colour_name", "size_name",
            "mrp_paise", "mrp_rupees", "selling_price_paise",
            "cost_price_paise", "is_active",
        ]

    def get_mrp_rupees(self, obj):
        from decimal import Decimal
        return Decimal(obj.mrp_paise) / 100


class StatePriceOverrideSerializer(serializers.ModelSerializer):
    class Meta:
        model = StatePriceOverride
        fields = ["id", "variant", "gstin_state_code", "mrp_paise", "selling_price_paise", "effective_from", "effective_to"]


class BarcodeLabelSerializer(serializers.Serializer):
    variant_ids = serializers.ListField(child=serializers.UUIDField(), min_length=1)
    label_size = serializers.ChoiceField(choices=["50x25", "40x20"], default="50x25")
