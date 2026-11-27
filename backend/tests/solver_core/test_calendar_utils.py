"""Unit tests for solver_core.calendar_utils (FR-006, FR-009, FR-012, FR-013, FR-028)."""

from __future__ import annotations

from datetime import date, time
from decimal import Decimal
from uuid import uuid4

import pytest

from solver_core import (
    DayType,
    EmployeeProfile,
    PriorDayRecord,
    PriorMonthBoundary,
    ShiftSegment,
    SwissCanton,
    classify_day_type,
    compute_employee_corridor_minutes,
    compute_monthly_target_minutes,
    compute_trailing_work_streak,
    get_cantonal_holidays,
    iter_period_dates,
)

# ---------------------------------------------------------------------------
# get_cantonal_holidays (FR-006)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "canton",
    [
        SwissCanton.VD,
        SwissCanton.GE,
        SwissCanton.ZH,
        SwissCanton.FR,
        SwissCanton.VS,
        SwissCanton.TI,
    ],
)
def test_get_cantonal_holidays_swiss_national_day_all_cantons(canton: SwissCanton) -> None:
    """Swiss National Day (2026-08-01) is a statutory holiday across all tested cantons."""
    august_holidays = get_cantonal_holidays(canton, "2026-08")
    assert date(2026, 8, 1) in august_holidays
    assert august_holidays == tuple(sorted(august_holidays))


@pytest.mark.parametrize(
    ("canton", "year_month", "expected_present", "expected_absent"),
    [
        (
            SwissCanton.VD,
            "2026-01",
            (date(2026, 1, 1), date(2026, 1, 2)),
            (date(2026, 1, 6),),
        ),
        (
            SwissCanton.VD,
            "2026-09",
            (date(2026, 9, 21),),  # Lundi du Jeune federal
            (date(2026, 9, 10),),
        ),
        (
            SwissCanton.GE,
            "2026-09",
            (date(2026, 9, 10),),  # Jeune genevois
            (date(2026, 9, 21),),
        ),
        (
            SwissCanton.GE,
            "2026-12",
            (date(2026, 12, 25), date(2026, 12, 31)),  # Restauration de la Republique
            (date(2026, 12, 26),),
        ),
        (
            SwissCanton.ZH,
            "2026-05",
            (date(2026, 5, 1), date(2026, 5, 14), date(2026, 5, 25)),
            (),
        ),
        (
            SwissCanton.ZH,
            "2026-12",
            (date(2026, 12, 25), date(2026, 12, 26)),
            (date(2026, 12, 31),),
        ),
        (
            SwissCanton.FR,
            "2026-04",
            (date(2026, 4, 3),),
            (date(2026, 4, 6),),
        ),
        (
            SwissCanton.VS,
            "2026-03",
            (date(2026, 3, 19),),  # Saint-Joseph
            (),
        ),
        (
            SwissCanton.VS,
            "2026-08",
            (date(2026, 8, 1), date(2026, 8, 15)),  # Assomption
            (),
        ),
        (
            SwissCanton.TI,
            "2026-01",
            (date(2026, 1, 1), date(2026, 1, 6)),  # Epifania
            (date(2026, 1, 2),),
        ),
        (
            SwissCanton.TI,
            "2026-03",
            (date(2026, 3, 19),),  # San Giuseppe
            (),
        ),
    ],
)
def test_get_cantonal_holidays_canton_specific_dates(
    canton: SwissCanton,
    year_month: str,
    expected_present: tuple[date, ...],
    expected_absent: tuple[date, ...],
) -> None:
    """Cantonal calendars reflect genuine Swiss sub-canton public holiday variations."""
    found = get_cantonal_holidays(canton, year_month)
    for d in expected_present:
        assert d in found
    for d in expected_absent:
        assert d not in found


