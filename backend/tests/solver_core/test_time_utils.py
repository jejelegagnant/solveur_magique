"""Europe/Zurich DST-safe temporal, night-overlap, and Art. 15 LTr break tests (NFR-024)."""

from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest

from solver_core import (
    ShiftSegment,
    check_ltr_break_compliance,
    daily_span_minutes,
    elapsed_minutes,
    hours_to_minutes,
    intervals_overlap,
    is_ambiguous_local_time,
    is_nonexistent_local_time,
    local_to_utc,
    minutes_to_hours,
    night_window_overlap_minutes,
    paid_minutes,
    period_date_range,
    prior_boundary_range,
    rest_minutes_between,
    segment_utc_interval,
    segments_utc_intervals,
)

# ---------------------------------------------------------------------------
# Europe/Zurich DST transitions (NFR-024)
# ---------------------------------------------------------------------------


@pytest.mark.dst
@pytest.mark.parametrize(
    ("transition_date", "expected_day_minutes"),
    [
        (date(2026, 3, 29), 23 * 60),  # March 2026 spring-forward (23 h)
        (date(2027, 3, 28), 23 * 60),  # March 2027 spring-forward (23 h)
        (date(2026, 10, 25), 25 * 60),  # October 2026 fall-back (25 h)
        (date(2027, 10, 31), 25 * 60),  # October 2027 fall-back (25 h)
        (date(2026, 6, 15), 24 * 60),  # Standard summer day (24 h)
    ],
)
def test_dst_calendar_day_utc_length(transition_date: date, expected_day_minutes: int) -> None:
    """Spring-forward days span 23 h (1380 min) and fall-back days span 25 h (1500 min)."""
    start_utc = local_to_utc(transition_date, time(0, 0))
    next_midnight_utc = local_to_utc(transition_date + timedelta(days=1), time(0, 0))
    assert (next_midnight_utc - start_utc) == timedelta(minutes=expected_day_minutes)


@pytest.mark.dst
@pytest.mark.parametrize(
    ("work_date", "expected_minutes"),
    [
        (date(2026, 3, 28), 420),  # Spring-forward 2026: 22:00 CET -> 06:00 CEST = 7 h
        (date(2027, 3, 27), 420),  # Spring-forward 2027: 22:00 CET -> 06:00 CEST = 7 h
        (date(2026, 10, 24), 540),  # Fall-back 2026: 22:00 CEST -> 06:00 CET = 9 h
        (date(2027, 10, 30), 540),  # Fall-back 2027: 22:00 CEST -> 06:00 CET = 9 h
        (date(2026, 3, 15), 480),  # Normal winter night: 8 h
        (date(2026, 7, 15), 480),  # Normal summer night: 8 h
    ],
)
def test_dst_overnight_shift_duration(work_date: date, expected_minutes: int) -> None:
    """Overnight 22:00-06:00 shift yields 420 min (spring), 540 min (fall), 480 min (normal)."""
    night = (ShiftSegment(start_time=time(22, 0), end_time=time(6, 0), crosses_midnight=True),)
    assert elapsed_minutes(work_date, night) == expected_minutes
    assert daily_span_minutes(work_date, night) == expected_minutes


@pytest.mark.dst
@pytest.mark.parametrize(
    ("prev_date", "next_date", "expected_rest_min"),
    [
        (date(2026, 3, 28), date(2026, 3, 29), 540),  # Spring-forward 2026: 9 h
        (date(2027, 3, 27), date(2027, 3, 28), 540),  # Spring-forward 2027: 9 h
        (date(2026, 10, 24), date(2026, 10, 25), 660),  # Fall-back 2026: 11 h
        (date(2027, 10, 30), date(2027, 10, 31), 660),  # Fall-back 2027: 11 h
        (date(2026, 3, 15), date(2026, 3, 16), 600),  # Normal night: 10 h
    ],
)
def test_dst_evening_to_morning_rest(
    prev_date: date,
    next_date: date,
    expected_rest_min: int,
) -> None:
    """Evening 21:00 to next morning 07:00 rest is 540m spring, 660m fall, 600m normal."""
    evening = (ShiftSegment(start_time=time(14, 0), end_time=time(21, 0)),)
    morning = (ShiftSegment(start_time=time(7, 0), end_time=time(15, 0)),)
    assert rest_minutes_between(prev_date, evening, next_date, morning) == expected_rest_min


