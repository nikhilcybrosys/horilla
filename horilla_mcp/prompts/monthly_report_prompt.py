"""MCP prompt: /monthly-report — generate comprehensive monthly HR report."""

from horilla_mcp.server import mcp


@mcp.prompt()
def monthly_hr_report(
    month: str,
    department: str | None = None,
) -> str:
    """Generate a comprehensive monthly HR report with all key metrics."""
    dept_filter = f" for {department} department" if department else ""
    return f"""Generate a comprehensive Monthly HR Report for {month}{dept_filter}.

Gather data using these tools and compile a structured report:

**1. Headcount & Workforce**
- Use `get_department_summary` for current headcount per department
- Use `search_employees` to identify any new joiners this month

**2. Attendance Overview**
- Use `get_attendance_today` to get a snapshot
- Note: For full month data, check attendance patterns

**3. Leave Utilization**
- Use `get_leave_requests` with date filters for {month}
- Summarize: total leave days taken, most common leave types, pending requests

**4. Payroll Summary**
- Use `get_payroll_summary` for the month
- Report: total gross, total net, average salary, employee count processed

**5. Recruitment Pipeline**
- Use `get_recruitment_pipeline` for open positions
- Use `get_recruitment_analytics` for conversion rates
- Use `get_interview_schedule` for upcoming interviews

**6. Holidays & Calendar**
- Use `get_holidays` for the month
- Use `get_company_leaves` for recurring off-days

**Format the report as:**
```
# Monthly HR Report — {month}

## Executive Summary
(2-3 bullet points highlighting key metrics)

## Workforce
(headcount, new hires, exits)

## Attendance
(attendance rate, patterns)

## Leave
(utilization, popular types)

## Payroll
(totals, averages)

## Recruitment
(pipeline status, hiring velocity)

## Key Actions Required
(items needing attention)
```"""