@pytest.mark.parametrize(
    "canton",
    [
        SwissCanton.VD,
        SwissCanton.GE,
        SwissCanton.ZH,
        SwissCanton.FR,
        SwissCanton.VS,
        SwissCanton.TI,
    ],
)
def test_get_cantonal_holidays_leap_year_february_2028(canton: SwissCanton) -> None:
    """Leap-year February 2028-02 resolves cleanly without date-range errors."""
    feb_holidays = get_cantonal_holidays(canton, "2028-02")
    assert all(date(2028, 2, 1) <= d <= date(2028, 2, 29) for d in feb_holidays)
    assert feb_holidays == ()


# ---------------------------------------------------------------------------
# classify_day_type (FR-009)
# ---------------------------------------------------------------------------


def test_classify_day_type_weekday_weekend_and_holiday_precedence() -> None:
    """Holiday takes precedence over weekday, Saturday, and Sunday classifications."""
    holidays_set = {
        date(2026, 3, 19),  # Thursday (Saint-Joseph)
        date(2026, 8, 1),  # Saturday (Swiss National Day)
        date(2026, 11, 1),  # Sunday (All Saints' Day)
    }

    assert classify_day_type(date(2026, 3, 2), holidays_set) == DayType.WEEKDAY  # Monday
    assert classify_day_type(date(2026, 3, 6), holidays_set) == DayType.WEEKDAY  # Friday
    assert classify_day_type(date(2026, 3, 7), holidays_set) == DayType.SATURDAY
    assert classify_day_type(date(2026, 3, 8), holidays_set) == DayType.SUNDAY

    # Holiday precedence over weekday, Saturday, and Sunday.
    assert classify_day_type(date(2026, 3, 19), holidays_set) == DayType.HOLIDAY
    assert classify_day_type(date(2026, 8, 1), holidays_set) == DayType.HOLIDAY
    assert classify_day_type(date(2026, 11, 1), holidays_set) == DayType.HOLIDAY


# ---------------------------------------------------------------------------
# iter_period_dates
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("year_month", "expected_len", "expected_first", "expected_last"),
    [
        ("2026-02", 28, date(2026, 2, 1), date(2026, 2, 28)),
        ("2028-02", 29, date(2028, 2, 1), date(2028, 2, 29)),
        ("2026-04", 30, date(2026, 4, 1), date(2026, 4, 30)),
        ("2026-03", 31, date(2026, 3, 1), date(2026, 3, 31)),
    ],
)
def test_iter_period_dates_month_lengths(
    year_month: str,
    expected_len: int,
    expected_first: date,
    expected_last: date,
) -> None:
    """iter_period_dates produces exact contiguous date sequences for 28/29/30/31-day months."""
    dates = iter_period_dates(year_month)
    assert len(dates) == expected_len
    assert dates[0] == expected_first
    assert dates[-1] == expected_last
    assert list(dates) == sorted(set(dates))


# ---------------------------------------------------------------------------
# compute_monthly_target_minutes (FR-012)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("pensum_pct", "expected_minutes"),
    [
        # March 2026 has 22 Mon-Fri weekdays. At 42.0h/wk = 8.4h/day = 504 min/day:
        # 100%: 22 * 8.4 = 184.8h = 11_088 min
        #  80%: 22 * 8.4 * 0.8 = 147.84h = 8_870.4 -> 8_870 min (ROUND_HALF_UP)
        #  60%: 22 * 8.4 * 0.6 = 110.88h = 6_652.8 -> 6_653 min (ROUND_HALF_UP)
        (Decimal("100.00"), 11_088),
        (Decimal("80.00"), 8_870),
        (Decimal("60.00"), 6_653),
    ],
)
def test_compute_monthly_target_minutes_swiss_pensums(
    pensum_pct: Decimal,
    expected_minutes: int,
) -> None:
    """Exact Decimal pensum math for 100%, 80%, and 60% FTE on a 42h/wk Swiss baseline."""
    emp = EmployeeProfile(
        id=uuid4(),
        display_label="Soignant",
        pensum_pct=pensum_pct,
    )
    march_dates = iter_period_dates("2026-03")
    target = compute_monthly_target_minutes(
        emp,
        march_dates,
        public_holidays=frozenset(),
        approved_vacation_dates=frozenset(),
        team_base_fulltime_weekly_h=Decimal("42.00"),
    )
    assert target == expected_minutes


