"""CP-SAT performance benchmarks across 5-35 staff Swiss care schedules (NFR-001).

Validates that realistic 31-day schedules with mixed pensums, split/day/evening/night
shifts, vacations, FIXED_SDE meetings, cantonal holidays, and 7-day prior-month
boundaries solve with zero pouliste gaps, pass the independent hard-constraint
verifier, and satisfy NFR-001 latency targets (p50 < 2.0s, p95 < 10.0s).
"""

from __future__ import annotations

import math
from datetime import date, time
from decimal import Decimal
from time import perf_counter
from uuid import UUID

import pytest

from solver_core import (
    AvailabilityRequest,
    CoverageMatrix,
    CoverageRule,
    DayType,
    EmployeeProfile,
    LegalPresetType,
    Locale,
    PriorDayRecord,
    PriorMonthBoundary,
    RequestKind,
    RequestSource,
    ShiftSegment,
    ShiftTemplate,
    SolverInput,
    SolverOptions,
    SolverStatus,
    SwissCanton,
    TeamContext,
    build_preset,
    classify_day_type,
    compute_monthly_target_minutes,
    get_cantonal_holidays,
    iter_period_dates,
    solve_schedule,
)
from tests.solver_core.test_model_builder import _assert_valid_solution

BENCHMARK_TEAM_SIZES: tuple[int, ...] = (5, 10, 15, 20, 25, 30, 35)

_PENSUM_CYCLE: tuple[Decimal, ...] = (
    Decimal("100.00"),
    Decimal("100.00"),
    Decimal("80.00"),
    Decimal("60.00"),
    Decimal("50.00"),
)
_SOLDE_CYCLE: tuple[Decimal, ...] = (
    Decimal("2.00"),
    Decimal("-2.50"),
    Decimal("1.00"),
    Decimal("-1.50"),
    Decimal("0.00"),
)

_BENCH_SHIFT_MC1_ID = UUID("51000000-0000-4000-8000-000000000001")
_BENCH_SHIFT_M1_ID = UUID("51000000-0000-4000-8000-000000000002")
_BENCH_SHIFT_S1_ID = UUID("51000000-0000-4000-8000-000000000003")
_BENCH_SHIFT_N_ID = UUID("51000000-0000-4000-8000-000000000004")


def _benchmark_shifts() -> tuple[ShiftTemplate, ShiftTemplate, ShiftTemplate, ShiftTemplate]:
    """Return realistic Swiss care shifts: MC1 (7h split), M1 (8h), S1 (8h), N (8h night)."""
    mc1 = ShiftTemplate(
        id=_BENCH_SHIFT_MC1_ID,
        erp_code="MC1",
        label="Matin-Soir coupe 1",
        segments=(
            ShiftSegment(start_time=time(7, 0), end_time=time(9, 0)),
            ShiftSegment(start_time=time(16, 0), end_time=time(21, 0)),
        ),
        unpaid_break_min=0,
        paid_duration_h=Decimal("7.00"),
    )
    m1 = ShiftTemplate(
        id=_BENCH_SHIFT_M1_ID,
        erp_code="M1",
        label="Matin 1",
        segments=(ShiftSegment(start_time=time(7, 0), end_time=time(15, 30)),),
        unpaid_break_min=30,
        paid_duration_h=Decimal("8.00"),
    )
    s1 = ShiftTemplate(
        id=_BENCH_SHIFT_S1_ID,
        erp_code="S1",
        label="Soir 1",
        segments=(ShiftSegment(start_time=time(13, 30), end_time=time(22, 0)),),
        unpaid_break_min=30,
        paid_duration_h=Decimal("8.00"),
    )
    night = ShiftTemplate(
        id=_BENCH_SHIFT_N_ID,
        erp_code="N",
        label="Nuit",
        segments=(
            ShiftSegment(start_time=time(22, 0), end_time=time(6, 0), crosses_midnight=True),
        ),
        unpaid_break_min=0,
        paid_on_post_break=True,
        paid_duration_h=Decimal("8.00"),
        is_night_shift=True,
    )
    return (mc1, m1, s1, night)


