from django.http import JsonResponse
from django.views.decorators.http import require_http_methods

from horilla.decorators import login_required
from horilla_mcp.models import MCPQueryLog


@login_required
@require_http_methods(["GET"])
def mcp_status(request):
    """MCP server status and recent query log."""
    from horilla_mcp.tools import calendar_tools, employee_tools, leave_tools

    tools = [
        {"name": "get_employee", "module": "employee_tools"},
        {"name": "search_employees", "module": "employee_tools"},
        {"name": "get_leave_balance", "module": "leave_tools"},
        {"name": "search_policies", "module": "leave_tools"},
        {"name": "get_holidays", "module": "calendar_tools"},
        {"name": "get_company_leaves", "module": "calendar_tools"},
    ]

    recent_queries = MCPQueryLog.objects.order_by("-created_at")[:10]
    recent = [
        {
            "tool": q.tool_name,
            "user": str(q.user) if q.user else None,
            "success": q.success,
            "latency_ms": q.latency_ms,
            "created_at": q.created_at.isoformat() if q.created_at else None,
        }
        for q in recent_queries
    ]

    return JsonResponse(
        {
            "server": "horilla-hr",
            "transport": "stdio",
            "tools_count": len(tools),
            "tools": tools,
            "recent_queries": recent,
        }
    )