def test_compute_monthly_target_minutes_employee_weekly_override() -> None:
    """Per-employee base_fulltime_weekly_h overrides the team default."""
    emp = EmployeeProfile(
        id=uuid4(),
        display_label="Soignant 40h",
        pensum_pct=Decimal("100.00"),
        base_fulltime_weekly_h=Decimal("40.00"),
    )
    # March 2026: 22 weekdays * (40 / 5) = 176.0h = 10_560 min (vs 11_088 min at 42h).
    march_dates = iter_period_dates("2026-03")
    target = compute_monthly_target_minutes(
        emp,
        march_dates,
        public_holidays=frozenset(),
        approved_vacation_dates=frozenset(),
        team_base_fulltime_weekly_h=Decimal("42.00"),
    )
    assert target == 10_560


def test_compute_monthly_target_minutes_deductions_without_double_counting() -> None:
    """Weekday vacations and holidays deduct once; overlaps with holidays/weekends do not double."""
    emp = EmployeeProfile(
        id=uuid4(),
        display_label="Soignant",
        pensum_pct=Decimal("100.00"),
    )
    # March 2026 has 22 weekdays.
    # 2026-03-19 is Thursday (holiday + vacation -> counted once)
    # 2026-03-20 is Friday (vacation only -> counted once)
    # 2026-03-21 is Saturday (weekend + vacation -> 0 deduction)
    # 2026-03-22 is Sunday (weekend + holiday -> 0 deduction)
    # Effective working weekdays = 22 - 2 = 20 -> 20 * 8.4h = 168.0h = 10_080 min.
    march_dates = iter_period_dates("2026-03")
    holidays_set = frozenset({date(2026, 3, 19), date(2026, 3, 22)})
    vacations_set = frozenset({date(2026, 3, 19), date(2026, 3, 20), date(2026, 3, 21)})

    target = compute_monthly_target_minutes(
        emp,
        march_dates,
        public_holidays=holidays_set,
        approved_vacation_dates=vacations_set,
        team_base_fulltime_weekly_h=Decimal("42.00"),
    )
    assert target == 10_080

    # Non-overlapping deduction check: 1 holiday + 2 weekday vacations = 19 weekdays = 9_576 min.
    target_separate = compute_monthly_target_minutes(
        emp,
        march_dates,
        public_holidays=frozenset({date(2026, 3, 19)}),
        approved_vacation_dates=frozenset({date(2026, 3, 9), date(2026, 3, 10)}),
        team_base_fulltime_weekly_h=Decimal("42.00"),
    )
    assert target_separate == 19 * 504


def test_compute_monthly_target_minutes_rejects_invalid_base_weekly_hours() -> None:
    """Negative or non-finite team_base_fulltime_weekly_h raises ValueError."""
    emp = EmployeeProfile(id=uuid4(), display_label="S", pensum_pct=Decimal("100.00"))
    march_dates = iter_period_dates("2026-03")
    for bad_hours in (Decimal("-1.00"), Decimal("NaN"), Decimal("Infinity")):
        with pytest.raises(ValueError, match="base_fulltime_weekly_h"):
            compute_monthly_target_minutes(
                emp,
                march_dates,
                public_holidays=frozenset(),
                approved_vacation_dates=frozenset(),
                team_base_fulltime_weekly_h=bad_hours,
            )


# ---------------------------------------------------------------------------
# compute_employee_corridor_minutes (FR-013)
# ---------------------------------------------------------------------------


