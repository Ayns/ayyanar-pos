"""
AYY-34 — Catalogue views.

API endpoints for catalogue management (CRUD, search, barcode label printing).
Implements FR-CAT-001 through FR-CAT-010.
"""

from decimal import Decimal

from django.db import transaction
from django.db.models import Q, F, Prefetch
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import (
    Category, SubCategory, Style, Colour, Size, Variant, StatePriceOverride,
)
from .serializers import (
    CategorySerializer, SubCategorySerializer, StyleSerializer,
    ColourSerializer, SizeSerializer, VariantSerializer,
    StatePriceOverrideSerializer, VariantMatrixSerializer,
    BarcodeLabelSerializer,
)


class CategoryViewSet(viewsets.ModelViewSet):
    """FR-CAT-001: CRUD for product categories."""

    queryset = Category.objects.filter(is_active=True)
    serializer_class = CategorySerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ["is_active"]
    search_fields = ["name", "code"]

    def get_queryset(self):
        qs = Category.objects.all()
        if self.request.query_params.get("active_only") == "true":
            qs = qs.filter(is_active=True)
        return qs.order_by("code")


class SubCategoryViewSet(viewsets.ModelViewSet):
    """FR-CAT-001: CRUD for sub-categories with category hierarchy."""

    queryset = SubCategory.objects.filter(is_active=True)
    serializer_class = SubCategorySerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ["category", "is_active"]
    search_fields = ["name", "code"]

    def get_queryset(self):
        return SubCategory.objects.select_related("category").order_by("category__code", "code")


class StyleViewSet(viewsets.ModelViewSet):
    """FR-CAT-002, FR-CAT-004, FR-CAT-007: CRUD for styles."""

    queryset = Style.objects.select_related("sub_category__category")
    serializer_class = StyleSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ["sub_category", "is_active", "season", "collection"]
    search_fields = ["style_name", "style_code"]

    def get_queryset(self):
        return Style.objects.select_related(
            "sub_category", "sub_category__category"
        ).prefetch_related(
            Prefetch("variants", queryset=Variant.objects.select_related("colour", "size"))
        ).order_by("-created_at")

    @action(detail=True, methods=["get"])
    def matrix(self, request, pk=None):
        """FR-CAT-002: Return the full colour x size matrix for a style."""
        style = self.get_object()
        variants = style.variants.select_related("colour", "size").order_by("colour__name", "size__code")
        serializer = VariantMatrixSerializer(variants, many=True)
        return Response({
            "style": style.style_code,
            "style_name": style.style_name,
            "variants": serializer.data,
            "total_variants": variants.count(),
        })


class ColourViewSet(viewsets.ReadOnlyModelViewSet):
    """Read-only CRUD for colours."""

    queryset = Colour.objects.all()
    serializer_class = ColourSerializer
    filter_backends = [filters.SearchFilter]
    search_fields = ["name"]


class SizeViewSet(viewsets.ReadOnlyModelViewSet):
    """Read-only CRUD for sizes."""

    queryset = Size.objects.all()
    serializer_class = SizeSerializer
    filter_backends = [filters.SearchFilter]
    search_fields = ["name", "code"]


class VariantViewSet(viewsets.ModelViewSet):
    """FR-CAT-002, FR-CAT-003: CRUD for variants (SKUs)."""

    queryset = Variant.objects.select_related("style", "colour", "size")
    serializer_class = VariantSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ["style", "colour", "size", "is_active"]
    search_fields = ["sku", "barcode", "style__style_name"]

    def get_queryset(self):
        return Variant.objects.select_related(
            "style", "style__sub_category", "colour", "size"
        ).order_by("style__sub_category__code", "colour__name", "size__code")

    @action(detail=True, methods=["get"])
    def stock(self, request, pk=None):
        """Return current stock for a variant."""
        from ayypos.backend.inventory.models import StockLevel

        variant = self.get_object()
        store_id = request.query_params.get("store_id")
        if store_id:
            stock = StockLevel.objects.filter(variant=variant, store__id=store_id).first()
        else:
            stock = None

        return Response({
            "variant_id": variant.id,
            "sku": variant.sku,
            "full_label": variant.full_label,
            "current_stock": stock.on_hand if stock else None,
            "reserved_stock": stock.reserved if stock else 0,
            "sellable_stock": (stock.on_hand - stock.reserved) if stock else 0,
        })


class BarcodeLabelPrintView(APIView):
    """FR-CAT-009, FR-CAT-010: Generate barcode label data for printing."""

    def post(self, request):
        """Generate label data for one or more variants."""
        serializer = BarcodeLabelSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        labels = []
        variant_ids = serializer.validated_data.get("variant_ids", [])
        label_size = serializer.validated_data.get("label_size", "50x25")

        for vid in variant_ids:
            try:
                v = Variant.objects.get(id=vid)
                label = {
                    "size": label_size,
                    "style_code": v.style.style_code,
                    "style_name": v.style.style_name,
                    "colour": v.colour.name,
                    "size": v.size.name,
                    "sku": v.sku,
                    "barcode": v.barcode,
                    "mrp": f"Rs {Decimal(v.mrp_paise) / 100}",
                    "hsn": v.style.hsn_code,
                    "dual_mrp": f"Old: Rs {Decimal(v.old_mrp_paise) / 100}" if v.old_mrp_paise else None,
                }
                labels.append(label)
            except Variant.DoesNotExist:
                continue

        return Response({"labels": labels, "count": len(labels)})


class CatalogueSearchView(APIView):
    """Fast search across the full catalogue — optimised for POS use (FR-POS-001, FR-POS-002)."""

    def get(self, request):
        query = request.query_params.get("q", "").strip()
        if not query:
            return Response({"variants": []})

        # Search by barcode, SKU, style code, or style name
        results = Variant.objects.select_related(
            "style", "style__sub_category", "colour", "size"
        ).filter(
            Q(barcode__icontains=query)
            | Q(sku__icontains=query)
            | Q(style__style_code__icontains=query)
            | Q(style__style_name__icontains=query)
            | Q(barcode=query)  # exact barcode match
        )[:50]

        serializer = VariantSerializer(results, many=True)
        return Response({"variants": serializer.data, "count": results.count()})
