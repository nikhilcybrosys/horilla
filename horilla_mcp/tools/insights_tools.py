"""MCP tools for proactive HR insights and dashboard summary."""

import json

from horilla_mcp.server import mcp


@mcp.tool()
def get_insights(
    alert_type: str | None = None,
    unread_only: bool = True,
    limit: int = 10,
) -> str:
    """
    Get current HR insight alerts. Types: attendance, leave_balance,
    contract_expiry, birthday, capacity, probation.
    """
    from horilla_rag.models import InsightAlert

    qs = InsightAlert.objects.filter(is_active=True)
    if unread_only:
        qs = qs.filter(is_read=False)
    if alert_type:
        qs = qs.filter(alert_type=alert_type)

    qs = qs.order_by("-severity", "-created_at")[:limit]

    results = []
    for alert in qs:
        results.append(
            {
                "id": alert.pk,
                "type": alert.alert_type,
                "severity": alert.severity,
                "title": alert.title,
                "description": alert.description[:500],
                "created_at": (
                    alert.created_at.isoformat() if alert.created_at else None
                ),
                "is_read": alert.is_read,
                "employee_count": alert.related_employees.count(),
            }
        )

    return json.dumps(
        {
            "count": len(results),
            "alerts": results,
        },
        indent=2,
    )


@mcp.tool()
def mark_insight_read(alert_id: int) -> str:
    """Mark an insight alert as read."""
    from horilla_rag.models import InsightAlert

    alert = InsightAlert.objects.filter(pk=alert_id).first()
    if not alert:
        return json.dumps({"error": f"Alert {alert_id} not found"})

    alert.is_read = True
    alert.save()
    return json.dumps(
        {"success": True, "message": f"Alert '{alert.title}' marked as read"}
    )


@mcp.tool()
def get_hr_dashboard_summary() -> str:
    """
    Single-call summary combining headcount, today's attendance,
    pending approvals, active alerts, and recruitment status.
    Ideal for a quick daily briefing.
    """
    from datetime import date

    from employee.models import Employee

    today = date.today()
    summary = {}

    # Headcount
    summary["total_active_employees"] = Employee.objects.filter(is_active=True).count()

    # Today's attendance
    try:
        from attendance.models import Attendance

        present = Attendance.objects.filter(attendance_date=today).count()
        summary["present_today"] = present
        summary["absent_today"] = summary["total_active_employees"] - present
    except ImportError:
        pass

    # Pending leave approvals
    try:
        from leave.models import LeaveRequest

        summary["pending_leave_requests"] = LeaveRequest.objects.filter(
            status="requested"
        ).count()
    except ImportError:
        pass

    # Active alerts
    try:
        from horilla_rag.models import InsightAlert

        summary["unread_alerts"] = InsightAlert.objects.filter(
            is_active=True, is_read=False
        ).count()
        summary["critical_alerts"] = InsightAlert.objects.filter(
            is_active=True, is_read=False, severity="critical"
        ).count()
    except Exception:
        pass

    # Open recruitments
    try:
        from recruitment.models import Recruitment

        summary["open_recruitments"] = Recruitment.objects.filter(
            closed=False, is_active=True
        ).count()
    except ImportError:
        pass

    summary["date"] = str(today)

    return json.dumps(summary, indent=2)
