"""MCP tools for actions that modify data (approve, reject).
All actions use a 2-step confirmation pattern for safety."""

import json
import logging

from horilla_mcp.tools import logged_tool

logger = logging.getLogger(__name__)


@logged_tool()
def approve_leave_request(
    leave_request_id: int,
    confirm: bool = False,
) -> str:
    """
    Approve a pending leave request.
    Call first WITHOUT confirm=True to see a preview.
    Call again WITH confirm=True to execute the approval.
    """
    from leave.models import AvailableLeave, LeaveRequest

    lr = (
        LeaveRequest.objects.filter(pk=leave_request_id)
        .select_related("employee_id", "leave_type_id")
        .first()
    )

    if not lr:
        return json.dumps({"error": f"Leave request {leave_request_id} not found"})

    if lr.status != "requested":
        return json.dumps(
            {"error": f"Cannot approve — current status is '{lr.status}'"}
        )

    emp = lr.employee_id
    emp_name = f"{emp.employee_first_name} {emp.employee_last_name}"

    # Preview mode
    if not confirm:
        return json.dumps(
            {
                "action": "approve_leave_request",
                "preview": True,
                "message": (
                    f"About to APPROVE leave request #{lr.pk} for {emp_name}: "
                    f"{lr.leave_type_id} from {lr.start_date} to {lr.end_date} "
                    f"({lr.requested_days} days). "
                    f"Call again with confirm=True to execute."
                ),
                "details": {
                    "id": lr.pk,
                    "employee": emp_name,
                    "leave_type": str(lr.leave_type_id),
                    "start_date": str(lr.start_date),
                    "end_date": str(lr.end_date),
                    "requested_days": (
                        float(lr.requested_days) if lr.requested_days else None
                    ),
                },
            },
            indent=2,
        )

    # Execute approval — deduct from leave balance
    try:
        available = AvailableLeave.objects.filter(
            employee_id=emp,
            leave_type_id=lr.leave_type_id,
        ).first()

        if not available:
            return json.dumps(
                {"error": "No leave allocation found for this employee/type"}
            )

        requested = float(lr.requested_days or 0)
        carryforward = float(available.carryforward_days)

        if requested > carryforward:
            leave_from_available = requested - carryforward
            lr.approved_carryforward_days = carryforward
            lr.approved_available_days = leave_from_available
            available.carryforward_days = 0
            available.available_days = (
                float(available.available_days) - leave_from_available
            )
        else:
            lr.approved_carryforward_days = requested
            lr.approved_available_days = 0
            available.carryforward_days = carryforward - requested

        available.save()

        lr.status = "approved"
        lr.save()

        logger.info(f"Leave request #{lr.pk} approved for {emp_name}")

        return json.dumps(
            {
                "action": "approve_leave_request",
                "success": True,
                "message": f"Leave request #{lr.pk} for {emp_name} has been approved.",
                "new_balance": {
                    "available_days": float(available.available_days),
                    "carryforward_days": float(available.carryforward_days),
                    "total": float(available.total_leave_days),
                },
            },
            indent=2,
        )

    except Exception as e:
        logger.exception(f"Failed to approve leave request #{leave_request_id}")
        return json.dumps({"error": f"Approval failed: {str(e)}"})


@logged_tool()
def reject_leave_request(
    leave_request_id: int,
    reason: str = "",
    confirm: bool = False,
) -> str:
    """
    Reject a pending leave request with an optional reason.
    Call first WITHOUT confirm=True to see a preview.
    Call again WITH confirm=True to execute.
    """
    from leave.models import LeaveRequest

    lr = (
        LeaveRequest.objects.filter(pk=leave_request_id)
        .select_related("employee_id", "leave_type_id")
        .first()
    )

    if not lr:
        return json.dumps({"error": f"Leave request {leave_request_id} not found"})

    if lr.status != "requested":
        return json.dumps({"error": f"Cannot reject — current status is '{lr.status}'"})

    emp = lr.employee_id
    emp_name = f"{emp.employee_first_name} {emp.employee_last_name}"

    if not confirm:
        return json.dumps(
            {
                "action": "reject_leave_request",
                "preview": True,
                "message": (
                    f"About to REJECT leave request #{lr.pk} for {emp_name}: "
                    f"{lr.leave_type_id} from {lr.start_date} to {lr.end_date}. "
                    f"Reason: {reason or '(none provided)'}. "
                    f"Call again with confirm=True to execute."
                ),
            },
            indent=2,
        )

    lr.status = "rejected"
    lr.reject_reason = reason
    lr.save()

    logger.info(f"Leave request #{lr.pk} rejected for {emp_name}: {reason}")

    return json.dumps(
        {
            "action": "reject_leave_request",
            "success": True,
            "message": f"Leave request #{lr.pk} for {emp_name} has been rejected.",
            "reason": reason,
        },
        indent=2,
    )


@logged_tool()
def approve_overtime(
    attendance_id: int,
    confirm: bool = False,
) -> str:
    """
    Approve overtime for an attendance record.
    Call first WITHOUT confirm=True to see a preview.
    Call again WITH confirm=True to execute.
    """
    from attendance.models import Attendance

    att = (
        Attendance.objects.filter(pk=attendance_id)
        .select_related("employee_id")
        .first()
    )

    if not att:
        return json.dumps({"error": f"Attendance {attendance_id} not found"})

    if att.attendance_overtime_approve:
        return json.dumps({"error": "Overtime already approved"})

    emp = att.employee_id
    emp_name = f"{emp.employee_first_name} {emp.employee_last_name}"

    if not confirm:
        return json.dumps(
            {
                "action": "approve_overtime",
                "preview": True,
                "message": (
                    f"About to APPROVE overtime for {emp_name} on {att.attendance_date}: "
                    f"Overtime: {att.attendance_overtime}, "
                    f"Worked: {att.attendance_worked_hour}. "
                    f"Call again with confirm=True to execute."
                ),
            },
            indent=2,
        )

    att.attendance_overtime_approve = True
    att.save()

    logger.info(f"Overtime approved for {emp_name} on {att.attendance_date}")

    return json.dumps(
        {
            "action": "approve_overtime",
            "success": True,
            "message": f"Overtime approved for {emp_name} on {att.attendance_date}.",
            "overtime": att.attendance_overtime,
        },
        indent=2,
    )
