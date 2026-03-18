"""MCP tools for recruitment pipeline queries."""

import json

from horilla_mcp.server import mcp


@mcp.tool()
def get_recruitment_pipeline(status: str | None = None) -> str:
    """
    Get all active recruitment pipelines with candidate counts per stage.
    Status filter: None (all open), or 'closed'.
    """
    from recruitment.models import Recruitment

    qs = Recruitment.objects.filter(is_active=True)
    if status == "closed":
        qs = qs.filter(closed=True)
    else:
        qs = qs.filter(closed=False)

    results = []
    for rec in qs.prefetch_related("stage_set"):
        stages = []
        for stage in rec.stage_set.filter(is_active=True).order_by("sequence"):
            count = stage.candidate_set.filter(is_active=True, canceled=False).count()
            stages.append(
                {
                    "stage": stage.stage,
                    "type": stage.stage_type,
                    "candidate_count": count,
                }
            )

        results.append(
            {
                "id": rec.pk,
                "title": rec.title,
                "job_position": (
                    str(rec.job_position_id) if rec.job_position_id else None
                ),
                "vacancy": rec.vacancy,
                "total_hires": rec.total_hires(),
                "is_published": rec.is_published,
                "stages": stages,
            }
        )

    return json.dumps(
        {
            "count": len(results),
            "recruitments": results,
        },
        indent=2,
    )


@mcp.tool()
def get_candidates(
    recruitment_id: int | None = None,
    stage: str | None = None,
    status: str | None = None,
    limit: int = 30,
) -> str:
    """
    List candidates, optionally filtered by recruitment, stage name, or status.
    Status options: hired, canceled, converted.
    """
    from recruitment.models import Candidate

    qs = (
        Candidate.objects.filter(is_active=True)
        .select_related("recruitment_id", "stage_id", "job_position_id")
        .order_by("-created_at")
    )

    if recruitment_id:
        qs = qs.filter(recruitment_id=recruitment_id)
    if stage:
        qs = qs.filter(stage_id__stage__icontains=stage)
    if status == "hired":
        qs = qs.filter(hired=True)
    elif status == "canceled":
        qs = qs.filter(canceled=True)
    elif status == "converted":
        qs = qs.filter(converted=True)

    qs = qs[:limit]

    results = []
    for c in qs:
        results.append(
            {
                "id": c.pk,
                "name": c.name,
                "email": c.email,
                "recruitment": str(c.recruitment_id) if c.recruitment_id else None,
                "stage": str(c.stage_id) if c.stage_id else None,
                "job_position": str(c.job_position_id) if c.job_position_id else None,
                "hired": c.hired,
                "canceled": c.canceled,
                "converted": c.converted,
                "offer_status": c.offer_letter_status,
                "rating": c.get_avg_rating() if hasattr(c, "get_avg_rating") else None,
            }
        )

    return json.dumps(
        {
            "count": len(results),
            "candidates": results,
        },
        indent=2,
    )


@mcp.tool()
def get_interview_schedule(
    date_from: str | None = None,
    date_to: str | None = None,
    interviewer_id: int | None = None,
    limit: int = 20,
) -> str:
    """
    List upcoming or recent interviews. Filter by date range or interviewer.
    Date format: YYYY-MM-DD.
    """
    from datetime import date

    from recruitment.models import InterviewSchedule

    qs = (
        InterviewSchedule.objects.filter(
            is_active=True,
        )
        .select_related("candidate_id")
        .order_by("interview_date", "interview_time")
    )

    if date_from:
        qs = qs.filter(interview_date__gte=date_from)
    else:
        qs = qs.filter(interview_date__gte=date.today())

    if date_to:
        qs = qs.filter(interview_date__lte=date_to)

    if interviewer_id:
        qs = qs.filter(employee_id=interviewer_id)

    qs = qs[:limit]

    results = []
    for interview in qs:
        interviewers = [
            f"{e.employee_first_name} {e.employee_last_name}"
            for e in interview.employee_id.all()
        ]
        results.append(
            {
                "id": interview.pk,
                "candidate": (
                    interview.candidate_id.name if interview.candidate_id else None
                ),
                "date": str(interview.interview_date),
                "time": (
                    str(interview.interview_time) if interview.interview_time else None
                ),
                "interviewers": interviewers,
                "completed": interview.completed,
            }
        )

    return json.dumps(
        {
            "count": len(results),
            "interviews": results,
        },
        indent=2,
    )


@mcp.tool()
def get_recruitment_analytics() -> str:
    """
    Get recruitment analytics: open positions, total candidates,
    hired count, conversion rates, average time-to-hire.
    """
    from django.db.models import Avg, Count, F

    from recruitment.models import Candidate, Recruitment

    open_recs = Recruitment.objects.filter(closed=False, is_active=True)
    total_open = open_recs.count()
    total_vacancy = sum(r.vacancy or 0 for r in open_recs)
    total_hired = sum(r.total_hires() for r in open_recs)

    total_candidates = Candidate.objects.filter(is_active=True).count()
    hired_candidates = Candidate.objects.filter(hired=True, is_active=True).count()
    converted = Candidate.objects.filter(converted=True, is_active=True).count()

    conversion_rate = (
        round(hired_candidates / total_candidates * 100, 1) if total_candidates else 0
    )

    return json.dumps(
        {
            "open_recruitments": total_open,
            "total_vacancies": total_vacancy,
            "total_hires": total_hired,
            "total_candidates": total_candidates,
            "hired_candidates": hired_candidates,
            "converted_to_employee": converted,
            "conversion_rate_percent": conversion_rate,
        },
        indent=2,
    )
