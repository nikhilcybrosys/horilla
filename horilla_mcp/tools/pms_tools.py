"""MCP tools for Performance Management System (OKR, feedback)."""

import json

from horilla_mcp.server import mcp


@mcp.tool()
def get_employee_objectives(employee_id: int) -> str:
    """
    Get OKR objectives and key results for an employee.
    Shows progress percentage, status, and key result details.
    """
    from pms.models import EmployeeObjective

    objectives = (
        EmployeeObjective.objects.filter(
            employee_id=employee_id,
            archive=False,
        )
        .select_related("objective_id")
        .prefetch_related("employee_key_result")
    )

    results = []
    for obj in objectives:
        krs = []
        for kr in obj.employee_key_result.all():
            krs.append(
                {
                    "title": kr.key_result or str(kr.key_result_id),
                    "progress": kr.progress_percentage,
                    "current_value": kr.current_value,
                    "target_value": kr.target_value,
                    "status": kr.status,
                }
            )

        results.append(
            {
                "id": obj.pk,
                "objective": (
                    str(obj.objective_id) if obj.objective_id else obj.objective
                ),
                "progress": obj.progress_percentage,
                "status": obj.status,
                "start_date": str(obj.start_date) if obj.start_date else None,
                "end_date": str(obj.end_date) if obj.end_date else None,
                "key_results": krs,
            }
        )

    return json.dumps(
        {
            "employee_id": employee_id,
            "count": len(results),
            "objectives": results,
        },
        indent=2,
    )


@mcp.tool()
def get_employee_feedback(employee_id: int, status: str | None = None) -> str:
    """
    Get 360-degree feedback entries for an employee (as subject).
    Status filter: Not Started, On Track, Behind, At Risk, Closed.
    """
    from pms.models import Feedback

    qs = Feedback.objects.filter(
        employee_id=employee_id,
        archive=False,
    ).select_related("question_template_id")

    if status:
        qs = qs.filter(status=status)

    results = []
    for fb in qs:
        answered = fb.feedback_answer.count() if hasattr(fb, "feedback_answer") else 0
        requested = (
            len(fb.requested_employees()) if hasattr(fb, "requested_employees") else 0
        )

        results.append(
            {
                "id": fb.pk,
                "review_cycle": fb.review_cycle,
                "status": fb.status,
                "start_date": str(fb.start_date),
                "end_date": str(fb.end_date),
                "template": (
                    str(fb.question_template_id) if fb.question_template_id else None
                ),
                "responses_received": answered,
                "responses_expected": requested,
                "is_cyclic": fb.cyclic_feedback,
            }
        )

    return json.dumps(
        {
            "employee_id": employee_id,
            "count": len(results),
            "feedback": results,
        },
        indent=2,
    )


@mcp.tool()
def get_performance_summary(employee_id: int) -> str:
    """
    Aggregated performance summary: OKR progress, feedback status,
    bonus points, and attendance rate. Useful for performance reviews.
    """
    from datetime import date

    summary = {"employee_id": employee_id}

    # OKR progress
    try:
        from pms.models import EmployeeObjective

        objectives = EmployeeObjective.objects.filter(
            employee_id=employee_id, archive=False
        )
        if objectives.exists():
            avg_progress = (
                sum(o.progress_percentage for o in objectives) / objectives.count()
            )
            summary["okr"] = {
                "total_objectives": objectives.count(),
                "average_progress": round(avg_progress, 1),
                "completed": objectives.filter(status="Closed").count(),
                "at_risk": objectives.filter(status="At Risk").count(),
            }
    except ImportError:
        pass

    # Feedback
    try:
        from pms.models import Feedback

        feedbacks = Feedback.objects.filter(employee_id=employee_id, archive=False)
        summary["feedback"] = {
            "total_cycles": feedbacks.count(),
            "open": feedbacks.exclude(status="Closed").count(),
            "closed": feedbacks.filter(status="Closed").count(),
        }
    except ImportError:
        pass

    # Bonus points
    try:
        from employee.models import BonusPoint

        bp = BonusPoint.objects.filter(employee_id=employee_id).first()
        if bp:
            summary["bonus_points"] = bp.points
    except Exception:
        pass

    # Attendance rate (current month)
    try:
        from datetime import timedelta

        from attendance.models import Attendance

        today = date.today()
        month_start = today.replace(day=1)
        working_days = sum(
            1
            for d in range((today - month_start).days + 1)
            if (month_start + timedelta(days=d)).weekday() < 5
        )
        present = Attendance.objects.filter(
            employee_id=employee_id,
            attendance_date__gte=month_start,
            attendance_date__lte=today,
        ).count()
        summary["attendance"] = {
            "present_this_month": present,
            "working_days": working_days,
            "rate_pct": round(present / working_days * 100, 1) if working_days else 0,
        }
    except ImportError:
        pass

    return json.dumps(summary, indent=2)