@pytest.mark.dst
def test_cross_month_boundary_rest_and_overnight() -> None:
    """Rest and overnight durations stay exact across month-end boundaries."""
    evening = (ShiftSegment(start_time=time(14, 0), end_time=time(21, 0)),)
    morning = (ShiftSegment(start_time=time(7, 0), end_time=time(15, 0)),)
    assert rest_minutes_between(date(2026, 3, 31), evening, date(2026, 4, 1), morning) == 600

    night = (ShiftSegment(start_time=time(22, 0), end_time=time(6, 0), crosses_midnight=True),)
    assert elapsed_minutes(date(2026, 10, 31), night) == 480
    late_shift = (ShiftSegment(start_time=time(17, 0), end_time=time(22, 0)),)
    assert rest_minutes_between(date(2026, 10, 31), night, date(2026, 11, 1), late_shift) == 660

    # Fall-back on 2027-10-31: overnight 2027-10-30 22:00-06:00 (540 min) -> 2027-11-01 07:00
    assert elapsed_minutes(date(2027, 10, 30), night) == 540
    assert rest_minutes_between(date(2027, 10, 30), night, date(2027, 11, 1), morning) == 1500


@pytest.mark.dst
def test_nonexistent_and_ambiguous_local_times() -> None:
    """Spring-forward gaps raise ValueError unless allowed; fall-back ambiguities detected."""
    spring_day = date(2026, 3, 29)
    gap_time = time(2, 30)
    assert is_nonexistent_local_time(spring_day, gap_time) is True
    assert is_ambiguous_local_time(spring_day, gap_time) is False

    with pytest.raises(ValueError, match="does not exist"):
        local_to_utc(spring_day, gap_time)

    # Explicitly allowing nonexistent time succeeds and returns a UTC datetime
    allowed_utc = local_to_utc(spring_day, gap_time, allow_nonexistent=True)
    assert allowed_utc.tzinfo == UTC

    # Segment starting or ending inside spring-forward gap raises ValueError
    with pytest.raises(ValueError, match="does not exist"):
        segment_utc_interval(spring_day, ShiftSegment(start_time=time(2, 30), end_time=time(6, 0)))

    fall_day = date(2026, 10, 25)
    amb_time = time(2, 30)
    assert is_nonexistent_local_time(fall_day, amb_time) is False
    assert is_ambiguous_local_time(fall_day, amb_time) is True

    utc_first = local_to_utc(fall_day, amb_time, fold=0)
    utc_second = local_to_utc(fall_day, amb_time, fold=1)
    assert utc_second - utc_first == timedelta(hours=1)
    assert utc_first == datetime(2026, 10, 25, 0, 30, tzinfo=UTC)
    assert utc_second == datetime(2026, 10, 25, 1, 30, tzinfo=UTC)

    # Validation errors on fold and aware time
    with pytest.raises(ValueError, match="fold must be 0 or 1"):
        local_to_utc(fall_day, amb_time, fold=2)
    with pytest.raises(ValueError, match="fold must be 0 or 1"):
        local_to_utc(fall_day, amb_time, fold=True)
    with pytest.raises(ValueError, match="must be timezone-naive"):
        local_to_utc(fall_day, time(10, 0, tzinfo=UTC))


@pytest.mark.dst
def test_night_window_overlap_across_normal_custom_and_dst_nights() -> None:
    """Night-window overlap handles 23:00-06:00, Vaud CCT 20:00-06:00, early morning, and DST."""
    night = (ShiftSegment(start_time=time(22, 0), end_time=time(6, 0), crosses_midnight=True),)
    strict_night = (
        ShiftSegment(start_time=time(23, 0), end_time=time(6, 0), crosses_midnight=True),
    )
    early_morning = (ShiftSegment(start_time=time(4, 30), end_time=time(12, 30)),)
    day_shift = (ShiftSegment(start_time=time(8, 0), end_time=time(17, 0)),)
    evening = (ShiftSegment(start_time=time(16, 0), end_time=time(22, 0)),)

    # Normal winter/summer night
    assert night_window_overlap_minutes(date(2026, 3, 15), night) == 420
    assert night_window_overlap_minutes(date(2026, 3, 15), night, time(20, 0), time(6, 0)) == 480

    # Early morning & day & evening shifts
    assert night_window_overlap_minutes(date(2026, 3, 15), early_morning) == 90
    assert night_window_overlap_minutes(date(2026, 3, 15), day_shift) == 0
    assert night_window_overlap_minutes(date(2026, 3, 15), evening) == 0
    assert night_window_overlap_minutes(date(2026, 3, 15), evening, time(20, 0), time(6, 0)) == 120

    # Spring-forward night (2026-03-28 -> 2026-03-29): 23:00-06:00 is 360 min (6 h)
    assert night_window_overlap_minutes(date(2026, 3, 28), strict_night) == 360
    assert night_window_overlap_minutes(date(2026, 3, 28), night) == 360
    assert night_window_overlap_minutes(date(2026, 3, 28), night, time(20, 0), time(6, 0)) == 420

    # Fall-back night (2026-10-24 -> 2026-10-25): 23:00-06:00 is 480 min (8 h)
    assert night_window_overlap_minutes(date(2026, 10, 24), strict_night) == 480
    assert night_window_overlap_minutes(date(2026, 10, 24), night) == 480
    assert night_window_overlap_minutes(date(2026, 10, 24), night, time(20, 0), time(6, 0)) == 540

    with pytest.raises(ValueError, match="must differ"):
        night_window_overlap_minutes(date(2026, 3, 15), night, time(23, 0), time(23, 0))