def build_realistic_swiss_care_benchmark(
    num_staff: int,
    *,
    year_month: str = "2026-05",
    canton: SwissCanton = SwissCanton.VD,
) -> SolverInput:
    """Generate a balanced 31-day Swiss care SolverInput fixture for ``num_staff`` employees."""
    mc1, m1, s1, night = _benchmark_shifts()
    shifts = (mc1, m1, s1, night)
    period_dates = iter_period_dates(year_month)
    public_holidays = get_cantonal_holidays(canton, year_month)
    holiday_set = frozenset(public_holidays)

    team = TeamContext(
        team_id=UUID(f"50000000-0000-4000-8000-{num_staff:012d}"),
        name=f"Fondation Benchmark {num_staff}p",
        canton_code=canton,
        base_fulltime_weekly_h=Decimal("42.00"),
        default_corridor_h=Decimal("10.00"),
        locale=Locale.FR_CH,
    )

    employees: list[EmployeeProfile] = []
    for idx in range(num_staff):
        employees.append(
            EmployeeProfile(
                id=UUID(f"52000000-0000-4000-8000-{idx + 1:012d}"),
                display_label=f"Soignant {idx + 1:02d}",
                erp_employee_code=f"EMP{idx + 1:03d}",
                pensum_pct=_PENSUM_CYCLE[idx % len(_PENSUM_CYCLE)],
                current_solde_h=_SOLDE_CYCLE[idx % len(_SOLDE_CYCLE)],
                role_tags=("soins",),
            )
        )

    # Realistic vacations (3 consecutive weekdays for 1 employee per 5) and 2h FIXED_SDE meetings.
    requests: list[AvailabilityRequest] = []
    vac_by_emp: dict[UUID, set[date]] = {emp.id: set() for emp in employees}
    sde_min_by_emp: dict[UUID, int] = {emp.id: 0 for emp in employees}
    req_counter = 1

    weekdays = [d for d in period_dates if classify_day_type(d, holiday_set) == DayType.WEEKDAY]
    for group_idx in range(num_staff // 5):
        vac_emp = employees[group_idx * 5 + 2]  # 80% FTE employee
        start_slot = (group_idx * 3) % max(1, len(weekdays) - 3)
        for vac_date in weekdays[start_slot : start_slot + 3]:
            requests.append(
                AvailabilityRequest(
                    id=UUID(f"53000000-0000-4000-8000-{req_counter:012d}"),
                    employee_id=vac_emp.id,
                    request_date=vac_date,
                    kind=RequestKind.VACATION_V,
                    source=RequestSource.MANAGER,
                    approved=True,
                )
            )
            vac_by_emp[vac_emp.id].add(vac_date)
            req_counter += 1

        sde_emp = employees[group_idx * 5]  # 100% FTE employee attends a 2h team SDE meeting
        sde_date = weekdays[min(len(weekdays) - 1, 5 + (group_idx % 5))]
        requests.append(
            AvailabilityRequest(
                id=UUID(f"53000000-0000-4000-8000-{req_counter:012d}"),
                employee_id=sde_emp.id,
                request_date=sde_date,
                kind=RequestKind.FIXED_SDE,
                custom_interval=ShiftSegment(start_time=time(10, 0), end_time=time(12, 0)),
                sde_label="SDE/10/12",
                source=RequestSource.MANAGER,
                approved=True,
            )
        )
        sde_min_by_emp[sde_emp.id] += 120
        req_counter += 1

    # Realistic 7-day prior-month boundary (trailing shifts & rest days).
    prior_days: list[PriorDayRecord] = []
    period_start = period_dates[0]
    for idx, emp in enumerate(employees):
        last_day = date.fromordinal(period_start.toordinal() - 1)
        prev_day = date.fromordinal(period_start.toordinal() - 2)
        if idx % 5 == 0:
            # Worked evening shift on the final day of prior month.
            prior_days.append(
                PriorDayRecord(
                    employee_id=emp.id,
                    work_date=last_day,
                    shift_template_id=s1.id,
                    segments=s1.segments,
                    paid_hours=Decimal("8.00"),
                )
            )
        elif idx % 5 == 1:
            # Worked night shift on the final day of prior month.
            prior_days.append(
                PriorDayRecord(
                    employee_id=emp.id,
                    work_date=last_day,
                    shift_template_id=night.id,
                    segments=night.segments,
                    paid_hours=Decimal("8.00"),
                )
            )
        else:
            prior_days.append(
                PriorDayRecord(
                    employee_id=emp.id,
                    work_date=prev_day,
                    shift_template_id=m1.id,
                    segments=m1.segments,
                    paid_hours=Decimal("8.00"),
                )
            )
            prior_days.append(
                PriorDayRecord(
                    employee_id=emp.id,
                    work_date=last_day,
                    is_rest_day=True,
                )
            )

    boundary = PriorMonthBoundary(
        days=tuple(prior_days),
        consecutive_work_days_at_month_end={
            emp.id: (3 if idx % 5 in (0, 1) else 0) for idx, emp in enumerate(employees)
        },
    )

    # Compute exact team regular-shift capacity (in minutes) and size daily coverage to match.
    total_regular_target_min = sum(
        compute_monthly_target_minutes(
            emp,
            period_dates,
            holiday_set,
            vac_by_emp[emp.id],
            team.base_fulltime_weekly_h,
        )
        - sde_min_by_emp[emp.id]
        for emp in employees
    )

    day_type_counts: dict[DayType, int] = {dt: 0 for dt in DayType}
    for d in period_dates:
        day_type_counts[classify_day_type(d, holiday_set)] += 1

    # Scale per-day shift slots proportionally to num_staff while matching total monthly hours.
    # Start with balanced baseline headcounts per (shift, day_type), then calibrate target_hc
    # so min_hours <= total_regular_target_min <= target_hours cleanly.
    avg_shifts_per_day = (total_regular_target_min / 60.0) / (len(period_dates) * 7.8)
    weekday_slots = max(2, round(avg_shifts_per_day * 1.12))
    weekend_slots = max(2, round(avg_shifts_per_day * 0.82))

    def _distribute_slots(total_slots: int) -> tuple[int, int, int, int]:
        """Distribute daily slots across (MC1, M1, S1, N) with >= 1 night when total >= 4."""
        if total_slots <= 2:
            return (0, 1, 1, 0)
        if total_slots == 3:
            return (1, 1, 1, 0)
        n_hc = max(1, round(total_slots * 0.16))
        mc1_hc = max(1, round(total_slots * 0.20))
        remaining = total_slots - n_hc - mc1_hc
        m1_hc = (remaining + 1) // 2
        s1_hc = remaining - m1_hc
        return (mc1_hc, m1_hc, s1_hc, n_hc)

    wk_min = list(_distribute_slots(max(2, weekday_slots - 1)))
    we_min = list(_distribute_slots(max(2, weekend_slots - 1)))
    if num_staff == 5:
        # Ensure all 4 shift types (including MC1 & N) are actively scheduled even at 5 staff.
        wk_min = [1, 1, 1, 0]
        we_min = [0, 1, 0, 1]

    wk_tgt = [c + (1 if idx in (1, 2) else 0) for idx, c in enumerate(wk_min)]
    we_tgt = [c + (1 if idx == 1 else 0) for idx, c in enumerate(we_min)]
    if num_staff == 5:
        wk_tgt = [1, 1, 1, 1]
        we_tgt = [1, 1, 1, 1]

    shift_min_durations = (420, 480, 480, 480)
    num_wk = day_type_counts[DayType.WEEKDAY]
    num_we = (
        day_type_counts[DayType.SATURDAY]
        + day_type_counts[DayType.SUNDAY]
        + day_type_counts[DayType.HOLIDAY]
    )

    def _total_min(wk: list[int], we: list[int]) -> int:
        return sum(
            (wk[i] * num_wk + we[i] * num_we) * shift_min_durations[i] for i in range(len(shifts))
        )

    # Guarantee total_min_hours <= total_regular_target_min <= total_target_hours.
    while _total_min(wk_min, we_min) > total_regular_target_min - 300 * num_staff:
        for i in (1, 2, 0, 3):
            if wk_min[i] > 1:
                wk_min[i] -= 1
                break
        else:
            break

    while _total_min(wk_tgt, we_tgt) < total_regular_target_min + 300 * num_staff:
        for i in (1, 2, 0):
            wk_tgt[i] += 1
            if _total_min(wk_tgt, we_tgt) >= total_regular_target_min + 300 * num_staff:
                break

    rules: list[CoverageRule] = []
    for s_idx, shift in enumerate(shifts):
        for dt in DayType:
            is_wk = dt == DayType.WEEKDAY
            min_hc = wk_min[s_idx] if is_wk else we_min[s_idx]
            tgt_hc = max(min_hc, wk_tgt[s_idx] if is_wk else we_tgt[s_idx])
            rules.append(
                CoverageRule(
                    shift_template_id=shift.id,
                    day_type=dt,
                    min_headcount=min_hc,
                    target_headcount=tgt_hc,
                )
            )

    return SolverInput(
        period_id=UUID(f"54000000-0000-4000-8000-{num_staff:012d}"),
        year_month=year_month,
        team=team,
        legal_rules=build_preset(LegalPresetType.OLT2_CARE),
        shift_templates=shifts,
        coverage_matrix=CoverageMatrix(rules=tuple(rules)),
        employees=tuple(employees),
        availability_requests=tuple(requests),
        prior_month_boundary=boundary,
        public_holidays=public_holidays,
        options=SolverOptions(
            timeout_sec=15,
            allow_pouliste=True,
            random_seed=202605,
            num_search_workers=1,
            locale=Locale.FR_CH,
        ),
    )


def _percentile(values: list[float], pct: float) -> float:
    """Compute exact linear-interpolated percentile (0-100) on a non-empty list."""
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    rank = (pct / 100.0) * (len(ordered) - 1)
    lo = math.floor(rank)
    hi = math.ceil(rank)
    if lo == hi:
        return ordered[lo]
    return ordered[lo] + (ordered[hi] - ordered[lo]) * (rank - lo)


@pytest.mark.benchmark
def test_nfr001_benchmark_5_to_35_staff_latency_and_validity() -> None:
    """NFR-001: 5-35 staff realistic 31-day schedules solve with 0 gaps, p50 < 2.0s, p95 < 10.0s."""
    timings_sec: dict[int, float] = {}

    for num_staff in BENCHMARK_TEAM_SIZES:
        problem = build_realistic_swiss_care_benchmark(num_staff)
        t0 = perf_counter()
        output = solve_schedule(problem)
        elapsed_sec = perf_counter() - t0
        timings_sec[num_staff] = elapsed_sec

        assert output.status in (SolverStatus.OPTIMAL, SolverStatus.FEASIBLE), (
            f"Team size {num_staff} failed with status={output.status}"
        )
        _assert_valid_solution(problem, output)
        assert output.solutions[0].kpis.total_pouliste_gaps == 0, (
            f"Team size {num_staff} produced unexpected pouliste gaps: "
            f"{output.solutions[0].kpis.total_pouliste_gaps}"
        )

    samples = list(timings_sec.values())
    p50_sec = _percentile(samples, 50.0)
    p95_sec = _percentile(samples, 95.0)

    summary = ", ".join(f"{n}p={t:.3f}s" for n, t in timings_sec.items())
    print(f"\n[NFR-001 Benchmark] {summary} | p50={p50_sec:.3f}s, p95={p95_sec:.3f}s")

    assert p50_sec < 2.0, f"NFR-001 p50 latency exceeded 2.0s: {p50_sec:.3f}s ({summary})"
    assert p95_sec < 10.0, f"NFR-001 p95 latency exceeded 10.0s: {p95_sec:.3f}s ({summary})"
