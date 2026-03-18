from django.apps import AppConfig
from django.conf import settings


class HorillaMcpConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "horilla_mcp"

    def ready(self):
        from django.urls import include, path

        from horilla.urls import urlpatterns

        settings.APPS.append("horilla_mcp")
        urlpatterns.append(
            path("mcp/", include("horilla_mcp.urls")),
        )
        super().ready()