# ---------------------------------------------------------------------------
# Split shifts & Art. 15 LTr mandatory breaks
# ---------------------------------------------------------------------------


def test_split_shift_elapsed_span_and_ltr_break_credit() -> None:
    """Split shift 07:00-09:00 + 16:00-21:00 has 420m elapsed, 840m span, and satisfies Art. 15."""
    mc1_segments = (
        ShiftSegment(start_time=time(7, 0), end_time=time(9, 0)),
        ShiftSegment(start_time=time(16, 0), end_time=time(21, 0)),
    )
    work_date = date(2026, 3, 10)
    assert elapsed_minutes(work_date, mc1_segments) == 420
    assert daily_span_minutes(work_date, mc1_segments) == 840
    assert paid_minutes(work_date, mc1_segments, unpaid_break_min=0) == 420
    # 420 min mid-day gap easily covers Art. 15 LTr break requirements
    assert check_ltr_break_compliance(work_date, mc1_segments, unpaid_break_min=0) == []


@pytest.mark.parametrize(
    ("end_time", "unpaid_break_min", "expected_code", "expected_required"),
    [
        # 5h30 (330 min): at threshold, no break required
        (time(12, 30), 0, None, None),
        # 5h31 (331 min): > 5.5h -> 15 min required
        (time(12, 31), 0, "LTR_BREAK_15M", 15),
        (time(12, 46), 15, None, None),  # 331 paid min with 15 min break -> OK
        # 7h00 (420 min) with 15m break -> still in >5.5h tier -> OK
        (time(14, 15), 15, None, None),
        # 7h01 (421 min) with 15m break -> >7.0h requires 30 min -> warning
        (time(14, 16), 15, "LTR_BREAK_30M", 30),
        (time(14, 31), 30, None, None),  # 421 paid min with 30 min break -> OK
        # 9h00 (540 min) with 30m break -> still in >7.0h tier -> OK
        (time(16, 30), 30, None, None),
        # 9h01 (541 min) with 30m break -> >9.0h requires 60 min -> warning
        (time(16, 31), 30, "LTR_BREAK_60M", 60),
        (time(17, 1), 60, None, None),  # 541 paid min with 60 min break -> OK
    ],
)
def test_ltr_art15_break_thresholds(
    end_time: time,
    unpaid_break_min: int,
    expected_code: str | None,
    expected_required: int | None,
) -> None:
    """Art. 15 LTr break checks enforce strict >330, >420, and >540 min thresholds."""
    shift_id = uuid4()
    segments = (ShiftSegment(start_time=time(7, 0), end_time=end_time),)
    warnings = check_ltr_break_compliance(
        date(2026, 3, 10),
        segments,
        unpaid_break_min=unpaid_break_min,
        shift_template_id=shift_id,
    )
    if expected_code is None:
        assert warnings == []
    else:
        assert len(warnings) == 1
        warning = warnings[0]
        assert warning.code == expected_code
        assert warning.required_break_min == expected_required
        assert warning.configured_break_min == unpaid_break_min
        assert warning.shift_template_id == shift_id


def test_ltr_break_paid_on_post_exemption() -> None:
    """paid_on_post_break=True exempts night/solo shifts from Art. 15 break warnings."""
    segments = (ShiftSegment(start_time=time(7, 0), end_time=time(17, 0)),)
    assert (
        check_ltr_break_compliance(
            date(2026, 3, 10),
            segments,
            unpaid_break_min=0,
            paid_on_post_break=True,
        )
        == []
    )


# ---------------------------------------------------------------------------
# General temporal helper functions
# ---------------------------------------------------------------------------


