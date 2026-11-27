"""Swiss cantonal holiday calendar, target-hour, and boundary-streak utilities.

Provides pure-Python calendar classification, monthly contractual target-minute
computation, hour-corridor resolution, and prior-month trailing work-streak
extraction for ``solver_core`` (``FR-006``, ``FR-009``, ``FR-012``, ``FR-013``,
``FR-028``).
"""

from __future__ import annotations

from collections.abc import Sequence
from collections.abc import Set as AbstractSet
from datetime import date, timedelta
from decimal import Decimal
from typing import Final
from uuid import UUID

import holidays

from solver_core.schemas.common import DayType, SwissCanton
from solver_core.schemas.staff import EmployeeProfile, PriorDayRecord, PriorMonthBoundary
from solver_core.time_utils import hours_to_minutes, period_date_range

_WORKDAYS_PER_WEEK: Final[Decimal] = Decimal(5)
_PERCENT_DIVISOR: Final[Decimal] = Decimal(100)
_ZERO: Final[Decimal] = Decimal("0")
_SATURDAY_WEEKDAY: Final[int] = 5
_SUNDAY_WEEKDAY: Final[int] = 6

__all__ = [
    "classify_day_type",
    "compute_employee_corridor_minutes",
    "compute_monthly_target_minutes",
    "compute_trailing_work_streak",
    "get_cantonal_holidays",
    "iter_period_dates",
]


def get_cantonal_holidays(canton: SwissCanton, year_month: str) -> tuple[date, ...]:
    """Return sorted official public holiday dates for ``canton`` within ``year_month`` (FR-006)."""
    p_start, p_end = period_date_range(year_month)
    cantonal_calendar = holidays.country_holidays("CH", subdiv=canton.value, years=p_start.year)
    return tuple(sorted(d for d in cantonal_calendar if p_start <= d <= p_end))


def classify_day_type(work_date: date, public_holidays: AbstractSet[date]) -> DayType:
    """Classify ``work_date`` as holiday, Saturday, Sunday, or weekday (FR-009)."""
    if work_date in public_holidays:
        return DayType.HOLIDAY
    weekday = work_date.weekday()
    if weekday == _SATURDAY_WEEKDAY:
        return DayType.SATURDAY
    if weekday == _SUNDAY_WEEKDAY:
        return DayType.SUNDAY
    return DayType.WEEKDAY


def iter_period_dates(year_month: str) -> tuple[date, ...]:
    """Return an ordered tuple of every calendar date in ``year_month`` inclusive."""
    p_start, p_end = period_date_range(year_month)
    num_days = (p_end - p_start).days + 1
    return tuple(p_start + timedelta(days=offset) for offset in range(num_days))


def compute_monthly_target_minutes(
    employee: EmployeeProfile,
    period_dates: Sequence[date],
    public_holidays: AbstractSet[date],
    approved_vacation_dates: AbstractSet[date],
    team_base_fulltime_weekly_h: Decimal,
) -> int:
    """Compute an employee's monthly contractual target work minutes (FR-012).

    Excludes weekends, statutory public holidays, and approved vacation dates
    without double-deducting overlapping dates.
    """
    base_weekly_h = (
        employee.base_fulltime_weekly_h
        if employee.base_fulltime_weekly_h is not None
        else team_base_fulltime_weekly_h
    )
    if not base_weekly_h.is_finite() or base_weekly_h < _ZERO:
        msg = f"base_fulltime_weekly_h must be a finite non-negative Decimal, got {base_weekly_h!r}"
        raise ValueError(msg)

    working_weekdays = sum(
        1
        for d in period_dates
        if d.weekday() < _SATURDAY_WEEKDAY
        and d not in public_holidays
        and d not in approved_vacation_dates
    )
    target_h = (
        Decimal(working_weekdays)
        * (base_weekly_h / _WORKDAYS_PER_WEEK)
        * (employee.pensum_pct / _PERCENT_DIVISOR)
    )
    return hours_to_minutes(target_h)


def compute_employee_corridor_minutes(
    employee: EmployeeProfile,
    team_default_corridor_h: Decimal,
) -> int:
    """Resolve an employee's monthly hour-balance tolerance corridor in minutes (FR-013)."""
    corridor_h = employee.corridor_h if employee.corridor_h is not None else team_default_corridor_h
    if not corridor_h.is_finite() or corridor_h < _ZERO:
        msg = f"corridor_h must be a finite non-negative Decimal, got {corridor_h!r}"
        raise ValueError(msg)
    return hours_to_minutes(corridor_h)


def compute_trailing_work_streak(
    employee_id: UUID,
    period_start: date,
    boundary: PriorMonthBoundary,
) -> int:
    """Compute consecutive worked days ending immediately before ``period_start`` (FR-028)."""
    records_by_date: dict[date, PriorDayRecord] = {
        rec.work_date: rec for rec in boundary.days if rec.employee_id == employee_id
    }
    computed_streak = 0
    cursor = period_start - timedelta(days=1)
    while (rec := records_by_date.get(cursor)) is not None:
        if rec.is_rest_day or not (bool(rec.segments) or rec.paid_hours > _ZERO):
            break
        computed_streak += 1
        cursor -= timedelta(days=1)

    return max(computed_streak, boundary.consecutive_work_days_at_month_end.get(employee_id, 0))
