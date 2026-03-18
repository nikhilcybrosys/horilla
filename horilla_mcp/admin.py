from django.contrib import admin

from horilla_mcp.models import MCPQueryLog


@admin.register(MCPQueryLog)
class MCPQueryLogAdmin(admin.ModelAdmin):
    list_display = [
        "tool_name",
        "user",
        "success",
        "latency_ms",
        "created_at",
    ]
    list_filter = ["tool_name", "success", "company_id"]
    search_fields = ["tool_name", "result_summary"]
    readonly_fields = ["tool_args", "result_summary", "error_message"]
