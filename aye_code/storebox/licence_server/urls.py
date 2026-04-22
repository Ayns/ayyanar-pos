"""Licence server URLs."""
from django.urls import path
from . import views

app_name = "licence_server"

urlpatterns = [
    path("issue/", views.issue_licence, name="issue"),
    path("validate/", views.validate_licence, name="validate"),
]
