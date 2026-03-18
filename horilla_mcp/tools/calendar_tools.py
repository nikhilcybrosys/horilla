"""MCP tools for holiday and calendar queries."""

import json
from datetime import date

from horilla_mcp.server import mcp


@mcp.tool()
def get_holidays(year: int | None = None) -> str:
    """
    List company holidays. Defaults to current year.
    Returns holiday name, dates, and whether it recurs annually.
    """
    from base.models import Holidays

    if year is None:
        year = date.today().year

    holidays = Holidays.objects.filter(
        start_date__year=year,
        is_active=True,
    ).order_by("start_date")

    # Also include recurring holidays
    recurring = Holidays.objects.filter(recurring=True, is_active=True)

    seen_ids = set()
    results = []

    for h in list(holidays) + list(recurring):
        if h.pk in seen_ids:
            continue
        seen_ids.add(h.pk)
        results.append(
            {
                "name": h.name,
                "start_date": str(h.start_date),
                "end_date": str(h.end_date) if h.end_date else str(h.start_date),
                "recurring": h.recurring,
                "company": str(h.company_id) if h.company_id else "All",
            }
        )

    return json.dumps(
        {"year": year, "count": len(results), "holidays": results},
        indent=2,
    )


@mcp.tool()
def get_company_leaves() -> str:
    """
    List recurring company leave days (e.g., every Saturday, every 2nd Saturday).
    These are non-working days defined by the company.
    """
    from base.models import CompanyLeaves

    leaves = CompanyLeaves.objects.filter(is_active=True)

    week_names = {
        "0": "Every week",
        "1": "First week",
        "2": "Second week",
        "3": "Third week",
        "4": "Fourth week",
        "5": "Fifth week",
        None: "Every week",
    }
    day_names = {
        "0": "Monday",
        "1": "Tuesday",
        "2": "Wednesday",
        "3": "Thursday",
        "4": "Friday",
        "5": "Saturday",
        "6": "Sunday",
    }

    results = []
    for cl in leaves:
        week = week_names.get(cl.based_on_week, cl.based_on_week or "Every week")
        day = day_names.get(cl.based_on_week_day, cl.based_on_week_day)
        results.append(
            {
                "week": week,
                "day": day,
                "description": f"{week} {day}",
                "company": str(cl.company_id) if cl.company_id else "All",
            }
        )

    return json.dumps(
        {"count": len(results), "company_leaves": results},
        indent=2,
    )
