"""AYY-27 — URL routes for the till POS interface."""
from django.urls import path
from . import views

app_name = "till"

urlpatterns = [
    path("", views.till_home, name="home"),
    path("cart/", views.cart_view, name="cart"),
    path("cart/add/", views.cart_add, name="cart-add"),
    path("cart/remove/", views.cart_remove, name="cart-remove"),
    path("checkout/", views.checkout_view, name="checkout"),
    path("receipt/<int:invoice_id>/", views.receipt_view, name="receipt"),
]
