"""
Monthly HR report generation.
Assembles data from all modules into a structured report dict.
"""

import logging
from datetime import date

from django.db.models import Avg, Count, Sum

logger = logging.getLogger(__name__)


class MonthlyReportService:
    """Generates comprehensive monthly HR report."""

    def generate(self, company_id=None, month=None, year=None):
        """
        Assemble a monthly HR report from all available modules.

        Returns:
            dict with sections: workforce, attendance, leave, payroll, recruitment
        """
        today = date.today()
        m = month or today.month
        y = year or today.year

        report = {
            "period": f"{y}-{m:02d}",
            "generated_at": str(today),
            "workforce": self._workforce_section(company_id, m, y),
            "attendance": self._attendance_section(company_id, m, y),
            "leave": self._leave_section(company_id, m, y),
            "payroll": self._payroll_section(company_id, m, y),
            "recruitment": self._recruitment_section(company_id),
        }

        return report

    def _workforce_section(self, company_id, month, year):
        """Headcount and workforce composition."""
        try:
            from base.models import Department
            from employee.models import Employee

            qs = Employee.objects.filter(is_active=True)
            if company_id:
                qs = qs.filter(employee_work_info__company_id=company_id)

            total = qs.count()

            # New joiners this month
            new_joiners = qs.filter(
                employee_work_info__date_joining__month=month,
                employee_work_info__date_joining__year=year,
            ).count()

            # By department
            dept_breakdown = (
                qs.values("employee_work_info__department_id__department")
                .annotate(count=Count("id"))
                .order_by("-count")
            )

            return {
                "total_headcount": total,
                "new_joiners": new_joiners,
                "by_department": [
                    {
                        "department": d["employee_work_info__department_id__department"]
                        or "Unassigned",
                        "count": d["count"],
                    }
                    for d in dept_breakdown[:10]
                ],
            }
        except Exception:
            logger.exception("Workforce section failed")
            return {"error": "Could not generate workforce data"}

    def _attendance_section(self, company_id, month, year):
        """Attendance statistics for the month."""
        try:
            from attendance.models import Attendance, AttendanceLateComeEarlyOut

            qs = Attendance.objects.filter(
                attendance_date__month=month,
                attendance_date__year=year,
            )
            if company_id:
                qs = qs.filter(employee_id__employee_work_info__company_id=company_id)

            total_records = qs.count()
            validated = qs.filter(attendance_validated=True).count()

            late_count = AttendanceLateComeEarlyOut.objects.filter(
                attendance_id__attendance_date__month=month,
                attendance_id__attendance_date__year=year,
                type="late_come",
            ).count()

            return {
                "total_attendance_records": total_records,
                "validated": validated,
                "late_arrivals": late_count,
                "validation_rate": (
                    round(validated / total_records * 100, 1) if total_records else 0
                ),
            }
        except ImportError:
            return {"note": "Attendance module not installed"}
        except Exception:
            logger.exception("Attendance section failed")
            return {"error": "Could not generate attendance data"}

    def _leave_section(self, company_id, month, year):
        """Leave utilization for the month."""
        try:
            from leave.models import LeaveRequest

            qs = LeaveRequest.objects.filter(
                start_date__month=month,
                start_date__year=year,
            )
            if company_id:
                qs = qs.filter(employee_id__employee_work_info__company_id=company_id)

            total = qs.count()
            approved = qs.filter(status="approved").count()
            rejected = qs.filter(status="rejected").count()
            pending = qs.filter(status="requested").count()

            total_days = (
                qs.filter(status="approved").aggregate(days=Sum("requested_days"))[
                    "days"
                ]
                or 0
            )

            # By leave type
            by_type = (
                qs.filter(status="approved")
                .values("leave_type_id__name")
                .annotate(count=Count("id"), days=Sum("requested_days"))
                .order_by("-days")
            )

            return {
                "total_requests": total,
                "approved": approved,
                "rejected": rejected,
                "pending": pending,
                "total_leave_days": float(total_days),
                "by_type": [
                    {
                        "type": t["leave_type_id__name"],
                        "requests": t["count"],
                        "days": float(t["days"] or 0),
                    }
                    for t in by_type[:10]
                ],
            }
        except ImportError:
            return {"note": "Leave module not installed"}
        except Exception:
            logger.exception("Leave section failed")
            return {"error": "Could not generate leave data"}

    def _payroll_section(self, company_id, month, year):
        """Payroll summary for the month."""
        try:
            from payroll.models.models import Payslip

            qs = Payslip.objects.filter(
                start_date__month=month,
                start_date__year=year,
                status__in=["confirmed", "paid"],
            )
            if company_id:
                qs = qs.filter(employee_id__employee_work_info__company_id=company_id)

            agg = qs.aggregate(
                total_gross=Sum("gross_pay"),
                total_net=Sum("net_pay"),
                total_deductions=Sum("deduction"),
                avg_net=Avg("net_pay"),
                count=Count("id"),
            )

            return {
                "payslips_processed": agg["count"] or 0,
                "total_gross": float(agg["total_gross"] or 0),
                "total_net": float(agg["total_net"] or 0),
                "total_deductions": float(agg["total_deductions"] or 0),
                "average_net_pay": round(float(agg["avg_net"] or 0), 2),
            }
        except ImportError:
            return {"note": "Payroll module not installed"}
        except Exception:
            logger.exception("Payroll section failed")
            return {"error": "Could not generate payroll data"}

    def _recruitment_section(self, company_id):
        """Current recruitment pipeline status."""
        try:
            from recruitment.models import Candidate, Recruitment

            open_recs = Recruitment.objects.filter(closed=False, is_active=True)
            if company_id:
                open_recs = open_recs.filter(company_id=company_id)

            total_open = open_recs.count()
            total_candidates = Candidate.objects.filter(
                is_active=True,
                canceled=False,
            ).count()
            hired = Candidate.objects.filter(hired=True, is_active=True).count()

            return {
                "open_recruitments": total_open,
                "active_candidates": total_candidates,
                "hired_this_period": hired,
            }
        except ImportError:
            return {"note": "Recruitment module not installed"}
        except Exception:
            logger.exception("Recruitment section failed")
            return {"error": "Could not generate recruitment data"}
