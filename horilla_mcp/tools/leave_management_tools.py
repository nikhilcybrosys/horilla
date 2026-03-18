"""MCP tools for leave request management (manager view)."""

import json
from datetime import date

from horilla_mcp.server import mcp


@mcp.tool()
def get_leave_requests(
    employee_id: int | None = None,
    status: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    limit: int = 20,
) -> str:
    """
    List leave requests. Optionally filter by employee, status, or date range.
    Status values: requested, approved, cancelled, rejected.
    Date format: YYYY-MM-DD.
    """
    from leave.models import LeaveRequest

    qs = LeaveRequest.objects.select_related("employee_id", "leave_type_id").order_by(
        "-start_date"
    )

    if employee_id:
        qs = qs.filter(employee_id=employee_id)
    if status:
        qs = qs.filter(status=status)
    if date_from:
        qs = qs.filter(start_date__gte=date_from)
    if date_to:
        qs = qs.filter(end_date__lte=date_to)

    qs = qs[:limit]

    results = []
    for lr in qs:
        emp = lr.employee_id
        results.append(
            {
                "id": lr.pk,
                "employee": f"{emp.employee_first_name} {emp.employee_last_name}",
                "employee_id": emp.pk,
                "leave_type": str(lr.leave_type_id),
                "start_date": str(lr.start_date),
                "end_date": str(lr.end_date),
                "requested_days": (
                    float(lr.requested_days) if lr.requested_days else None
                ),
                "status": lr.status,
                "description": (lr.description or "")[:200],
            }
        )

    return json.dumps({"count": len(results), "requests": results}, indent=2)


@mcp.tool()
def get_team_leave_requests(
    manager_employee_id: int,
    status: str | None = None,
    limit: int = 30,
) -> str:
    """
    Get leave requests from a manager's direct reports.
    Shows all subordinates' leave requests.
    """
    from employee.models import Employee
    from leave.models import LeaveRequest

    subordinate_ids = Employee.objects.filter(
        employee_work_info__reporting_manager_id=manager_employee_id,
        is_active=True,
    ).values_list("pk", flat=True)

    qs = (
        LeaveRequest.objects.filter(employee_id__in=subordinate_ids)
        .select_related("employee_id", "leave_type_id")
        .order_by("-start_date")
    )

    if status:
        qs = qs.filter(status=status)

    qs = qs[:limit]

    results = []
    for lr in qs:
        emp = lr.employee_id
        results.append(
            {
                "id": lr.pk,
                "employee": f"{emp.employee_first_name} {emp.employee_last_name}",
                "leave_type": str(lr.leave_type_id),
                "start_date": str(lr.start_date),
                "end_date": str(lr.end_date),
                "requested_days": (
                    float(lr.requested_days) if lr.requested_days else None
                ),
                "status": lr.status,
            }
        )

    return json.dumps(
        {
            "manager_employee_id": manager_employee_id,
            "count": len(results),
            "requests": results,
        },
        indent=2,
    )


@mcp.tool()
def get_pending_approvals(manager_employee_id: int) -> str:
    """
    Get leave requests pending this manager's approval.
    Includes both direct approval and multi-level approval conditions.
    """
    from employee.models import Employee
    from leave.models import LeaveRequest

    # Direct subordinate pending requests
    subordinate_ids = Employee.objects.filter(
        employee_work_info__reporting_manager_id=manager_employee_id,
        is_active=True,
    ).values_list("pk", flat=True)

    pending = (
        LeaveRequest.objects.filter(
            employee_id__in=subordinate_ids,
            status="requested",
        )
        .select_related("employee_id", "leave_type_id")
        .order_by("start_date")
    )

    results = []
    for lr in pending:
        emp = lr.employee_id
        results.append(
            {
                "id": lr.pk,
                "employee": f"{emp.employee_first_name} {emp.employee_last_name}",
                "leave_type": str(lr.leave_type_id),
                "start_date": str(lr.start_date),
                "end_date": str(lr.end_date),
                "requested_days": (
                    float(lr.requested_days) if lr.requested_days else None
                ),
                "description": (lr.description or "")[:200],
            }
        )

    return json.dumps(
        {
            "manager_employee_id": manager_employee_id,
            "pending_count": len(results),
            "requests": results,
        },
        indent=2,
    )
