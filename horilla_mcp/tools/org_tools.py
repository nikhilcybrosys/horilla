"""MCP tools for organizational structure queries."""

import json
from datetime import date, timedelta

from horilla_mcp.server import mcp


@mcp.tool()
def get_org_chart(department: str | None = None) -> str:
    """
    Get organizational hierarchy showing reporting relationships.
    Optionally filter by department name.
    Returns a tree of managers and their direct reports.
    """
    from employee.models import Employee

    qs = Employee.objects.filter(is_active=True).select_related(
        "employee_work_info",
        "employee_work_info__department_id",
        "employee_work_info__job_position_id",
        "employee_work_info__reporting_manager_id",
    )

    if department:
        qs = qs.filter(
            employee_work_info__department_id__department__icontains=department
        )

    # Build manager → reports mapping
    manager_map = {}
    all_employees = {}

    for emp in qs:
        work_info = getattr(emp, "employee_work_info", None)
        emp_data = {
            "id": emp.pk,
            "name": f"{emp.employee_first_name} {emp.employee_last_name}",
            "position": (
                str(work_info.job_position_id)
                if work_info and work_info.job_position_id
                else None
            ),
            "department": (
                str(work_info.department_id)
                if work_info and work_info.department_id
                else None
            ),
        }
        all_employees[emp.pk] = emp_data

        manager_pk = None
        if work_info and work_info.reporting_manager_id:
            manager_pk = work_info.reporting_manager_id.pk

        if manager_pk not in manager_map:
            manager_map[manager_pk] = []
        manager_map[manager_pk].append(emp_data)

    # Find top-level managers (those with no manager or manager outside the set)
    top_level = manager_map.get(None, [])

    def build_tree(emp_data):
        emp_data["reports"] = []
        if emp_data["id"] in manager_map:
            for report in manager_map[emp_data["id"]]:
                emp_data["reports"].append(build_tree(report))
        return emp_data

    tree = [build_tree(e) for e in top_level]

    return json.dumps(
        {
            "department": department or "All",
            "total_employees": len(all_employees),
            "hierarchy": tree,
        },
        indent=2,
    )


@mcp.tool()
def get_department_summary() -> str:
    """
    Get summary of all departments with headcount, managers, and positions.
    """
    from base.models import Department
    from employee.models import Employee

    departments = Department.objects.all()
    results = []

    for dept in departments:
        employees = Employee.objects.filter(
            employee_work_info__department_id=dept,
            is_active=True,
        )
        headcount = employees.count()

        results.append(
            {
                "department": str(dept),
                "id": dept.pk,
                "headcount": headcount,
            }
        )

    results.sort(key=lambda x: x["headcount"], reverse=True)

    return json.dumps(
        {
            "total_departments": len(results),
            "departments": results,
        },
        indent=2,
    )


@mcp.tool()
def get_team_calendar(
    manager_employee_id: int,
    date_from: str | None = None,
    date_to: str | None = None,
) -> str:
    """
    Show team availability calendar for a manager's direct reports.
    Shows who is on leave or has leave planned in the given date range.
    Defaults to the next 14 days.
    """
    from employee.models import Employee

    today = date.today()
    start = date.fromisoformat(date_from) if date_from else today
    end = date.fromisoformat(date_to) if date_to else today + timedelta(days=14)

    subordinates = Employee.objects.filter(
        employee_work_info__reporting_manager_id=manager_employee_id,
        is_active=True,
    )

    team_calendar = []

    try:
        from leave.models import LeaveRequest

        for emp in subordinates:
            leave_requests = LeaveRequest.objects.filter(
                employee_id=emp.pk,
                status="approved",
                start_date__lte=end,
                end_date__gte=start,
            ).select_related("leave_type_id")

            leaves = []
            for lr in leave_requests:
                leaves.append(
                    {
                        "leave_type": str(lr.leave_type_id),
                        "from": str(lr.start_date),
                        "to": str(lr.end_date),
                        "days": float(lr.requested_days) if lr.requested_days else None,
                    }
                )

            team_calendar.append(
                {
                    "employee": f"{emp.employee_first_name} {emp.employee_last_name}",
                    "employee_id": emp.pk,
                    "available": len(leaves) == 0,
                    "planned_leaves": leaves,
                }
            )
    except ImportError:
        for emp in subordinates:
            team_calendar.append(
                {
                    "employee": f"{emp.employee_first_name} {emp.employee_last_name}",
                    "employee_id": emp.pk,
                    "available": True,
                    "planned_leaves": [],
                }
            )

    return json.dumps(
        {
            "manager_employee_id": manager_employee_id,
            "date_from": str(start),
            "date_to": str(end),
            "team_count": len(team_calendar),
            "team": team_calendar,
        },
        indent=2,
    )
