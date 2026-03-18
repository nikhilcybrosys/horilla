from django.contrib import admin

from horilla_rag.models import EmbeddingDocument, InsightAlert, RAGQueryLog


@admin.register(EmbeddingDocument)
class EmbeddingDocumentAdmin(admin.ModelAdmin):
    list_display = [
        "document_type",
        "source_model",
        "source_id",
        "token_count",
        "company_id",
        "created_at",
    ]
    list_filter = ["document_type", "company_id"]
    search_fields = ["content_text", "source_model"]
    readonly_fields = ["content_hash", "embedding", "token_count"]


@admin.register(RAGQueryLog)
class RAGQueryLogAdmin(admin.ModelAdmin):
    list_display = [
        "user",
        "query_type",
        "results_count",
        "latency_ms",
        "created_at",
    ]
    list_filter = ["query_type", "company_id"]
    search_fields = ["query_text"]
    readonly_fields = ["query_text", "response_text"]


@admin.register(InsightAlert)
class InsightAlertAdmin(admin.ModelAdmin):
    list_display = [
        "alert_type",
        "severity",
        "title",
        "is_read",
        "company_id",
        "created_at",
    ]
    list_filter = ["alert_type", "severity", "is_read", "company_id"]
    search_fields = ["title", "description"]