def test_compute_employee_corridor_minutes_default_and_override() -> None:
    """Employee corridor_h overrides team default; None falls back to team default."""
    emp_default = EmployeeProfile(
        id=uuid4(),
        display_label="Default Corridor",
        pensum_pct=Decimal("100.00"),
        corridor_h=None,
    )
    emp_override = EmployeeProfile(
        id=uuid4(),
        display_label="Tight Corridor",
        pensum_pct=Decimal("80.00"),
        corridor_h=Decimal("6.50"),
    )
    emp_zero = EmployeeProfile(
        id=uuid4(),
        display_label="Zero Corridor",
        pensum_pct=Decimal("100.00"),
        corridor_h=Decimal("0.00"),
    )

    assert compute_employee_corridor_minutes(emp_default, Decimal("10.00")) == 600
    assert compute_employee_corridor_minutes(emp_override, Decimal("10.00")) == 390
    assert compute_employee_corridor_minutes(emp_zero, Decimal("10.00")) == 0

    for bad_corridor in (Decimal("-2.00"), Decimal("NaN"), Decimal("Infinity")):
        with pytest.raises(ValueError, match="corridor_h"):
            compute_employee_corridor_minutes(emp_default, bad_corridor)


# ---------------------------------------------------------------------------
# compute_trailing_work_streak (FR-028)
# ---------------------------------------------------------------------------


def test_compute_trailing_work_streak_consecutive_rest_gap_and_explicit_max() -> None:
    """Trailing streak counts backwards from period_start - 1 and takes max with explicit value."""
    emp_a = uuid4()
    emp_b = uuid4()
    emp_c = uuid4()
    emp_d = uuid4()
    seg = (ShiftSegment(start_time=time(7, 0), end_time=time(15, 0)),)
    period_start = date(2026, 3, 1)

    boundary = PriorMonthBoundary(
        days=(
            # emp_a: worked Feb 26, 27, 28; rest on Feb 25; worked Feb 24 -> streak == 3
            PriorDayRecord(
                employee_id=emp_a,
                work_date=date(2026, 2, 24),
                segments=seg,
                paid_hours=Decimal("8.00"),
            ),
            PriorDayRecord(
                employee_id=emp_a,
                work_date=date(2026, 2, 25),
                is_rest_day=True,
            ),
            PriorDayRecord(
                employee_id=emp_a,
                work_date=date(2026, 2, 26),
                segments=seg,
                paid_hours=Decimal("8.00"),
            ),
            PriorDayRecord(
                employee_id=emp_a,
                work_date=date(2026, 2, 27),
                segments=seg,
                paid_hours=Decimal("8.00"),
            ),
            PriorDayRecord(
                employee_id=emp_a,
                work_date=date(2026, 2, 28),
                segments=seg,
                paid_hours=Decimal("8.00"),
            ),
            # emp_b: worked Feb 28 and Feb 26, missing Feb 27 (gap day) -> computed streak == 1
            PriorDayRecord(
                employee_id=emp_b,
                work_date=date(2026, 2, 26),
                segments=seg,
                paid_hours=Decimal("8.00"),
            ),
            PriorDayRecord(
                employee_id=emp_b,
                work_date=date(2026, 2, 28),
                segments=(),
                paid_hours=Decimal("4.00"),
            ),
            # emp_c: rest on Feb 28 -> computed streak == 0, explicit == 5 -> max == 5
            PriorDayRecord(
                employee_id=emp_c,
                work_date=date(2026, 2, 27),
                segments=seg,
                paid_hours=Decimal("8.00"),
            ),
            PriorDayRecord(
                employee_id=emp_c,
                work_date=date(2026, 2, 28),
                is_rest_day=True,
            ),
        ),
        consecutive_work_days_at_month_end={
            emp_a: 2,  # computed 3 > explicit 2 -> 3
            emp_b: 0,  # computed 1 > explicit 0 -> 1
            emp_c: 5,  # explicit 5 > computed 0 -> 5
        },
    )

    assert compute_trailing_work_streak(emp_a, period_start, boundary) == 3
    assert compute_trailing_work_streak(emp_b, period_start, boundary) == 1
    assert compute_trailing_work_streak(emp_c, period_start, boundary) == 5
    assert compute_trailing_work_streak(emp_d, period_start, boundary) == 0
