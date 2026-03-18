"""MCP tools for attendance queries."""

import json
from datetime import date

from horilla_mcp.server import mcp


@mcp.tool()
def get_attendance_today(department: str | None = None) -> str:
    """
    Get today's attendance summary: who's present, absent, and on leave.
    Optionally filter by department name.
    """
    from attendance.models import Attendance
    from employee.models import Employee

    today = date.today()
    employees = Employee.objects.filter(is_active=True)

    if department:
        employees = employees.filter(
            employee_work_info__department_id__department__icontains=department
        )

    total = employees.count()

    present_ids = Attendance.objects.filter(
        attendance_date=today,
        employee_id__in=employees,
    ).values_list("employee_id", flat=True)

    present_count = len(set(present_ids))
    absent_count = total - present_count

    # Get who's on leave today
    on_leave = []
    try:
        from leave.models import LeaveRequest

        leave_today = LeaveRequest.objects.filter(
            status="approved",
            start_date__lte=today,
            end_date__gte=today,
            employee_id__in=employees,
        ).select_related("employee_id", "leave_type_id")

        for lr in leave_today:
            emp = lr.employee_id
            on_leave.append(
                {
                    "employee": f"{emp.employee_first_name} {emp.employee_last_name}",
                    "leave_type": str(lr.leave_type_id),
                }
            )
    except ImportError:
        pass

    return json.dumps(
        {
            "date": str(today),
            "department": department or "All",
            "total_employees": total,
            "present": present_count,
            "absent": absent_count,
            "on_leave_count": len(on_leave),
            "on_leave": on_leave[:20],
        },
        indent=2,
    )


@mcp.tool()
def get_employee_attendance(
    employee_id: int,
    month: int | None = None,
    year: int | None = None,
) -> str:
    """
    Get monthly attendance summary for a specific employee.
    Defaults to current month/year.
    Returns: days present, worked hours, overtime, pending hours, late arrivals.
    """
    from attendance.models import (
        Attendance,
        AttendanceLateComeEarlyOut,
        AttendanceOverTime,
    )
    from employee.models import Employee

    today = date.today()
    month = month or today.month
    year = year or today.year

    emp = Employee.objects.filter(pk=employee_id).first()
    if not emp:
        return json.dumps({"error": f"Employee {employee_id} not found"})

    # Get AttendanceOverTime for the month
    month_names = [
        "",
        "january",
        "february",
        "march",
        "april",
        "may",
        "june",
        "july",
        "august",
        "september",
        "october",
        "november",
        "december",
    ]
    month_name = month_names[month]

    ot = AttendanceOverTime.objects.filter(
        employee_id=employee_id,
        month=month_name,
        year=str(year),
    ).first()

    # Count days present
    attendances = Attendance.objects.filter(
        employee_id=employee_id,
        attendance_date__month=month,
        attendance_date__year=year,
    )
    days_present = attendances.count()

    # Late arrivals and early departures
    late_count = AttendanceLateComeEarlyOut.objects.filter(
        attendance_id__employee_id=employee_id,
        attendance_id__attendance_date__month=month,
        attendance_id__attendance_date__year=year,
        type="late_come",
    ).count()

    early_count = AttendanceLateComeEarlyOut.objects.filter(
        attendance_id__employee_id=employee_id,
        attendance_id__attendance_date__month=month,
        attendance_id__attendance_date__year=year,
        type="early_out",
    ).count()

    result = {
        "employee": f"{emp.employee_first_name} {emp.employee_last_name}",
        "employee_id": emp.pk,
        "month": month,
        "year": year,
        "days_present": days_present,
        "worked_hours": ot.worked_hours if ot else "00:00",
        "pending_hours": ot.pending_hours if ot else "00:00",
        "overtime": ot.overtime if ot else "00:00",
        "late_arrivals": late_count,
        "early_departures": early_count,
    }

    return json.dumps(result, indent=2)


@mcp.tool()
def get_team_attendance(manager_employee_id: int) -> str:
    """
    Get current month's attendance summary for all direct reports.
    Shows each team member's days present, overtime, and late arrivals.
    """
    from attendance.models import Attendance, AttendanceLateComeEarlyOut
    from employee.models import Employee

    today = date.today()
    month = today.month
    year = today.year

    subordinates = Employee.objects.filter(
        employee_work_info__reporting_manager_id=manager_employee_id,
        is_active=True,
    )

    results = []
    for emp in subordinates:
        days_present = Attendance.objects.filter(
            employee_id=emp.pk,
            attendance_date__month=month,
            attendance_date__year=year,
        ).count()

        late_count = AttendanceLateComeEarlyOut.objects.filter(
            attendance_id__employee_id=emp.pk,
            attendance_id__attendance_date__month=month,
            attendance_id__attendance_date__year=year,
            type="late_come",
        ).count()

        results.append(
            {
                "employee": f"{emp.employee_first_name} {emp.employee_last_name}",
                "employee_id": emp.pk,
                "days_present": days_present,
                "late_arrivals": late_count,
            }
        )

    return json.dumps(
        {
            "manager_employee_id": manager_employee_id,
            "month": month,
            "year": year,
            "team_count": len(results),
            "team": results,
        },
        indent=2,
    )
