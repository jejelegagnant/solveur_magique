"""Deterministic Hypothesis property-based invariant tests for solver_core (NFR-019)."""

from __future__ import annotations

from datetime import date, time, timedelta
from decimal import Decimal
from uuid import UUID

import pytest
from hypothesis import given
from hypothesis import strategies as st

from solver_core import (
    AvailabilityRequest,
    CoverageMatrix,
    CoverageRule,
    DayType,
    DoublureConfig,
    EmployeeProfile,
    LegalPresetType,
    Locale,
    PinnedCell,
    PreferenceWeight,
    PriorDayRecord,
    PriorMonthBoundary,
    RequestKind,
    RequestSource,
    ShiftSegment,
    ShiftTemplate,
    SolverInput,
    SolverOptions,
    SwissCanton,
    TeamContext,
    build_preset,
    daily_span_minutes,
    elapsed_minutes,
    hours_to_minutes,
    is_nonexistent_local_time,
    minutes_to_hours,
    night_window_overlap_minutes,
    paid_minutes,
    period_date_range,
    prior_boundary_range,
    rest_minutes_between,
    segment_utc_interval,
    segments_utc_intervals,
)

# Explicit Europe/Zurich DST transition weekends across 2025-2029 so every run exercises them.
_DST_WEEKEND_DATES: tuple[date, ...] = (
    date(2025, 3, 29),
    date(2025, 3, 30),
    date(2025, 10, 25),
    date(2025, 10, 26),
    date(2026, 3, 28),
    date(2026, 3, 29),
    date(2026, 10, 24),
    date(2026, 10, 25),
    date(2027, 3, 27),
    date(2027, 3, 28),
    date(2027, 10, 30),
    date(2027, 10, 31),
    date(2028, 3, 25),
    date(2028, 3, 26),
    date(2028, 10, 28),
    date(2028, 10, 29),
    date(2029, 3, 24),
    date(2029, 3, 25),
    date(2029, 10, 27),
    date(2029, 10, 28),
)

_DATES_2025_2029 = st.one_of(
    st.sampled_from(_DST_WEEKEND_DATES),
    st.dates(min_value=date(2025, 1, 1), max_value=date(2029, 12, 31)),
)

_BUILTIN_PRESETS: tuple[LegalPresetType, ...] = (
    LegalPresetType.LTR_45,
    LegalPresetType.LTR_50,
    LegalPresetType.OLT2_CARE,
    LegalPresetType.LGAV,
)


