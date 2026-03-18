"""
Model-to-text serializers for RAG embedding.

These are NOT DRF serializers. They convert Django model instances
into natural language text suitable for vector embedding.
"""


def serialize_employee(employee):
    """Serialize an Employee instance to embeddable text."""
    parts = [
        f"Employee: {employee.employee_first_name} {employee.employee_last_name}",
        f"Badge ID: {employee.badge_id or 'N/A'}",
        f"Email: {employee.email}",
    ]

    if employee.phone:
        parts.append(f"Phone: {employee.phone}")
    if employee.gender:
        parts.append(f"Gender: {employee.get_gender_display()}")
    if employee.qualification:
        parts.append(f"Qualification: {employee.qualification}")

    parts.append(f"Status: {'Active' if employee.is_active else 'Inactive'}")

    work_info = getattr(employee, "employee_work_info", None)
    if work_info:
        if work_info.department_id:
            parts.append(f"Department: {work_info.department_id}")
        if work_info.job_position_id:
            parts.append(f"Position: {work_info.job_position_id}")
        if work_info.job_role_id:
            parts.append(f"Role: {work_info.job_role_id}")
        if work_info.reporting_manager_id:
            mgr = work_info.reporting_manager_id
            parts.append(
                f"Reports to: {mgr.employee_first_name} {mgr.employee_last_name}"
            )
        if work_info.company_id:
            parts.append(f"Company: {work_info.company_id}")
        if work_info.shift_id:
            parts.append(f"Shift: {work_info.shift_id}")
        if work_info.work_type_id:
            parts.append(f"Work type: {work_info.work_type_id}")
        if work_info.employee_type_id:
            parts.append(f"Employee type: {work_info.employee_type_id}")
        if work_info.date_joining:
            parts.append(f"Date of joining: {work_info.date_joining}")

    return ". ".join(parts) + "."


def serialize_policy(policy):
    """Serialize a Policy instance to embeddable text."""
    parts = [f"Company Policy: {policy.title}"]

    if policy.body:
        # Strip HTML tags for clean text
        import re

        clean_body = re.sub(r"<[^>]+>", "", policy.body)
        clean_body = re.sub(r"\s+", " ", clean_body).strip()
        parts.append(f"Content: {clean_body}")

    visibility = "all employees" if policy.is_visible_to_all else "specific employees"
    parts.append(f"Visible to: {visibility}")

    companies = policy.company_id.all()
    if companies.exists():
        company_names = ", ".join(str(c) for c in companies)
        parts.append(f"Company: {company_names}")

    return ". ".join(parts) + "."


def serialize_leave_type(leave_type):
    """Serialize a LeaveType instance to embeddable text."""
    parts = [
        f"Leave Type: {leave_type.name}",
        f"Payment: {leave_type.payment}",
        f"Total days allowed: {leave_type.total_days}",
    ]

    if leave_type.reset:
        parts.append(f"Resets: {leave_type.reset_based}")
    else:
        parts.append("Does not reset")

    if (
        leave_type.carryforward_type
        and leave_type.carryforward_type != "no carryforward"
    ):
        parts.append(f"Carryforward: {leave_type.carryforward_type}")
        if leave_type.carryforward_max:
            parts.append(f"Max carryforward: {leave_type.carryforward_max} days")
    else:
        parts.append("No carryforward allowed")

    if leave_type.require_approval == "yes":
        parts.append("Requires manager approval")
    else:
        parts.append("Auto-approved (no approval needed)")

    if leave_type.require_attachment == "yes":
        parts.append("Attachment required")

    if leave_type.exclude_company_leave == "yes":
        parts.append("Company leaves excluded from count")
    if leave_type.exclude_holiday == "yes":
        parts.append("Holidays excluded from count")

    if leave_type.is_compensatory_leave:
        parts.append("This is a compensatory leave type")

    if leave_type.company_id:
        parts.append(f"Company: {leave_type.company_id}")

    return ". ".join(parts) + "."


