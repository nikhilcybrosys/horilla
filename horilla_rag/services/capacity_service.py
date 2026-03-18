"""
Team capacity forecasting.
Predicts day-by-day availability based on approved leaves, holidays,
and company leave patterns.
"""

import logging
from datetime import date, timedelta

logger = logging.getLogger(__name__)


class CapacityService:
    """Forecasts team capacity for a given period."""

    def forecast(
        self,
        company_id=None,
        department_id=None,
        date_from=None,
        date_to=None,
    ):
        """
        Calculate day-by-day capacity forecast.

        Returns:
            dict with: period, total_headcount, daily_forecast (list of day dicts),
                       critical_days (days below 50% capacity)
        """
        from employee.models import Employee

        today = date.today()
        start = date_from or today
        end = date_to or (today + timedelta(days=14))

        employees = Employee.objects.filter(is_active=True)
        if company_id:
            employees = employees.filter(employee_work_info__company_id=company_id)
        if department_id:
            employees = employees.filter(
                employee_work_info__department_id=department_id
            )

        total_headcount = employees.count()
        if total_headcount == 0:
            return {
                "period": f"{start} to {end}",
                "total_headcount": 0,
                "daily_forecast": [],
                "critical_days": [],
            }

        employee_ids = set(employees.values_list("pk", flat=True))

        # Get approved leave requests in the period
        leave_map = self._build_leave_map(employee_ids, start, end)

        # Get holidays
        holiday_dates = self._get_holiday_dates(start, end)

        # Get company leave dates
        company_leave_dates = self._get_company_leave_dates(start, end)

        # Build day-by-day forecast
        daily = []
        critical = []
        current = start

        while current <= end:
            is_weekend = current.weekday() >= 5
            is_holiday = current in holiday_dates
            is_company_leave = current in company_leave_dates

            if is_weekend or is_holiday or is_company_leave:
                day_type = (
                    "holiday"
                    if is_holiday
                    else ("company_leave" if is_company_leave else "weekend")
                )
                daily.append(
                    {
                        "date": str(current),
                        "day": current.strftime("%A"),
                        "type": day_type,
                        "available": 0,
                        "on_leave": 0,
                        "capacity_pct": 0,
                    }
                )
            else:
                on_leave = len(leave_map.get(current, set()))
                available = total_headcount - on_leave
                capacity = round(available / total_headcount * 100, 1)

                day_data = {
                    "date": str(current),
                    "day": current.strftime("%A"),
                    "type": "working",
                    "available": available,
                    "on_leave": on_leave,
                    "capacity_pct": capacity,
                }
                daily.append(day_data)

                if capacity < 50:
                    critical.append(day_data)

            current += timedelta(days=1)

        return {
            "period": f"{start} to {end}",
            "total_headcount": total_headcount,
            "daily_forecast": daily,
            "critical_days": critical,
            "average_capacity_pct": round(
                sum(d["capacity_pct"] for d in daily if d["type"] == "working")
                / max(sum(1 for d in daily if d["type"] == "working"), 1),
                1,
            ),
        }

    def _build_leave_map(self, employee_ids, start, end):
        """Build date → set(employee_ids) map from approved leave requests."""
        leave_map = {}
        try:
            from leave.models import LeaveRequest

            leaves = LeaveRequest.objects.filter(
                employee_id__in=employee_ids,
                status="approved",
                start_date__lte=end,
                end_date__gte=start,
            )

            for lr in leaves:
                current = max(lr.start_date, start)
                lr_end = min(lr.end_date, end)
                while current <= lr_end:
                    if current not in leave_map:
                        leave_map[current] = set()
                    leave_map[current].add(lr.employee_id_id)
                    current += timedelta(days=1)

        except ImportError:
            pass
        return leave_map

    def _get_holiday_dates(self, start, end):
        """Get set of holiday dates in the range."""
        holiday_dates = set()
        try:
            from base.models import Holidays

            holidays = Holidays.objects.filter(
                start_date__lte=end,
                is_active=True,
            )
            for h in holidays:
                h_end = h.end_date or h.start_date
                current = max(h.start_date, start)
                while current <= min(h_end, end):
                    holiday_dates.add(current)
                    current += timedelta(days=1)
        except Exception:
            pass
        return holiday_dates

    def _get_company_leave_dates(self, start, end):
        """Get set of company leave dates in the range."""
        company_leave_dates = set()
        try:
            from base.methods import get_company_leave_dates

            year_dates = get_company_leave_dates(start.year)
            company_leave_dates.update(d for d in year_dates if start <= d <= end)
            if start.year != end.year:
                year_dates_next = get_company_leave_dates(end.year)
                company_leave_dates.update(
                    d for d in year_dates_next if start <= d <= end
                )
        except Exception:
            pass
        return company_leave_dates
