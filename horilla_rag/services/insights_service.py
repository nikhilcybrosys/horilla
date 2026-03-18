"""
Proactive HR insight generation.
Runs daily at 6 AM to surface attendance issues, expiring contracts,
leave balance warnings, and upcoming birthdays.
"""

import logging
from datetime import date, timedelta

from django.utils import timezone

logger = logging.getLogger(__name__)


class InsightsService:
    """Generates InsightAlert records for actionable HR insights."""

    def generate_all(self, company=None):
        """Run all insight generators. Returns total alerts created."""
        total = 0
        total += self.attendance_alerts(company)
        total += self.leave_balance_alerts(company)
        total += self.contract_expiry_alerts(company)
        total += self.birthday_alerts(company)
        total += self.probation_alerts(company)
        logger.info(f"Generated {total} insight alerts")
        return total

    def attendance_alerts(self, company=None):
        """Flag employees with attendance below 80% in the current month."""
        count = 0
        try:
            from attendance.models import Attendance
            from employee.models import Employee
            from horilla_rag.models import InsightAlert

            today = date.today()
            month_start = today.replace(day=1)
            working_days = sum(
                1
                for d in range((today - month_start).days + 1)
                if (month_start + timedelta(days=d)).weekday() < 5
            )

            if working_days < 5:
                return 0  # Not enough data yet

            threshold = 0.8
            employees = Employee.objects.filter(is_active=True)
            if company:
                employees = employees.filter(employee_work_info__company_id=company)

            low_attendance = []
            for emp in employees.iterator():
                present = Attendance.objects.filter(
                    employee_id=emp,
                    attendance_date__gte=month_start,
                    attendance_date__lte=today,
                ).count()

                rate = present / working_days if working_days else 0
                if rate < threshold:
                    low_attendance.append((emp, present, round(rate * 100, 1)))

            if low_attendance:
                alert = InsightAlert.objects.create(
                    company_id=company,
                    alert_type="attendance",
                    title=f"{len(low_attendance)} employees below 80% attendance this month",
                    description="\n".join(
                        f"- {emp.employee_first_name} {emp.employee_last_name}: "
                        f"{present}/{working_days} days ({rate}%)"
                        for emp, present, rate in low_attendance[:20]
                    ),
                    severity="warning" if len(low_attendance) > 5 else "info",
                    expires_at=timezone.now() + timedelta(days=1),
                )
                alert.related_employees.set([e for e, _, _ in low_attendance])
                count = 1

        except ImportError:
            pass
        except Exception:
            logger.exception("Failed to generate attendance alerts")
        return count

    def leave_balance_alerts(self, company=None):
        """Flag employees with high unused leave balance (>80% remaining near reset)."""
        count = 0
        try:
            from horilla_rag.models import InsightAlert
            from leave.models import AvailableLeave

            today = date.today()
            high_balance = []

            qs = AvailableLeave.objects.filter(
                employee_id__is_active=True,
            ).select_related("employee_id", "leave_type_id")

            if company:
                qs = qs.filter(employee_id__employee_work_info__company_id=company)

            for avl in qs.iterator():
                if (
                    not avl.leave_type_id.total_days
                    or avl.leave_type_id.total_days == 0
                ):
                    continue

                usage_rate = 1 - (avl.total_leave_days / avl.leave_type_id.total_days)
                days_left = avl.total_leave_days

                # Alert if >80% balance remaining and reset within 60 days
                if usage_rate < 0.2 and days_left > 5:
                    if avl.reset_date and (avl.reset_date - today).days <= 60:
                        high_balance.append(
                            (
                                avl.employee_id,
                                avl.leave_type_id.name,
                                float(days_left),
                                str(avl.reset_date),
                            )
                        )

            if high_balance:
                alert = InsightAlert.objects.create(
                    company_id=company,
                    alert_type="leave_balance",
                    title=f"{len(high_balance)} employees have high unused leave (reset approaching)",
                    description="\n".join(
                        f"- {emp.employee_first_name} {emp.employee_last_name}: "
                        f"{days} days of {lt} (resets {reset})"
                        for emp, lt, days, reset in high_balance[:20]
                    ),
                    severity="info",
                    expires_at=timezone.now() + timedelta(days=1),
                )
                alert.related_employees.set([e for e, _, _, _ in high_balance])
                count = 1

        except ImportError:
            pass
        except Exception:
            logger.exception("Failed to generate leave balance alerts")
        return count

    def contract_expiry_alerts(self, company=None):
        """Flag contracts expiring within 30 days."""
        count = 0
        try:
            from horilla_rag.models import InsightAlert
            from payroll.models.models import Contract

            today = date.today()
            cutoff = today + timedelta(days=30)

            expiring = Contract.objects.filter(
                contract_status="active",
                contract_end_date__gte=today,
                contract_end_date__lte=cutoff,
            ).select_related("employee_id")

            if company:
                expiring = expiring.filter(
                    employee_id__employee_work_info__company_id=company
                )

            contracts = list(expiring)
            if contracts:
                severity = (
                    "critical"
                    if any((c.contract_end_date - today).days <= 7 for c in contracts)
                    else "warning"
                )

                alert = InsightAlert.objects.create(
                    company_id=company,
                    alert_type="contract_expiry",
                    title=f"{len(contracts)} contracts expiring within 30 days",
                    description="\n".join(
                        f"- {c.employee_id.employee_first_name} {c.employee_id.employee_last_name}: "
                        f"expires {c.contract_end_date} ({(c.contract_end_date - today).days} days)"
                        for c in contracts
                    ),
                    severity=severity,
                    expires_at=timezone.now() + timedelta(days=1),
                )
                alert.related_employees.set([c.employee_id for c in contracts])
                count = 1

        except ImportError:
            pass
        except Exception:
            logger.exception("Failed to generate contract expiry alerts")
        return count

    def birthday_alerts(self, company=None):
        """Surface birthdays in the next 7 days."""
        count = 0
        try:
            from employee.models import Employee
            from horilla_rag.models import InsightAlert

            today = date.today()
            upcoming = []

            employees = Employee.objects.filter(
                is_active=True,
                dob__isnull=False,
            )
            if company:
                employees = employees.filter(employee_work_info__company_id=company)

            for emp in employees.iterator():
                try:
                    bday_this_year = emp.dob.replace(year=today.year)
                except ValueError:
                    # Feb 29 birthdays in non-leap years
                    bday_this_year = emp.dob.replace(year=today.year, day=28)

                delta = (bday_this_year - today).days
                if 0 <= delta <= 7:
                    upcoming.append((emp, bday_this_year, delta))

            if upcoming:
                upcoming.sort(key=lambda x: x[2])
                alert = InsightAlert.objects.create(
                    company_id=company,
                    alert_type="birthday",
                    title=f"{len(upcoming)} birthdays in the next 7 days",
                    description="\n".join(
                        f"- {emp.employee_first_name} {emp.employee_last_name}: "
                        f"{bday} ({'today!' if delta == 0 else f'in {delta} days'})"
                        for emp, bday, delta in upcoming
                    ),
                    severity="info",
                    expires_at=timezone.now() + timedelta(days=1),
                )
                alert.related_employees.set([e for e, _, _ in upcoming])
                count = 1

        except Exception:
            logger.exception("Failed to generate birthday alerts")
        return count

    def probation_alerts(self, company=None):
        """Flag employees whose probation ends within 14 days."""
        count = 0
        try:
            from horilla_rag.models import InsightAlert
            from recruitment.models import Candidate

            today = date.today()
            cutoff = today + timedelta(days=14)

            ending = Candidate.objects.filter(
                probation_end__gte=today,
                probation_end__lte=cutoff,
                hired=True,
                is_active=True,
            )

            candidates = list(ending)
            if candidates:
                alert = InsightAlert.objects.create(
                    company_id=company,
                    alert_type="probation",
                    title=f"{len(candidates)} probation periods ending within 14 days",
                    description="\n".join(
                        f"- {c.name}: probation ends {c.probation_end} "
                        f"({(c.probation_end - today).days} days)"
                        for c in candidates
                    ),
                    severity="warning",
                    expires_at=timezone.now() + timedelta(days=1),
                )
                count = 1

        except ImportError:
            pass
        except Exception:
            logger.exception("Failed to generate probation alerts")
        return count
