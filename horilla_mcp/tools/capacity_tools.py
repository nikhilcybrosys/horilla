"""MCP tools for team capacity forecasting."""

import json

from horilla_mcp.server import mcp


@mcp.tool()
def get_team_capacity(
    department: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
) -> str:
    """
    Forecast team capacity for a date range. Shows day-by-day availability
    accounting for approved leaves, holidays, and company leaves.
    Defaults to next 14 days. Optionally filter by department name.
    """
    from datetime import date

    from horilla_rag.services.capacity_service import CapacityService

    start = date.fromisoformat(date_from) if date_from else None
    end = date.fromisoformat(date_to) if date_to else None

    department_id = None
    if department:
        from base.models import Department

        dept = Department.objects.filter(department__icontains=department).first()
        if dept:
            department_id = dept.pk

    svc = CapacityService()
    result = svc.forecast(
        department_id=department_id,
        date_from=start,
        date_to=end,
    )

    return json.dumps(result, indent=2)


@mcp.tool()
def get_critical_capacity_days(
    threshold: float = 50.0,
    days_ahead: int = 30,
) -> str:
    """
    Find upcoming working days where team capacity drops below a threshold.
    Default threshold: 50%. Looks ahead 30 days.
    """
    from datetime import date, timedelta

    from horilla_rag.services.capacity_service import CapacityService

    today = date.today()
    svc = CapacityService()
    result = svc.forecast(
        date_from=today,
        date_to=today + timedelta(days=days_ahead),
    )

    critical = [
        day
        for day in result.get("daily_forecast", [])
        if day.get("type") == "working" and day.get("capacity_pct", 100) < threshold
    ]

    return json.dumps(
        {
            "threshold_pct": threshold,
            "days_ahead": days_ahead,
            "critical_days_count": len(critical),
            "critical_days": critical,
            "average_capacity_pct": result.get("average_capacity_pct", 0),
        },
        indent=2,
    )