def test_paid_minutes_and_segments_validation() -> None:
    """paid_minutes and segments_utc_intervals reject invalid inputs."""
    seg = (ShiftSegment(start_time=time(8, 0), end_time=time(10, 0)),)
    with pytest.raises(ValueError, match="non-negative integer"):
        paid_minutes(date(2026, 3, 10), seg, unpaid_break_min=-5)
    with pytest.raises(ValueError, match="non-negative integer"):
        paid_minutes(date(2026, 3, 10), seg, unpaid_break_min=True)
    with pytest.raises(ValueError, match="cannot exceed elapsed"):
        paid_minutes(date(2026, 3, 10), seg, unpaid_break_min=121)

    with pytest.raises(ValueError, match="non-empty"):
        segments_utc_intervals(date(2026, 3, 10), ())
    with pytest.raises(ValueError, match="overlap or are out of chronological order"):
        segments_utc_intervals(
            date(2026, 3, 10),
            (
                ShiftSegment(start_time=time(8, 0), end_time=time(12, 0)),
                ShiftSegment(start_time=time(11, 0), end_time=time(15, 0)),
            ),
        )


def test_intervals_overlap() -> None:
    """Half-open interval overlap checks touch/disjoint/overlap and validate awareness."""
    t0 = datetime(2026, 3, 10, 7, 0, tzinfo=UTC)
    t1 = datetime(2026, 3, 10, 12, 0, tzinfo=UTC)
    t2 = datetime(2026, 3, 10, 16, 0, tzinfo=UTC)
    t_mid = datetime(2026, 3, 10, 10, 0, tzinfo=UTC)

    assert intervals_overlap((t0, t1), (t_mid, t2)) is True
    assert intervals_overlap((t0, t1), (t1, t2)) is False  # touching half-open
    assert intervals_overlap((t0, t_mid), (t1, t2)) is False  # disjoint

    naive_dt = datetime(2026, 3, 10, 7, 0)  # noqa: DTZ001
    with pytest.raises(ValueError, match="must be timezone-aware"):
        intervals_overlap((naive_dt, t1), (t0, t2))
    with pytest.raises(ValueError, match="must be <= end"):
        intervals_overlap((t1, t0), (t0, t2))


def test_period_date_range_and_prior_boundary_range() -> None:
    """period_date_range and prior_boundary_range handle leap years and year boundaries."""
    assert period_date_range("2026-02") == (date(2026, 2, 1), date(2026, 2, 28))
    assert period_date_range("2028-02") == (date(2028, 2, 1), date(2028, 2, 29))
    assert period_date_range("2026-03") == (date(2026, 3, 1), date(2026, 3, 31))

    assert prior_boundary_range("2026-03") == (date(2026, 2, 22), date(2026, 2, 28))
    assert prior_boundary_range("2028-03") == (date(2028, 2, 23), date(2028, 2, 29))
    assert prior_boundary_range("2026-01") == (date(2025, 12, 25), date(2025, 12, 31))
    assert prior_boundary_range("2026-03", lookback_days=14) == (
        date(2026, 2, 15),
        date(2026, 2, 28),
    )

    for bad_ym in ("2026-00", "2026-13", "26-03", "2026/03"):
        with pytest.raises(ValueError):
            period_date_range(bad_ym)

    with pytest.raises(ValueError, match="integer >= 1"):
        prior_boundary_range("2026-03", lookback_days=0)
    with pytest.raises(ValueError, match="integer >= 1"):
        prior_boundary_range("2026-03", lookback_days=True)


def test_hours_and_minutes_conversions() -> None:
    """hours_to_minutes and minutes_to_hours use ROUND_HALF_UP and validate types."""
    assert hours_to_minutes(Decimal("7.5")) == 450
    assert hours_to_minutes(Decimal("0.00")) == 0
    assert hours_to_minutes(Decimal("-1.25")) == -75
    # 0.025 h = 1.5 min -> ROUND_HALF_UP -> 2
    assert hours_to_minutes(Decimal("0.025")) == 2

    assert minutes_to_hours(450) == Decimal("7.50")
    assert minutes_to_hours(90) == Decimal("1.50")
    assert minutes_to_hours(20) == Decimal("0.33")
    assert minutes_to_hours(40) == Decimal("0.67")
    assert minutes_to_hours(0) == Decimal("0.00")

    with pytest.raises(ValueError, match="finite Decimal"):
        hours_to_minutes(Decimal("NaN"))
    with pytest.raises(ValueError, match="finite Decimal"):
        hours_to_minutes(Decimal("Infinity"))
    with pytest.raises(TypeError, match="not bool"):
        minutes_to_hours(True)
