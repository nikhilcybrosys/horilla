"""MCP tools for payroll data queries."""

import json

from horilla_mcp.server import mcp


@mcp.tool()
def get_employee_payslip(
    employee_id: int,
    month: int | None = None,
    year: int | None = None,
) -> str:
    """
    Get payslip details for an employee. Defaults to most recent payslip.
    Returns: basic pay, gross pay, allowances, deductions, net pay.
    Sensitive data — only the employee themselves or their manager should access this.
    """
    from datetime import date

    from payroll.models.models import Payslip

    qs = Payslip.objects.filter(
        employee_id=employee_id,
    ).order_by("-end_date")

    if month and year:
        qs = qs.filter(start_date__month=month, start_date__year=year)

    payslip = qs.first()

    if not payslip:
        return json.dumps({"error": f"No payslip found for employee {employee_id}"})

    # Extract pay components from pay_head_data JSON
    pay_data = payslip.pay_head_data or {}
    allowances = pay_data.get("allowances", [])
    pretax = pay_data.get("pretax_deductions", [])
    posttax = pay_data.get("post_tax_deductions", [])

    result = {
        "employee_id": employee_id,
        "period": f"{payslip.start_date} to {payslip.end_date}",
        "status": payslip.status,
        "contract_wage": float(payslip.contract_wage),
        "basic_pay": float(payslip.basic_pay),
        "gross_pay": float(payslip.gross_pay),
        "total_deductions": float(payslip.deduction),
        "net_pay": float(payslip.net_pay),
        "allowances": [
            {"title": a.get("title", ""), "amount": float(a.get("amount", 0))}
            for a in allowances
        ],
        "deductions": [
            {"title": d.get("title", ""), "amount": float(d.get("amount", 0))}
            for d in pretax + posttax
        ],
        "loss_of_pay": float(pay_data.get("loss_of_pay", 0)),
        "paid_days": pay_data.get("paid_days"),
        "unpaid_days": pay_data.get("unpaid_days"),
    }

    if payslip.group_name:
        result["group"] = payslip.group_name

    return json.dumps(result, indent=2)


@mcp.tool()
def get_employee_contract(employee_id: int) -> str:
    """
    Get the active contract for an employee.
    Returns: wage type, salary, pay frequency, filing status, notice period.
    """
    from payroll.models.models import Contract

    contract = Contract.objects.filter(
        employee_id=employee_id,
        contract_status="active",
    ).first()

    if not contract:
        return json.dumps({"error": f"No active contract for employee {employee_id}"})

    result = {
        "employee_id": employee_id,
        "contract_name": contract.contract_name,
        "status": contract.contract_status,
        "wage_type": contract.wage_type,
        "wage": float(contract.wage),
        "pay_frequency": contract.pay_frequency,
        "start_date": str(contract.contract_start_date),
        "end_date": (
            str(contract.contract_end_date) if contract.contract_end_date else None
        ),
        "notice_period_days": contract.notice_period_in_days,
        "deduct_leave_from_basic_pay": contract.deduct_leave_from_basic_pay,
        "filing_status": (
            str(contract.filing_status) if contract.filing_status else None
        ),
    }

    if contract.department:
        result["department"] = str(contract.department)
    if contract.job_position:
        result["job_position"] = str(contract.job_position)

    return json.dumps(result, indent=2)


@mcp.tool()
def get_payroll_summary(month: int | None = None, year: int | None = None) -> str:
    """
    Get aggregated payroll summary for a period.
    Returns: total gross, total net, total deductions, employee count.
    Defaults to most recent payroll period. Requires HR permission.
    """
    from datetime import date

    from django.db.models import Avg, Count, Sum

    from payroll.models.models import Payslip

    today = date.today()
    m = month or today.month
    y = year or today.year

    payslips = Payslip.objects.filter(
        start_date__month=m,
        start_date__year=y,
        status__in=["confirmed", "paid"],
    )

    if not payslips.exists():
        # Try finding the most recent period
        latest = (
            Payslip.objects.filter(status__in=["confirmed", "paid"])
            .order_by("-end_date")
            .first()
        )
        if latest:
            m = latest.start_date.month
            y = latest.start_date.year
            payslips = Payslip.objects.filter(
                start_date__month=m,
                start_date__year=y,
                status__in=["confirmed", "paid"],
            )

    agg = payslips.aggregate(
        total_gross=Sum("gross_pay"),
        total_net=Sum("net_pay"),
        total_deductions=Sum("deduction"),
        avg_net=Avg("net_pay"),
        count=Count("id"),
    )

    return json.dumps(
        {
            "period": f"{y}-{m:02d}",
            "employee_count": agg["count"] or 0,
            "total_gross_pay": float(agg["total_gross"] or 0),
            "total_net_pay": float(agg["total_net"] or 0),
            "total_deductions": float(agg["total_deductions"] or 0),
            "average_net_pay": round(float(agg["avg_net"] or 0), 2),
        },
        indent=2,
    )