def serialize_holiday(holiday):
    """Serialize a Holiday instance to embeddable text."""
    parts = [
        f"Holiday: {holiday.name}",
        f"Date: {holiday.start_date}",
    ]
    if holiday.end_date and holiday.end_date != holiday.start_date:
        parts.append(f"to {holiday.end_date}")
    if holiday.recurring:
        parts.append("Recurring annually")
    if holiday.company_id:
        parts.append(f"Company: {holiday.company_id}")
    return ". ".join(parts) + "."


def serialize_faq(faq):
    """Serialize a helpdesk FAQ to embeddable text."""
    parts = [
        f"FAQ Question: {faq.question}",
        f"Answer: {faq.answer}",
    ]
    if hasattr(faq, "category") and faq.category:
        parts.append(f"Category: {faq.category.title}")
    return ". ".join(parts) + "."


def serialize_available_leave(available_leave):
    """Serialize an AvailableLeave balance to embeddable text."""
    emp = available_leave.employee_id
    leave_type = available_leave.leave_type_id
    return (
        f"Leave balance for {emp.employee_first_name} {emp.employee_last_name}: "
        f"{leave_type.name} - "
        f"Available: {available_leave.available_days} days, "
        f"Carryforward: {available_leave.carryforward_days} days, "
        f"Total: {available_leave.total_leave_days} days."
    )


def serialize_announcement(announcement):
    """Serialize an Announcement to embeddable text."""
    import re

    parts = [f"Announcement: {announcement.title}"]
    if announcement.description:
        clean = re.sub(r"<[^>]+>", "", announcement.description)
        clean = re.sub(r"\s+", " ", clean).strip()
        parts.append(f"Content: {clean}")
    if announcement.expire_date:
        parts.append(f"Expires: {announcement.expire_date}")
    return ". ".join(parts) + "."


def serialize_leave_request(leave_request):
    """Serialize a LeaveRequest to embeddable text."""
    emp = leave_request.employee_id
    leave_type = leave_request.leave_type_id
    parts = [
        f"Leave request by {emp.employee_first_name} {emp.employee_last_name}",
        f"Leave type: {leave_type.name}",
        f"From: {leave_request.start_date} ({leave_request.start_date_breakdown})",
        f"To: {leave_request.end_date} ({leave_request.end_date_breakdown})",
        f"Requested days: {leave_request.requested_days}",
        f"Status: {leave_request.status}",
    ]
    if leave_request.description:
        parts.append(f"Reason: {leave_request.description[:200]}")
    return ". ".join(parts) + "."


def serialize_attendance_summary(employee, month, year, data):
    """Serialize an attendance summary dict to embeddable text."""
    parts = [
        f"Attendance summary for {employee.employee_first_name} {employee.employee_last_name}",
        f"Period: {month} {year}",
        f"Present days: {data.get('present_days', 0)}",
        f"Worked hours: {data.get('worked_hours', '00:00')}",
        f"Pending hours: {data.get('pending_hours', '00:00')}",
        f"Overtime: {data.get('overtime', '00:00')}",
    ]
    late = data.get("late_count", 0)
    early = data.get("early_count", 0)
    if late:
        parts.append(f"Late arrivals: {late}")
    if early:
        parts.append(f"Early departures: {early}")
    return ". ".join(parts) + "."


# Registry mapping model paths to serializer functions
SERIALIZER_REGISTRY = {
    "employee.Employee": serialize_employee,
    "employee.Policy": serialize_policy,
    "leave.LeaveType": serialize_leave_type,
    "leave.AvailableLeave": serialize_available_leave,
    "leave.LeaveRequest": serialize_leave_request,
    "base.Holidays": serialize_holiday,
    "base.Announcement": serialize_announcement,
    "helpdesk.FAQ": serialize_faq,
}

# Document type mapping
MODEL_TO_DOCUMENT_TYPE = {
    "employee.Employee": "employee",
    "employee.Policy": "policy",
    "leave.LeaveType": "leave_type",
    "leave.AvailableLeave": "leave_balance",
    "leave.LeaveRequest": "leave_request",
    "base.Holidays": "holiday",
    "base.Announcement": "announcement",
    "helpdesk.FAQ": "faq",
}
