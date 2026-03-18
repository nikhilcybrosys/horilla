from django.urls import path

from horilla_mcp import views

urlpatterns = [
    path("status/", views.mcp_status, name="mcp-status"),
]
