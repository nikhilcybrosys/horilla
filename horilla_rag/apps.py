from django.apps import AppConfig
from django.conf import settings


class HorillaRagConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "horilla_rag"

    def ready(self):
        from django.urls import include, path

        import horilla_rag.signals  # noqa: F401
        from horilla.urls import urlpatterns

        settings.APPS.append("horilla_rag")
        urlpatterns.append(
            path("rag/", include("horilla_rag.urls")),
        )

        # Start background scheduler for batch re-indexing
        from horilla_rag.scheduler import start_scheduler

        start_scheduler()

        super().ready()
