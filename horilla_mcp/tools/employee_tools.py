"""MCP tools for employee data queries."""

import json

from django.db.models import Q

from horilla_mcp.server import mcp


@mcp.tool()
def get_employee(
    employee_id: int | None = None,
    badge_id: str | None = None,
    email: str | None = None,
) -> str:
    """
    Look up an employee by ID, badge ID, or email.
    Returns profile details including department, position, manager, and contact info.
    At least one of employee_id, badge_id, or email must be provided.
    """
    from employee.models import Employee

    if employee_id:
        emp = Employee.objects.filter(pk=employee_id, is_active=True).first()
    elif badge_id:
        emp = Employee.objects.filter(badge_id=badge_id, is_active=True).first()
    elif email:
        emp = Employee.objects.filter(email=email, is_active=True).first()
    else:
        return json.dumps({"error": "Provide employee_id, badge_id, or email"})

    if not emp:
        return json.dumps({"error": "Employee not found"})

    result = {
        "id": emp.pk,
        "badge_id": emp.badge_id,
        "first_name": emp.employee_first_name,
        "last_name": emp.employee_last_name,
        "email": emp.email,
        "phone": emp.phone,
        "gender": emp.gender,
        "is_active": emp.is_active,
    }

    work_info = getattr(emp, "employee_work_info", None)
    if work_info:
        result["work_info"] = {
            "department": (
                str(work_info.department_id) if work_info.department_id else None
            ),
            "job_position": (
                str(work_info.job_position_id) if work_info.job_position_id else None
            ),
            "job_role": str(work_info.job_role_id) if work_info.job_role_id else None,
            "reporting_manager": (
                f"{work_info.reporting_manager_id.employee_first_name} "
                f"{work_info.reporting_manager_id.employee_last_name}"
                if work_info.reporting_manager_id
                else None
            ),
            "company": str(work_info.company_id) if work_info.company_id else None,
            "shift": str(work_info.shift_id) if work_info.shift_id else None,
            "work_type": (
                str(work_info.work_type_id) if work_info.work_type_id else None
            ),
            "employee_type": (
                str(work_info.employee_type_id) if work_info.employee_type_id else None
            ),
            "date_joining": (
                str(work_info.date_joining) if work_info.date_joining else None
            ),
        }

    return json.dumps(result, indent=2)


@mcp.tool()
def search_employees(
    query: str,
    department: str | None = None,
    active_only: bool = True,
    limit: int = 20,
) -> str:
    """
    Search employees by name, email, phone, or badge ID.
    Optionally filter by department name. Returns up to `limit` results.
    """
    from employee.models import Employee

    qs = Employee.objects.all()

    if active_only:
        qs = qs.filter(is_active=True)

    if query:
        qs = qs.filter(
            Q(employee_first_name__icontains=query)
            | Q(employee_last_name__icontains=query)
            | Q(email__icontains=query)
            | Q(phone__icontains=query)
            | Q(badge_id__icontains=query)
        )

    if department:
        qs = qs.filter(
            employee_work_info__department_id__department__icontains=department
        )

    qs = qs.select_related("employee_work_info")[:limit]

    results = []
    for emp in qs:
        work_info = getattr(emp, "employee_work_info", None)
        results.append(
            {
                "id": emp.pk,
                "badge_id": emp.badge_id,
                "name": f"{emp.employee_first_name} {emp.employee_last_name}",
                "email": emp.email,
                "department": (
                    str(work_info.department_id)
                    if work_info and work_info.department_id
                    else None
                ),
                "position": (
                    str(work_info.job_position_id)
                    if work_info and work_info.job_position_id
                    else None
                ),
                "is_active": emp.is_active,
            }
        )

    return json.dumps(
        {"count": len(results), "employees": results},
        indent=2,
    )
