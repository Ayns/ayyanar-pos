"""
AYY-34 — Catalogue URL routes.
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register(r"categories", views.CategoryViewSet, basename="category")
router.register(r"subcategories", views.SubCategoryViewSet, basename="subcategory")
router.register(r"styles", views.StyleViewSet, basename="style")
router.register(r"colours", views.ColourViewSet, basename="colour")
router.register(r"sizes", views.SizeViewSet, basename="size")
router.register(r"variants", views.VariantViewSet, basename="variant")

urlpatterns = [
    path("", include(router.urls)),
    path("search/", views.CatalogueSearchView.as_view(), name="catalogue-search"),
    path("labels/", views.BarcodeLabelPrintView.as_view(), name="barcode-labels"),
]