def _minute_to_time(minute_of_day: int) -> time:
    return time(minute_of_day // 60, minute_of_day % 60)


def _safe_wall_minute(d: date, minute_of_day: int) -> int:
    """Shift a wall-clock minute out of any Europe/Zurich spring-forward DST gap."""
    t = _minute_to_time(minute_of_day)
    if is_nonexistent_local_time(d, t):
        return minute_of_day + 60
    return minute_of_day


@st.composite
def valid_date_and_segments(draw: st.DrawFn) -> tuple[date, tuple[ShiftSegment, ...]]:
    """Generate a date in 2025-2029 and 1 or 2 valid, non-overlapping ShiftSegments."""
    work_date = draw(_DATES_2025_2029)
    num_segments = draw(st.integers(min_value=1, max_value=2))

    if num_segments == 1:
        crosses_midnight = draw(st.booleans())
        if crosses_midnight:
            start_min = _safe_wall_minute(
                work_date, draw(st.integers(min_value=18 * 60, max_value=23 * 60 + 45))
            )
            next_day = work_date + timedelta(days=1)
            end_min = _safe_wall_minute(next_day, draw(st.integers(min_value=0, max_value=10 * 60)))
            seg = ShiftSegment(
                start_time=_minute_to_time(start_min),
                end_time=_minute_to_time(end_min),
                crosses_midnight=True,
            )
            return (work_date, (seg,))

        start_min = _safe_wall_minute(work_date, draw(st.integers(min_value=0, max_value=21 * 60)))
        end_min = _safe_wall_minute(
            work_date,
            draw(st.integers(min_value=start_min + 15, max_value=23 * 60 + 55)),
        )
        if end_min <= start_min:
            end_min = start_min + 60
        seg = ShiftSegment(
            start_time=_minute_to_time(start_min),
            end_time=_minute_to_time(end_min),
            crosses_midnight=False,
        )
        return (work_date, (seg,))

    # Two non-overlapping chronological segments on work_date (final may cross midnight).
    s1 = _safe_wall_minute(work_date, draw(st.integers(min_value=5 * 60, max_value=10 * 60)))
    e1 = _safe_wall_minute(work_date, draw(st.integers(min_value=s1 + 30, max_value=13 * 60)))
    s2 = _safe_wall_minute(work_date, draw(st.integers(min_value=e1 + 30, max_value=20 * 60)))
    crosses_midnight = draw(st.booleans())
    if crosses_midnight:
        next_day = work_date + timedelta(days=1)
        e2 = _safe_wall_minute(next_day, draw(st.integers(min_value=0, max_value=7 * 60)))
        seg2 = ShiftSegment(
            start_time=_minute_to_time(s2),
            end_time=_minute_to_time(e2),
            crosses_midnight=True,
        )
    else:
        e2 = _safe_wall_minute(
            work_date, draw(st.integers(min_value=s2 + 30, max_value=23 * 60 + 55))
        )
        seg2 = ShiftSegment(
            start_time=_minute_to_time(s2),
            end_time=_minute_to_time(e2),
            crosses_midnight=False,
        )
    seg1 = ShiftSegment(
        start_time=_minute_to_time(s1),
        end_time=_minute_to_time(e1),
        crosses_midnight=False,
    )
    return (work_date, (seg1, seg2))


@st.composite
def valid_solver_input(draw: st.DrawFn) -> SolverInput:
    """Generate a complete, referentially valid SolverInput instance for round-trip testing."""
    year = draw(st.integers(min_value=2025, max_value=2029))
    month = draw(st.integers(min_value=1, max_value=12))
    year_month = f"{year:04d}-{month:02d}"
    p_start, p_end = period_date_range(year_month)
    prior_start, prior_end = prior_boundary_range(year_month, lookback_days=7)

    num_shifts = draw(st.integers(min_value=1, max_value=3))
    shift_templates: list[ShiftTemplate] = []
    shift_specs: tuple[tuple[str, tuple[ShiftSegment, ...], bool], ...] = (
        (
            "MC1",
            (
                ShiftSegment(start_time=time(7, 0), end_time=time(9, 0)),
                ShiftSegment(start_time=time(16, 0), end_time=time(21, 0)),
            ),
            False,
        ),
        (
            "M1",
            (ShiftSegment(start_time=time(7, 0), end_time=time(15, 30)),),
            False,
        ),
        (
            "N",
            (ShiftSegment(start_time=time(22, 0), end_time=time(6, 0), crosses_midnight=True),),
            True,
        ),
    )
    for idx in range(num_shifts):
        code, segs, is_night = shift_specs[idx]
        shift_templates.append(
            ShiftTemplate(
                id=UUID(int=0x2000 + idx + 1),
                erp_code=code,
                label=f"Poste {code}",
                segments=segs,
                unpaid_break_min=30 if code == "M1" else 0,
                paid_on_post_break=is_night,
                is_night_shift=is_night,
            )
        )
    shift_ids = tuple(s.id for s in shift_templates)

    num_employees = draw(st.integers(min_value=1, max_value=3))
    emp_ids = tuple(UUID(int=0x3000 + idx + 1) for idx in range(num_employees))
    employees: list[EmployeeProfile] = []
    for idx, emp_id in enumerate(emp_ids):
        doublure: DoublureConfig | None = None
        if idx == num_employees - 1 and num_employees >= 2 and draw(st.booleans()):
            d1 = draw(st.dates(min_value=p_start, max_value=p_end))
            d2 = draw(st.dates(min_value=d1, max_value=p_end))
            doublure = DoublureConfig(
                is_trainee=True,
                mentor_ids=(emp_ids[0],),
                start_date=d1,
                end_date=d2,
                counts_toward_solo_coverage=draw(st.booleans()),
            )
        pensum = Decimal(draw(st.integers(min_value=20, max_value=100)))
        employees.append(
            EmployeeProfile(
                id=emp_id,
                display_label=f"Soignant {idx + 1}",
                pensum_pct=pensum,
                current_solde_h=Decimal(draw(st.integers(min_value=-20, max_value=20)))
                / Decimal(2),
                qualified_shift_ids=shift_ids,
                doublure=doublure,
                free_sundays_ytd=draw(st.integers(min_value=0, max_value=12)),
            )
        )

    # Coverage rules (weekday rule per shift + optional in-month override)
    coverage_rules: list[CoverageRule] = []
    for sid in shift_ids:
        min_hc = draw(st.integers(min_value=0, max_value=2))
        target_hc = draw(st.integers(min_value=min_hc, max_value=3))
        coverage_rules.append(
            CoverageRule(
                shift_template_id=sid,
                day_type=DayType.WEEKDAY,
                min_headcount=min_hc,
                target_headcount=target_hc,
            )
        )
    if draw(st.booleans()):
        override_day = draw(st.dates(min_value=p_start, max_value=p_end))
        coverage_rules.append(
            CoverageRule(
                shift_template_id=shift_ids[0],
                override_date=override_day,
                min_headcount=1,
                target_headcount=2,
            )
        )

    # Availability requests (0 to 3)
    requests: list[AvailabilityRequest] = []
    num_reqs = draw(st.integers(min_value=0, max_value=3))
    for idx in range(num_reqs):
        req_emp = draw(st.sampled_from(emp_ids))
        req_date = draw(st.dates(min_value=p_start, max_value=p_end))
        kind = draw(st.sampled_from(list(RequestKind)))
        if kind == RequestKind.FIXED_SDE:
            requests.append(
                AvailabilityRequest(
                    id=UUID(int=0x4000 + idx + 1),
                    employee_id=req_emp,
                    request_date=req_date,
                    kind=kind,
                    custom_interval=ShiftSegment(start_time=time(9, 0), end_time=time(11, 0)),
                    sde_label="SDE/9/11",
                    source=RequestSource.MANAGER,
                )
            )
        else:
            req_shift = (
                draw(st.sampled_from(shift_ids))
                if kind in (RequestKind.SOFT_PREFER, RequestKind.SOFT_AVOID)
                else None
            )
            requests.append(
                AvailabilityRequest(
                    id=UUID(int=0x4000 + idx + 1),
                    employee_id=req_emp,
                    request_date=req_date,
                    kind=kind,
                    shift_template_id=req_shift,
                    weight=draw(st.sampled_from(list(PreferenceWeight))),
                    source=draw(st.sampled_from(list(RequestSource))),
                )
            )

    # Optional pinned cell
    pins: tuple[PinnedCell, ...] = ()
    if draw(st.booleans()):
        pin_day = draw(st.dates(min_value=p_start, max_value=p_end))
        is_off = draw(st.booleans())
        pins = (
            PinnedCell(
                employee_id=emp_ids[0],
                work_date=pin_day,
                shift_template_id=None if is_off else shift_ids[0],
                is_day_off=is_off,
            ),
        )

    # Prior month boundary record inside 7-day lookback
    prior_day = draw(st.dates(min_value=prior_start, max_value=prior_end))
    prior_is_rest = draw(st.booleans())
    boundary = PriorMonthBoundary(
        days=(
            PriorDayRecord(
                employee_id=emp_ids[0],
                work_date=prior_day,
                shift_template_id=None if prior_is_rest else shift_ids[0],
                segments=() if prior_is_rest else shift_templates[0].segments,
                paid_hours=Decimal("0.00") if prior_is_rest else Decimal("7.00"),
                is_rest_day=prior_is_rest,
            ),
        ),
        consecutive_work_days_at_month_end={
            emp_ids[0]: draw(st.integers(min_value=0, max_value=6))
        },
        rolling_14d_rest_minutes_by_employee={
            emp_ids[0]: (draw(st.integers(min_value=540, max_value=900)),),
        },
    )

    holidays = tuple(
        sorted(
            draw(
                st.sets(
                    st.dates(min_value=p_start, max_value=p_end),
                    min_size=0,
                    max_size=2,
                )
            )
        )
    )

    return SolverInput(
        period_id=UUID(int=0x1001),
        year_month=year_month,
        team=TeamContext(
            team_id=UUID(int=0x1002),
            name="Unite Propriete",
            canton_code=draw(st.sampled_from(list(SwissCanton))),
            locale=draw(st.sampled_from(list(Locale))),
        ),
        legal_rules=build_preset(draw(st.sampled_from(_BUILTIN_PRESETS))),
        shift_templates=tuple(shift_templates),
        coverage_matrix=CoverageMatrix(rules=tuple(coverage_rules)),
        employees=tuple(employees),
        availability_requests=tuple(requests),
        pinned_cells=pins,
        prior_month_boundary=boundary,
        public_holidays=holidays,
        options=SolverOptions(locale=draw(st.sampled_from(list(Locale)))),
    )


# ---------------------------------------------------------------------------
# Property tests (NFR-019)
# ---------------------------------------------------------------------------


@pytest.mark.property
@given(data=valid_date_and_segments())
def test_property_segment_utc_and_span_invariants(
    data: tuple[date, tuple[ShiftSegment, ...]],
) -> None:
    """Every valid segment has start_utc < end_utc, elapsed > 0, and span >= elapsed."""
    work_date, segments = data
    intervals = segments_utc_intervals(work_date, segments)
    assert len(intervals) == len(segments)
    for seg, (start_utc, end_utc) in zip(segments, intervals, strict=True):
        assert segment_utc_interval(work_date, seg) == (start_utc, end_utc)
        assert start_utc < end_utc

    elapsed = elapsed_minutes(work_date, segments)
    span = daily_span_minutes(work_date, segments)
    assert elapsed > 0
    assert span >= elapsed
    if len(segments) == 1:
        assert span == elapsed


@pytest.mark.property
@given(
    data=valid_date_and_segments(),
    night_window=st.sampled_from(
        [
            (time(23, 0), time(6, 0)),
            (time(20, 0), time(6, 0)),
            (time(22, 0), time(5, 0)),
        ]
    ),
)
def test_property_night_overlap_bounded_by_elapsed(
    data: tuple[date, tuple[ShiftSegment, ...]],
    night_window: tuple[time, time],
) -> None:
    """Night-window overlap is always within [0, elapsed_minutes], including DST transitions."""
    work_date, segments = data
    night_start, night_end = night_window
    elapsed = elapsed_minutes(work_date, segments)
    overlap = night_window_overlap_minutes(work_date, segments, night_start, night_end)
    assert 0 <= overlap <= elapsed


@pytest.mark.property
@given(
    data=valid_date_and_segments(),
    break_ratio=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
)
def test_property_paid_minutes_exact_subtraction(
    data: tuple[date, tuple[ShiftSegment, ...]],
    break_ratio: float,
) -> None:
    """paid_minutes always equals elapsed_minutes - unpaid_break_min."""
    work_date, segments = data
    elapsed = elapsed_minutes(work_date, segments)
    unpaid_break_min = int(elapsed * break_ratio)
    assert paid_minutes(work_date, segments, unpaid_break_min) == elapsed - unpaid_break_min


@pytest.mark.property
@given(
    first=valid_date_and_segments(),
    day_offset=st.integers(min_value=0, max_value=3),
    second_segments=st.sampled_from(
        [
            (ShiftSegment(start_time=time(7, 0), end_time=time(15, 0)),),
            (
                ShiftSegment(start_time=time(7, 0), end_time=time(9, 0)),
                ShiftSegment(start_time=time(16, 0), end_time=time(21, 0)),
            ),
            (ShiftSegment(start_time=time(22, 0), end_time=time(6, 0), crosses_midnight=True),),
        ]
    ),
)
def test_property_rest_minutes_matches_exact_utc_difference(
    first: tuple[date, tuple[ShiftSegment, ...]],
    day_offset: int,
    second_segments: tuple[ShiftSegment, ...],
) -> None:
    """rest_minutes_between matches exact UTC delta between prev end and next start."""
    prev_date, prev_segments = first
    next_date = prev_date + timedelta(days=day_offset)

    prev_intervals = segments_utc_intervals(prev_date, prev_segments)
    next_intervals = segments_utc_intervals(next_date, second_segments)
    expected_rest = (next_intervals[0][0] - prev_intervals[-1][1]) // timedelta(minutes=1)

    assert (
        rest_minutes_between(prev_date, prev_segments, next_date, second_segments) == expected_rest
    )


@pytest.mark.property
@given(quarter_hours=st.integers(min_value=-400, max_value=400))
def test_property_hours_minutes_quarter_hour_round_trip(quarter_hours: int) -> None:
    """Exact quarter-hour decimals round-trip losslessly between hours and minutes."""
    hours = (Decimal(quarter_hours) * Decimal("0.25")).quantize(Decimal("0.01"))
    minutes = hours_to_minutes(hours)
    assert minutes == quarter_hours * 15
    assert minutes_to_hours(minutes) == hours


@pytest.mark.property
@given(minutes=st.integers(min_value=-10_000, max_value=10_000))
def test_property_minutes_to_hours_to_minutes_bounded(minutes: int) -> None:
    """Converting arbitrary minutes -> 2dp hours -> minutes stays within +-1 minute."""
    hours = minutes_to_hours(minutes)
    back = hours_to_minutes(hours)
    assert abs(back - minutes) <= 1


@pytest.mark.property
@given(problem=valid_solver_input())
def test_property_solver_input_json_round_trip(problem: SolverInput) -> None:
    """Any valid generated SolverInput round-trips identically via JSON."""
    serialized = problem.model_dump_json()
    restored = SolverInput.model_validate_json(serialized)
    assert restored == problem
    assert (restored.period_start, restored.period_end) == period_date_range(restored.year_month)
