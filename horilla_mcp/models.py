from django.db import models

from horilla.models import HorillaModel


class MCPQueryLog(HorillaModel):
    """Audit trail for MCP tool invocations."""

    user = models.ForeignKey(
        "horilla_auth.HorillaUser",
        on_delete=models.SET_NULL,
        null=True,
        related_name="mcp_queries",
    )
    tool_name = models.CharField(max_length=100, db_index=True)
    tool_args = models.JSONField(default=dict)
    result_summary = models.TextField(blank=True, default="")
    latency_ms = models.IntegerField(default=0)
    company_id = models.ForeignKey(
        "base.Company",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    success = models.BooleanField(default=True)
    error_message = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"MCP:{self.tool_name} by {self.user} at {self.created_at}"
