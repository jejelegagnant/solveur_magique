"""Integration & invariant tests for solver_core.model_builder.solve_schedule.

Covers FR-009, FR-010, FR-012, FR-013, FR-027, FR-028, FR-029, FR-031,
NFR-002, NFR-019, and NFR-024 with an independent pure-Python post-solve verifier.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

import pytest

from solver_core import (
    AvailabilityRequest,
    CoverageMatrix,
    CoverageRule,
    DayType,
    EmployeeProfile,
    LegalPresetType,
    LegalRuleSet,
    Locale,
    PinnedCell,
    PriorDayRecord,
    PriorMonthBoundary,
    RequestKind,
    RequestSource,
    ShiftAssignmentOut,
    ShiftSegment,
    ShiftTemplate,
    SolverInput,
    SolverOptions,
    SolverOutput,
    SolverStatus,
    SwissCanton,
    TeamContext,
    build_preset,
    classify_day_type,
    compute_employee_corridor_minutes,
    compute_monthly_target_minutes,
    compute_trailing_work_streak,
    hours_to_minutes,
    intervals_overlap,
    iter_period_dates,
    minutes_to_hours,
    paid_minutes,
    rest_minutes_between,
    segment_utc_interval,
    segments_utc_intervals,
    solve_schedule,
)

_ONE_MIN = timedelta(minutes=1)
_HARD_UNAVAIL_KINDS = frozenset(
    {
        RequestKind.VACATION_V,
        RequestKind.WEEKEND_BUFFER_X,
        RequestKind.HARD_UNAVAIL,
    }
)


# ---------------------------------------------------------------------------
# Independent pure-Python post-solve hard-constraint verifier
# ---------------------------------------------------------------------------


def _expected_shift_paid_min(work_date: date, shift: ShiftTemplate) -> int:
    if shift.paid_duration_h is not None:
        return hours_to_minutes(shift.paid_duration_h)
    return paid_minutes(work_date, shift.segments, shift.unpaid_break_min)


def _assert_valid_solution(problem: SolverInput, output: SolverOutput) -> None:
    """Independently verify every hard constraint and accounting invariant on SolverOutput."""
    assert output.period_id == problem.period_id
    assert output.status in (SolverStatus.OPTIMAL, SolverStatus.FEASIBLE)
    assert len(output.solutions) >= 1
    assert not output.conflict_cards
    assert output.error_message is None

    period_dates = iter_period_dates(problem.year_month)
    period_date_set = set(period_dates)
    public_holidays = frozenset(problem.public_holidays)
    emp_by_id: dict[UUID, EmployeeProfile] = {emp.id: emp for emp in problem.employees}
    shift_by_id: dict[UUID, ShiftTemplate] = {s.id: s for s in problem.shift_templates}

    legal = problem.legal_rules
    min_rest_min = hours_to_minutes(
        legal.min_daily_rest_h
        if legal.reduced_rest_avg_window_days is not None or legal.min_reduced_rest_h is None
        else legal.min_reduced_rest_h
    )
    max_span_min = hours_to_minutes(legal.max_daily_span_h)
    max_work_min = hours_to_minutes(legal.max_daily_work_h)

    approved_vacations: dict[UUID, set[date]] = {emp.id: set() for emp in problem.employees}
    approved_sdes_by_emp_date: dict[tuple[UUID, date], list[AvailabilityRequest]] = {}
    for req in problem.availability_requests:
        if not req.approved:
            continue
        if req.kind == RequestKind.VACATION_V:
            approved_vacations[req.employee_id].add(req.request_date)
        elif req.kind == RequestKind.FIXED_SDE and req.custom_interval is not None:
            approved_sdes_by_emp_date.setdefault((req.employee_id, req.request_date), []).append(
                req
            )

    for solution in output.solutions:
        regular_by_emp_date: dict[tuple[UUID, date], ShiftAssignmentOut] = {}
        sde_by_emp_date: dict[tuple[UUID, date], list[ShiftAssignmentOut]] = {}
        assigned_count: dict[tuple[date, UUID], int] = {}

        # 1. Partition assignments, check no double-bookings, qualifications, role tags, paid_hours.
        for asgn in solution.assignments:
            assert asgn.employee_id in emp_by_id
            assert asgn.work_date in period_date_set
            emp = emp_by_id[asgn.employee_id]

            if asgn.is_sde:
                assert asgn.shift_template_id is None
                sde_by_emp_date.setdefault((asgn.employee_id, asgn.work_date), []).append(asgn)
                continue

            assert asgn.shift_template_id is not None
            assert asgn.shift_template_id in shift_by_id
            key = (asgn.employee_id, asgn.work_date)
            assert key not in regular_by_emp_date, f"Double-booking detected on {key}"
            regular_by_emp_date[key] = asgn

            shift = shift_by_id[asgn.shift_template_id]
            if emp.qualified_shift_ids:
                assert shift.id in emp.qualified_shift_ids, (
                    f"Employee {emp.display_label} not qualified for {shift.erp_code}"
                )
            if shift.required_role_tag is not None:
                assert shift.required_role_tag in emp.role_tags, (
                    f"Employee {emp.display_label} missing role tag {shift.required_role_tag}"
                )

            expected_paid = _expected_shift_paid_min(asgn.work_date, shift)
            assert asgn.paid_hours == minutes_to_hours(expected_paid)

            cov_key = (asgn.work_date, shift.id)
            assigned_count[cov_key] = assigned_count.get(cov_key, 0) + 1

        # 2. Verify every approved FIXED_SDE is emitted as is_sde=True (and excluded from coverage).
        assert set(sde_by_emp_date.keys()) == set(approved_sdes_by_emp_date.keys())
        for key, expected_reqs in approved_sdes_by_emp_date.items():
            emitted = sde_by_emp_date[key]
            assert len(emitted) == len(expected_reqs)
            expected_hours = sorted(
                minutes_to_hours(
                    (
                        segment_utc_interval(req.request_date, req.custom_interval)[1]
                        - segment_utc_interval(req.request_date, req.custom_interval)[0]
                    )
                    // _ONE_MIN
                )
                for req in expected_reqs
                if req.custom_interval is not None
            )
            emitted_hours = sorted(a.paid_hours for a in emitted)
            assert emitted_hours == expected_hours

        # 3. Verify 0 hard unavailability violations (regular shifts and FIXED_SDE).
        for req in problem.availability_requests:
            if not req.approved or req.kind not in _HARD_UNAVAIL_KINDS:
                continue
            asgn_opt = regular_by_emp_date.get((req.employee_id, req.request_date))
            if req.shift_template_id is None:
                assert asgn_opt is None, (
                    f"Hard unavailability {req.kind} violated on {req.request_date}"
                )
                assert (req.employee_id, req.request_date) not in sde_by_emp_date, (
                    f"Hard unavailability {req.kind} violated by FIXED_SDE on {req.request_date}"
                )
            elif asgn_opt is not None:
                assert asgn_opt.shift_template_id != req.shift_template_id

        # 4. Verify 100% pinned cell adherence (including day-off pins vs FIXED_SDE).
        for pin in problem.pinned_cells:
            asgn_opt = regular_by_emp_date.get((pin.employee_id, pin.work_date))
            if pin.is_day_off:
                assert asgn_opt is None, f"Day-off pin violated on {pin.work_date}"
                assert (pin.employee_id, pin.work_date) not in sde_by_emp_date, (
                    f"Day-off pin violated by FIXED_SDE on {pin.work_date}"
                )
            else:
                assert asgn_opt is not None, f"Shift pin missing on {pin.work_date}"
                assert asgn_opt.shift_template_id == pin.shift_template_id
                assert asgn_opt.is_pinned is True
                assert asgn_opt.is_doublure == pin.is_doublure

        # 5. Verify same-day SDE/shift overlap, span, work, inter-day rest, and prior-month rest.
        for emp in problem.employees:
            day_intervals: dict[date, list[tuple[datetime, datetime]]] = {}
            for work_date in period_dates:
                ivs: list[tuple[datetime, datetime]] = []
                total_work_min = 0

                reg = regular_by_emp_date.get((emp.id, work_date))
                if reg is not None and reg.shift_template_id is not None:
                    shift = shift_by_id[reg.shift_template_id]
                    ivs.extend(segments_utc_intervals(work_date, shift.segments))
                    total_work_min += _expected_shift_paid_min(work_date, shift)

                for sde_req in approved_sdes_by_emp_date.get((emp.id, work_date), ()):
                    assert sde_req.custom_interval is not None
                    sde_iv = segment_utc_interval(work_date, sde_req.custom_interval)
                    ivs.append(sde_iv)
                    total_work_min += (sde_iv[1] - sde_iv[0]) // _ONE_MIN

                if not ivs:
                    continue

                ivs.sort(key=lambda iv: iv[0])
                for idx in range(len(ivs) - 1):
                    assert not intervals_overlap(ivs[idx], ivs[idx + 1]), (
                        f"Same-day overlap for {emp.display_label} on {work_date}"
                    )
                span_min = (ivs[-1][1] - ivs[0][0]) // _ONE_MIN
                assert span_min <= max_span_min, (
                    f"Daily span {span_min}m > {max_span_min}m on {work_date}"
                )
                assert total_work_min <= max_work_min, (
                    f"Daily work {total_work_min}m > {max_work_min}m on {work_date}"
                )
                day_intervals[work_date] = ivs

            # Adjacent days inside the period.
            for idx in range(len(period_dates) - 1):
                d_prev = period_dates[idx]
                d_next = period_dates[idx + 1]
                prev_ivs = day_intervals.get(d_prev)
                next_ivs = day_intervals.get(d_next)
                if not prev_ivs or not next_ivs:
                    continue

                rest_min = (next_ivs[0][0] - prev_ivs[-1][1]) // _ONE_MIN
                assert rest_min >= min_rest_min, (
                    f"Inter-day rest violation for {emp.display_label}: "
                    f"{d_prev}->{d_next} rest={rest_min}m < {min_rest_min}m"
                )

                reg_prev = regular_by_emp_date.get((emp.id, d_prev))
                reg_next = regular_by_emp_date.get((emp.id, d_next))
                if (
                    reg_prev is not None
                    and reg_next is not None
                    and reg_prev.shift_template_id is not None
                    and reg_next.shift_template_id is not None
                ):
                    exact_rest = rest_minutes_between(
                        d_prev,
                        shift_by_id[reg_prev.shift_template_id].segments,
                        d_next,
                        shift_by_id[reg_next.shift_template_id].segments,
                    )
                    assert exact_rest >= min_rest_min

            # Cross-month 1st-of-month rest continuity against prior_month_boundary.days.
            for rec in problem.prior_month_boundary.days:
                if rec.employee_id != emp.id or not rec.segments:
                    continue
                prior_end = segments_utc_intervals(rec.work_date, rec.segments)[-1][1]
                for work_date in period_dates[:2]:
                    reg = regular_by_emp_date.get((emp.id, work_date))
                    if reg is not None and reg.shift_template_id is not None:
                        exact_rest = rest_minutes_between(
                            rec.work_date,
                            rec.segments,
                            work_date,
                            shift_by_id[reg.shift_template_id].segments,
                        )
                        assert exact_rest >= min_rest_min, (
                            f"Cross-month rest violation: {rec.work_date}->{work_date} "
                            f"rest={exact_rest}m < {min_rest_min}m"
                        )
                    for sde_req in approved_sdes_by_emp_date.get((emp.id, work_date), ()):
                        assert sde_req.custom_interval is not None
                        sde_start = segment_utc_interval(work_date, sde_req.custom_interval)[0]
                        assert (sde_start - prior_end) // _ONE_MIN >= min_rest_min

            # 6. Consecutive working days streak (including trailing prior-month streak).
            streak = compute_trailing_work_streak(
                emp.id,
                period_dates[0],
                problem.prior_month_boundary,
            )
            for work_date in period_dates:
                worked = (emp.id, work_date) in regular_by_emp_date or (
                    emp.id,
                    work_date,
                ) in approved_sdes_by_emp_date
                streak = streak + 1 if worked else 0
                assert streak <= legal.max_consecutive_days, (
                    f"Consecutive work-day violation for {emp.display_label} on {work_date}: "
                    f"streak={streak} > {legal.max_consecutive_days}"
                )

        # 7. Exact daily coverage bounds & pouliste gaps.
        gap_map: dict[tuple[date, UUID], int] = {
            (g.work_date, g.shift_template_id): g.missing_headcount for g in solution.pouliste_gaps
        }
        cov_summary_map = {(c.work_date, c.shift_template_id): c for c in solution.daily_coverage}

        for work_date in period_dates:
            day_type = classify_day_type(work_date, public_holidays)
            for shift in problem.shift_templates:
                min_hc, target_hc = problem.coverage_matrix.resolve(shift.id, work_date, day_type)
                assigned_hc = assigned_count.get((work_date, shift.id), 0)
                gap_hc = gap_map.get((work_date, shift.id), 0)

                assert assigned_hc <= target_hc, (
                    f"Overstaffed {shift.erp_code} on {work_date}: {assigned_hc} > {target_hc}"
                )
                assert assigned_hc + gap_hc >= min_hc, (
                    f"Understaffed {shift.erp_code} on {work_date}: "
                    f"{assigned_hc} + {gap_hc} < {min_hc}"
                )
                assert gap_hc == max(0, min_hc - assigned_hc)
                if not problem.options.allow_pouliste:
                    assert gap_hc == 0

                if (work_date, shift.id) in cov_summary_map:
                    c_out = cov_summary_map[(work_date, shift.id)]
                    assert c_out.min_headcount == min_hc
                    assert c_out.target_headcount == target_hc
                    assert c_out.assigned_headcount == assigned_hc
                    assert c_out.pouliste_gaps == gap_hc

        assert solution.kpis.total_pouliste_gaps == sum(
            g.missing_headcount for g in solution.pouliste_gaps
        )

        # 8. Exact monthly target/scheduled/delta/ending-solde & hard |delta| <= corridor.
        summary_by_emp = {s.employee_id: s for s in solution.employee_summaries}
        assert len(summary_by_emp) == len(problem.employees)

        for emp in problem.employees:
            summary = summary_by_emp[emp.id]
            target_min = compute_monthly_target_minutes(
                emp,
                period_dates,
                public_holidays,
                approved_vacations[emp.id],
                problem.team.base_fulltime_weekly_h,
            )
            corridor_min = compute_employee_corridor_minutes(emp, problem.team.default_corridor_h)
            starting_solde_min = hours_to_minutes(emp.current_solde_h)

            scheduled_min = 0
            for work_date in period_dates:
                reg = regular_by_emp_date.get((emp.id, work_date))
                if reg is not None and reg.shift_template_id is not None:
                    scheduled_min += _expected_shift_paid_min(
                        work_date, shift_by_id[reg.shift_template_id]
                    )
                for sde_req in approved_sdes_by_emp_date.get((emp.id, work_date), ()):
                    assert sde_req.custom_interval is not None
                    sde_iv = segment_utc_interval(work_date, sde_req.custom_interval)
                    scheduled_min += (sde_iv[1] - sde_iv[0]) // _ONE_MIN

            delta_min = scheduled_min - target_min
            ending_solde_min = starting_solde_min + delta_min

            assert abs(delta_min) <= corridor_min, (
                f"Hard corridor violated for {emp.display_label}: |{delta_min}m| > {corridor_min}m"
            )
            assert summary.target_hours == minutes_to_hours(target_min)
            assert summary.scheduled_hours == minutes_to_hours(scheduled_min)
            assert summary.monthly_delta_h == minutes_to_hours(delta_min)
            assert summary.starting_solde_h == minutes_to_hours(starting_solde_min)
            assert summary.ending_solde_h == minutes_to_hours(ending_solde_min)
            assert summary.corridor_breached == (
                abs(delta_min) > corridor_min or abs(ending_solde_min) > corridor_min
            )


# ---------------------------------------------------------------------------
# Reusable test problem builders
# ---------------------------------------------------------------------------


def _make_standard_shifts() -> tuple[ShiftTemplate, ShiftTemplate, ShiftTemplate, ShiftTemplate]:
    """Return canonical Swiss care shifts: MC1 (split), M1 (day), S1 (evening), N (night)."""
    mc1 = ShiftTemplate(
        id=UUID("21000000-0000-4000-8000-000000000001"),
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
        id=UUID("21000000-0000-4000-8000-000000000002"),
        erp_code="M1",
        label="Matin 1",
        segments=(ShiftSegment(start_time=time(7, 0), end_time=time(15, 30)),),
        unpaid_break_min=30,
        paid_duration_h=Decimal("8.00"),
    )
    s1 = ShiftTemplate(
        id=UUID("21000000-0000-4000-8000-000000000003"),
        erp_code="S1",
        label="Soir 1",
        segments=(ShiftSegment(start_time=time(13, 30), end_time=time(22, 0)),),
        unpaid_break_min=30,
        paid_duration_h=Decimal("8.00"),
    )
    night = ShiftTemplate(
        id=UUID("21000000-0000-4000-8000-000000000004"),
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


def _make_team(
    *,
    canton: SwissCanton = SwissCanton.VD,
    weekly_h: Decimal = Decimal("42.00"),
    corridor_h: Decimal = Decimal("10.00"),
) -> TeamContext:
    return TeamContext(
        team_id=UUID("11000000-0000-4000-8000-000000000001"),
        name="Unite Test",
        canton_code=canton,
        base_fulltime_weekly_h=weekly_h,
        default_corridor_h=corridor_h,
        locale=Locale.FR_CH,
    )


def _make_employees(
    count: int,
    *,
    pensums: tuple[Decimal, ...] | None = None,
    corridor_h: Decimal | None = None,
    qualified_shift_ids: tuple[UUID, ...] = (),
    role_tags: tuple[str, ...] = ("soins",),
) -> tuple[EmployeeProfile, ...]:
    emps: list[EmployeeProfile] = []
    for idx in range(count):
        pensum = pensums[idx % len(pensums)] if pensums else Decimal("100.00")
        emps.append(
            EmployeeProfile(
                id=UUID(f"31000000-0000-4000-8000-{idx + 1:012d}"),
                display_label=f"Soignant {idx + 1}",
                erp_employee_code=f"E{idx + 1:03d}",
                pensum_pct=pensum,
                corridor_h=corridor_h,
                qualified_shift_ids=qualified_shift_ids,
                role_tags=role_tags,
            )
        )
    return tuple(emps)


def _uniform_coverage(
    shift_specs: tuple[tuple[UUID, int, int], ...],
) -> CoverageMatrix:
    rules: list[CoverageRule] = []
    for shift_id, min_hc, target_hc in shift_specs:
        for dt in (DayType.WEEKDAY, DayType.SATURDAY, DayType.SUNDAY, DayType.HOLIDAY):
            rules.append(
                CoverageRule(
                    shift_template_id=shift_id,
                    day_type=dt,
                    min_headcount=min_hc,
                    target_headcount=target_hc,
                )
            )
    return CoverageMatrix(rules=tuple(rules))


def _make_problem(
    *,
    year_month: str = "2026-03",
    team: TeamContext | None = None,
    legal_rules: LegalRuleSet | None = None,
    shift_templates: tuple[ShiftTemplate, ...],
    coverage_matrix: CoverageMatrix,
    employees: tuple[EmployeeProfile, ...],
    availability_requests: tuple[AvailabilityRequest, ...] = (),
    pinned_cells: tuple[PinnedCell, ...] = (),
    prior_month_boundary: PriorMonthBoundary | None = None,
    public_holidays: tuple[date, ...] = (),
    allow_pouliste: bool = False,
    random_seed: int = 42,
    timeout_sec: int = 10,
) -> SolverInput:
    return SolverInput(
        period_id=UUID("11000000-0000-4000-8000-000000000099"),
        year_month=year_month,
        team=team if team is not None else _make_team(),
        legal_rules=legal_rules
        if legal_rules is not None
        else build_preset(LegalPresetType.LTR_45),
        shift_templates=shift_templates,
        coverage_matrix=coverage_matrix,
        employees=employees,
        availability_requests=availability_requests,
        pinned_cells=pinned_cells,
        prior_month_boundary=(
            prior_month_boundary if prior_month_boundary is not None else PriorMonthBoundary()
        ),
        public_holidays=public_holidays,
        options=SolverOptions(
            timeout_sec=timeout_sec,
            allow_pouliste=allow_pouliste,
            random_seed=random_seed,
            num_search_workers=1,
            locale=Locale.FR_CH,
        ),
    )


# ---------------------------------------------------------------------------
# 1. Discrete shifts, split shifts (MC1), overnight (N), and FIXED_SDE
# ---------------------------------------------------------------------------


def test_discrete_split_overnight_and_fixed_sde() -> None:
    """Feasible solve handles MC1, M1, S1, N and counts approved FIXED_SDE outside coverage."""
    mc1, m1, s1, night = _make_standard_shifts()
    # 6 employees at 100% FTE (March 2026: 22 wkdays * 8.4h = 184.8h each -> 1108.8h capacity).
    # Daily coverage: 1 MC1 (7h) + 1 M1 (8h) + 1 S1 (8h) + 1 N (8h) = 31h/day * 31 = 961h,
    # target up to 1 extra M1 on weekdays (+176h -> 1137h), easily balanced in ±10h corridor!
    employees = _make_employees(6)
    rules: list[CoverageRule] = []
    for dt in (DayType.WEEKDAY, DayType.SATURDAY, DayType.SUNDAY, DayType.HOLIDAY):
        rules.append(
            CoverageRule(shift_template_id=mc1.id, day_type=dt, min_headcount=1, target_headcount=1)
        )
        rules.append(
            CoverageRule(
                shift_template_id=m1.id,
                day_type=dt,
                min_headcount=1,
                target_headcount=2 if dt == DayType.WEEKDAY else 1,
            )
        )
        rules.append(
            CoverageRule(shift_template_id=s1.id, day_type=dt, min_headcount=1, target_headcount=1)
        )
        rules.append(
            CoverageRule(
                shift_template_id=night.id, day_type=dt, min_headcount=1, target_headcount=1
            )
        )

    sde_date = date(2026, 3, 12)
    sde_req = AvailabilityRequest(
        id=uuid4(),
        employee_id=employees[0].id,
        request_date=sde_date,
        kind=RequestKind.FIXED_SDE,
        custom_interval=ShiftSegment(start_time=time(10, 0), end_time=time(12, 0)),
        sde_label="SDE/10/12",
        source=RequestSource.MANAGER,
        approved=True,
    )
    unapproved_sde = AvailabilityRequest(
        id=uuid4(),
        employee_id=employees[1].id,
        request_date=date(2026, 3, 13),
        kind=RequestKind.FIXED_SDE,
        custom_interval=ShiftSegment(start_time=time(10, 0), end_time=time(12, 0)),
        sde_label="SDE/IGNORED",
        source=RequestSource.EMPLOYEE_PORTAL,
        approved=False,
    )

    problem = _make_problem(
        legal_rules=build_preset(LegalPresetType.OLT2_CARE),
        shift_templates=(mc1, m1, s1, night),
        coverage_matrix=CoverageMatrix(rules=tuple(rules)),
        employees=employees,
        availability_requests=(sde_req, unapproved_sde),
        allow_pouliste=False,
    )

    output = solve_schedule(problem)
    _assert_valid_solution(problem, output)

    sol = output.solutions[0]
    sde_asgns = [a for a in sol.assignments if a.is_sde]
    assert len(sde_asgns) == 1
    assert sde_asgns[0].employee_id == employees[0].id
    assert sde_asgns[0].work_date == sde_date
    assert sde_asgns[0].cell_code == "SDE/10/12"
    assert sde_asgns[0].paid_hours == Decimal("2.00")

    # On sde_date, regular coverage for MC1, M1, S1, N must STILL be met by non-SDE shifts.
    regular_on_sde_date = [a for a in sol.assignments if not a.is_sde and a.work_date == sde_date]
    covered_shift_ids = {a.shift_template_id for a in regular_on_sde_date}
    assert {mc1.id, m1.id, s1.id, night.id} <= covered_shift_ids

    # Night shifts generate positive night_supplement_hours (23:00-06:00 -> 7h * 10% = 42m).
    night_asgns = [a for a in sol.assignments if a.shift_template_id == night.id]
    assert len(night_asgns) == 31
    assert sol.kpis.total_night_supplement_hours > Decimal("0.00")


# ---------------------------------------------------------------------------
# 2. Coverage matrix, date overrides, and pouliste gap vs infeasible (FR-009)
# ---------------------------------------------------------------------------


def test_coverage_matrix_day_types_and_override_precedence() -> None:
    """Weekday, Saturday, Sunday, holiday, and override_date rules resolve in strict precedence."""
    _, m1, _, _ = _make_standard_shifts()
    # 4 employees at 60% FTE (110.88h target) with generous ±25h corridor so coverage drives counts.
    employees = _make_employees(4, pensums=(Decimal("60.00"),), corridor_h=Decimal("25.00"))
    holiday_date = date(2026, 3, 19)  # Thursday
    override_date = date(2026, 3, 22)  # Sunday overridden to 3 staff

    coverage = CoverageMatrix(
        rules=(
            CoverageRule(
                shift_template_id=m1.id,
                day_type=DayType.WEEKDAY,
                min_headcount=2,
                target_headcount=2,
            ),
            CoverageRule(
                shift_template_id=m1.id,
                day_type=DayType.SATURDAY,
                min_headcount=1,
                target_headcount=1,
            ),
            CoverageRule(
                shift_template_id=m1.id,
                day_type=DayType.SUNDAY,
                min_headcount=1,
                target_headcount=1,
            ),
            CoverageRule(
                shift_template_id=m1.id,
                day_type=DayType.HOLIDAY,
                min_headcount=0,
                target_headcount=0,
            ),
            CoverageRule(
                shift_template_id=m1.id,
                override_date=override_date,
                min_headcount=3,
                target_headcount=3,
            ),
        )
    )

    problem = _make_problem(
        shift_templates=(m1,),
        coverage_matrix=coverage,
        employees=employees,
        public_holidays=(holiday_date,),
        allow_pouliste=False,
    )

    output = solve_schedule(problem)
    _assert_valid_solution(problem, output)

    sol = output.solutions[0]
    counts_by_date: dict[date, int] = {}
    for asgn in sol.assignments:
        if not asgn.is_sde:
            counts_by_date[asgn.work_date] = counts_by_date.get(asgn.work_date, 0) + 1

    assert counts_by_date.get(date(2026, 3, 2), 0) == 2  # Regular Monday
    assert counts_by_date.get(date(2026, 3, 7), 0) == 1  # Saturday
    assert counts_by_date.get(date(2026, 3, 8), 0) == 1  # Regular Sunday
    assert counts_by_date.get(holiday_date, 0) == 0  # Holiday beats weekday
    assert counts_by_date.get(override_date, 0) == 3  # Date override beats Sunday


def test_coverage_pouliste_enabled_vs_disabled_infeasible() -> None:
    """Understaffed day yields minimized trilingual PoulisteGapOut or INFEASIBLE ConflictCard."""
    _, m1, _, _ = _make_standard_shifts()
    # 2 employees, but 2026-03-10 requires min 3 staff on M1 -> guaranteed gap of 1.
    employees = _make_employees(2, pensums=(Decimal("60.00"),), corridor_h=Decimal("40.00"))
    spike_date = date(2026, 3, 10)
    coverage = CoverageMatrix(
        rules=(
            CoverageRule(
                shift_template_id=m1.id,
                day_type=DayType.WEEKDAY,
                min_headcount=1,
                target_headcount=1,
            ),
            CoverageRule(
                shift_template_id=m1.id,
                day_type=DayType.SATURDAY,
                min_headcount=1,
                target_headcount=1,
            ),
            CoverageRule(
                shift_template_id=m1.id,
                day_type=DayType.SUNDAY,
                min_headcount=1,
                target_headcount=1,
            ),
            CoverageRule(
                shift_template_id=m1.id,
                override_date=spike_date,
                min_headcount=3,
                target_headcount=3,
            ),
        )
    )

    problem_pouliste = _make_problem(
        shift_templates=(m1,),
        coverage_matrix=coverage,
        employees=employees,
        allow_pouliste=True,
    )
    out_pouliste = solve_schedule(problem_pouliste)
    _assert_valid_solution(problem_pouliste, out_pouliste)

    sol = out_pouliste.solutions[0]
    assert sol.kpis.total_pouliste_gaps == 1
    assert len(sol.pouliste_gaps) == 1
    gap = sol.pouliste_gaps[0]
    assert gap.work_date == spike_date
    assert gap.shift_template_id == m1.id
    assert gap.missing_headcount == 1
    assert gap.reason is not None
    assert gap.reason.fr_CH and gap.reason.de_CH and gap.reason.en

    problem_strict = problem_pouliste.model_copy(
        update={
            "options": problem_pouliste.options.model_copy(update={"allow_pouliste": False}),
        }
    )
    out_strict = solve_schedule(problem_strict)
    assert out_strict.status == SolverStatus.INFEASIBLE
    assert not out_strict.solutions
    assert len(out_strict.conflict_cards) >= 1
    card = out_strict.conflict_cards[0]
    assert card.title.fr_CH and card.title.de_CH and card.title.en
    assert card.explanation.fr_CH and card.explanation.de_CH and card.explanation.en
    assert any(h.action_code == "ENABLE_POULISTE" for h in card.resolution_hints)


# ---------------------------------------------------------------------------
# 3. Qualifications & role tags
# ---------------------------------------------------------------------------


def test_qualifications_and_required_role_tags_enforced() -> None:
    """Restricted shifts are assigned exclusively to qualified staff holding required_role_tag."""
    _, m1, _, _ = _make_standard_shifts()
    nurse_shift = ShiftTemplate(
        id=UUID("22000000-0000-4000-8000-000000000001"),
        erp_code="INF",
        label="Infirmier",
        segments=(ShiftSegment(start_time=time(7, 0), end_time=time(15, 30)),),
        unpaid_break_min=30,
        paid_duration_h=Decimal("8.00"),
        required_role_tag="infirmier",
    )

    nurse_a = EmployeeProfile(
        id=UUID("32000000-0000-4000-8000-000000000001"),
        display_label="Infirmier A",
        pensum_pct=Decimal("65.00"),
        corridor_h=Decimal("20.00"),
        qualified_shift_ids=(nurse_shift.id, m1.id),
        role_tags=("soins", "infirmier"),
    )
    nurse_b = EmployeeProfile(
        id=UUID("32000000-0000-4000-8000-000000000002"),
        display_label="Infirmier B",
        pensum_pct=Decimal("65.00"),
        corridor_h=Decimal("20.00"),
        qualified_shift_ids=(nurse_shift.id, m1.id),
        role_tags=("soins", "infirmier"),
    )
    # Holds role tag "infirmier" but NOT qualified for nurse_shift.id.
    unqualified_tag = EmployeeProfile(
        id=UUID("32000000-0000-4000-8000-000000000003"),
        display_label="No Qual",
        pensum_pct=Decimal("65.00"),
        corridor_h=Decimal("20.00"),
        qualified_shift_ids=(m1.id,),
        role_tags=("soins", "infirmier"),
    )
    # Qualified for all shifts (empty tuple) but missing required_role_tag "infirmier".
    missing_tag = EmployeeProfile(
        id=UUID("32000000-0000-4000-8000-000000000004"),
        display_label="No Tag",
        pensum_pct=Decimal("65.00"),
        corridor_h=Decimal("20.00"),
        qualified_shift_ids=(),
        role_tags=("soins",),
    )

    coverage = _uniform_coverage(((nurse_shift.id, 1, 1), (m1.id, 1, 1)))
    problem = _make_problem(
        shift_templates=(nurse_shift, m1),
        coverage_matrix=coverage,
        employees=(nurse_a, nurse_b, unqualified_tag, missing_tag),
        allow_pouliste=False,
    )
    output = solve_schedule(problem)
    _assert_valid_solution(problem, output)

    sol = output.solutions[0]
    inf_assignees = {
        a.employee_id for a in sol.assignments if a.shift_template_id == nurse_shift.id
    }
    assert inf_assignees <= {nurse_a.id, nurse_b.id}
    assert unqualified_tag.id not in inf_assignees
    assert missing_tag.id not in inf_assignees


# ---------------------------------------------------------------------------
# 4. Pinned cells & pin collision infeasibility (FR-029)
# ---------------------------------------------------------------------------


def test_pinned_cells_respected_and_conflicting_pins_infeasible() -> None:
    """Valid shift/day-off pins are adhered to; pins colliding with hard rules are INFEASIBLE."""
    _, m1, _, night = _make_standard_shifts()
    employees = _make_employees(3, pensums=(Decimal("80.00"),), corridor_h=Decimal("20.00"))
    coverage = _uniform_coverage(((m1.id, 1, 2),))

    base_problem = _make_problem(
        shift_templates=(m1, night),
        coverage_matrix=coverage,
        employees=employees,
        pinned_cells=(
            PinnedCell(
                employee_id=employees[0].id,
                work_date=date(2026, 3, 5),
                shift_template_id=m1.id,
                is_day_off=False,
            ),
            PinnedCell(
                employee_id=employees[1].id,
                work_date=date(2026, 3, 5),
                is_day_off=True,
            ),
        ),
        allow_pouliste=False,
    )
    output = solve_schedule(base_problem)
    _assert_valid_solution(base_problem, output)

    # Collision 1: Shift pin on a day with approved VACATION_V -> INFEASIBLE.
    vac_collision = base_problem.model_copy(
        update={
            "availability_requests": (
                AvailabilityRequest(
                    id=uuid4(),
                    employee_id=employees[0].id,
                    request_date=date(2026, 3, 5),
                    kind=RequestKind.VACATION_V,
                    approved=True,
                ),
            )
        }
    )
    assert solve_schedule(vac_collision).status == SolverStatus.INFEASIBLE

    # Collision 2: Mar 1 morning pin colliding with Feb 28 night shift rest -> INFEASIBLE.
    rest_collision = base_problem.model_copy(
        update={
            "pinned_cells": (
                PinnedCell(
                    employee_id=employees[0].id,
                    work_date=date(2026, 3, 1),
                    shift_template_id=m1.id,
                ),
            ),
            "prior_month_boundary": PriorMonthBoundary(
                days=(
                    PriorDayRecord(
                        employee_id=employees[0].id,
                        work_date=date(2026, 2, 28),
                        shift_template_id=night.id,
                        segments=night.segments,
                        paid_hours=Decimal("8.00"),
                    ),
                )
            ),
        }
    )
    assert solve_schedule(rest_collision).status == SolverStatus.INFEASIBLE

    # Collision 3: Shift pin on night shift whose coverage target_headcount == 0 -> INFEASIBLE.
    zero_target_collision = base_problem.model_copy(
        update={
            "pinned_cells": (
                PinnedCell(
                    employee_id=employees[0].id,
                    work_date=date(2026, 3, 6),
                    shift_template_id=night.id,
                ),
            )
        }
    )
    assert solve_schedule(zero_target_collision).status == SolverStatus.INFEASIBLE


# ---------------------------------------------------------------------------
# 5. Pensum target, vacation/holiday adjustments, ±corridor & carry-over solde
# ---------------------------------------------------------------------------


def test_vacation_and_holiday_target_reduction_and_tight_corridor_infeasible() -> None:
    """Weekday vacations/holidays reduce target_hours; impossible tight corridor is INFEASIBLE."""
    _, m1, _, _ = _make_standard_shifts()
    employees = _make_employees(3, pensums=(Decimal("100.00"),), corridor_h=Decimal("20.00"))
    # Give enough target capacity (up to 3/day) so employees can hit their monthly targets.
    coverage = _uniform_coverage(((m1.id, 1, 3),))

    # 1 weekday cantonal holiday (2026-03-19) + 2 weekday vacations for emp 0 (2026-03-09, 10)
    # Plus 1 weekend vacation (2026-03-14 Saturday) which must NOT reduce target.
    vac_reqs = (
        AvailabilityRequest(
            id=uuid4(),
            employee_id=employees[0].id,
            request_date=date(2026, 3, 9),
            kind=RequestKind.VACATION_V,
            approved=True,
        ),
        AvailabilityRequest(
            id=uuid4(),
            employee_id=employees[0].id,
            request_date=date(2026, 3, 10),
            kind=RequestKind.VACATION_V,
            approved=True,
        ),
        AvailabilityRequest(
            id=uuid4(),
            employee_id=employees[0].id,
            request_date=date(2026, 3, 14),  # Saturday
            kind=RequestKind.VACATION_V,
            approved=True,
        ),
    )

    problem = _make_problem(
        shift_templates=(m1,),
        coverage_matrix=coverage,
        employees=employees,
        availability_requests=vac_reqs,
        public_holidays=(date(2026, 3, 19),),
        allow_pouliste=False,
    )
    output = solve_schedule(problem)
    _assert_valid_solution(problem, output)

    summaries = {s.employee_id: s for s in output.solutions[0].employee_summaries}
    # March 2026: 22 weekdays - 1 holiday = 21 weekdays -> 21 * 8.4h = 176.40h
    assert summaries[employees[1].id].target_hours == Decimal("176.40")
    # Emp 0: 21 - 2 weekday vacations = 19 weekdays -> 19 * 8.4h = 159.60h
    assert summaries[employees[0].id].target_hours == Decimal("159.60")

    # Tight ±0.00h corridor is impossible because 8.00h shifts cannot sum to 176.40h.
    impossible_corridor = _make_problem(
        team=_make_team(corridor_h=Decimal("0.00")),
        shift_templates=(m1,),
        coverage_matrix=coverage,
        employees=_make_employees(3, pensums=(Decimal("100.00"),), corridor_h=Decimal("0.00")),
        public_holidays=(date(2026, 3, 19),),
        allow_pouliste=False,
    )
    assert solve_schedule(impossible_corridor).status == SolverStatus.INFEASIBLE


def test_carry_over_solde_rebalancing() -> None:
    """Employee at -8.00h works above target while +8.00h colleague works below target."""
    _, m1, _, _ = _make_standard_shifts()
    # April 2026 has 22 weekdays; at 40h/wk (8.00h/day), 80% FTE = 140.80h -> use 50% FTE:
    # 22 * 8.0 * 0.5 = 88.00h exact (11 shifts of 8h each!).
    # Two employees -> total target = 176.00h = 22 shifts; 30 days with 0..2 shifts/day and
    # min 1 shift on 22 days gives exact freedom to shift 1 shift (+8h / -8h) cleanly!
    emp_deficit = EmployeeProfile(
        id=UUID("33000000-0000-4000-8000-000000000001"),
        display_label="Deficit -8h",
        pensum_pct=Decimal("50.00"),
        base_fulltime_weekly_h=Decimal("40.00"),
        corridor_h=Decimal("10.00"),
        current_solde_h=Decimal("-8.00"),
    )
    emp_surplus = EmployeeProfile(
        id=UUID("33000000-0000-4000-8000-000000000002"),
        display_label="Surplus +8h",
        pensum_pct=Decimal("50.00"),
        base_fulltime_weekly_h=Decimal("40.00"),
        corridor_h=Decimal("10.00"),
        current_solde_h=Decimal("8.00"),
    )
    # 22 weekdays * 1 shift = 22 shifts total (min=1, target=1 on weekdays; 0 on weekends).
    coverage = CoverageMatrix(
        rules=(
            CoverageRule(
                shift_template_id=m1.id,
                day_type=DayType.WEEKDAY,
                min_headcount=1,
                target_headcount=1,
            ),
        )
    )
    problem = _make_problem(
        year_month="2026-04",
        team=_make_team(weekly_h=Decimal("40.00"), corridor_h=Decimal("10.00")),
        shift_templates=(m1,),
        coverage_matrix=coverage,
        employees=(emp_deficit, emp_surplus),
        allow_pouliste=False,
    )
    output = solve_schedule(problem)
    _assert_valid_solution(problem, output)

    summaries = {s.employee_id: s for s in output.solutions[0].employee_summaries}
    s_def = summaries[emp_deficit.id]
    s_sur = summaries[emp_surplus.id]

    assert s_def.monthly_delta_h > Decimal("0.00")
    assert s_sur.monthly_delta_h < Decimal("0.00")
    assert abs(s_def.ending_solde_h) < abs(s_def.starting_solde_h)
    assert abs(s_sur.ending_solde_h) < abs(s_sur.starting_solde_h)
    assert s_def.ending_solde_h == Decimal("0.00")
    assert s_sur.ending_solde_h == Decimal("0.00")


# ---------------------------------------------------------------------------
# 6. Cross-month 7-day boundary continuity (FR-028)
# ---------------------------------------------------------------------------


def test_cross_month_boundary_rest_and_trailing_streaks() -> None:
    """Prior-month night shift blocks Mar 1 morning; trailing streaks of 5 & 6 enforce rest."""
    _, m1, _, night = _make_standard_shifts()
    ltr = build_preset(LegalPresetType.LTR_45)  # max_consecutive_days == 6, min_daily_rest == 11h
    employees = _make_employees(3, pensums=(Decimal("60.00"),), corridor_h=Decimal("25.00"))
    coverage = _uniform_coverage(((m1.id, 1, 2),))

    # Case A: emp 0 worked Feb 28 night (22:00-06:00) -> cannot work Mar 1 M1 (07:00-15:30).
    # Case B: emp 1 has trailing streak of 5 -> cannot work BOTH Mar 1 and Mar 2.
    # Case C: emp 2 has trailing streak of 6 -> MUST be off on Mar 1.
    # To stress Case B, pin emp 1 on Mar 1 so emp 1 MUST be off on Mar 2.
    boundary = PriorMonthBoundary(
        days=(
            PriorDayRecord(
                employee_id=employees[0].id,
                work_date=date(2026, 2, 28),
                shift_template_id=night.id,
                segments=night.segments,
                paid_hours=Decimal("8.00"),
            ),
            # 5 consecutive days ending Feb 28 for emp 1 (Feb 24..28)
            *(
                PriorDayRecord(
                    employee_id=employees[1].id,
                    work_date=date(2026, 2, day),
                    shift_template_id=m1.id,
                    segments=m1.segments,
                    paid_hours=Decimal("8.00"),
                )
                for day in range(24, 29)
            ),
            # 6 consecutive days ending Feb 28 for emp 2 (Feb 23..28)
            *(
                PriorDayRecord(
                    employee_id=employees[2].id,
                    work_date=date(2026, 2, day),
                    shift_template_id=m1.id,
                    segments=m1.segments,
                    paid_hours=Decimal("8.00"),
                )
                for day in range(23, 29)
            ),
        )
    )

    problem = _make_problem(
        legal_rules=ltr,
        shift_templates=(m1, night),
        coverage_matrix=coverage,
        employees=employees,
        prior_month_boundary=boundary,
        pinned_cells=(
            PinnedCell(
                employee_id=employees[1].id,
                work_date=date(2026, 3, 1),
                shift_template_id=m1.id,
            ),
        ),
        allow_pouliste=False,
    )
    output = solve_schedule(problem)
    _assert_valid_solution(problem, output)

    worked_pairs = {(a.employee_id, a.work_date) for a in output.solutions[0].assignments}
    assert (employees[0].id, date(2026, 3, 1)) not in worked_pairs  # Night -> M1 blocked
    assert (employees[1].id, date(2026, 3, 1)) in worked_pairs  # Pinned day 6 of streak
    assert (employees[1].id, date(2026, 3, 2)) not in worked_pairs  # Must rest after 6-day streak
    assert (employees[2].id, date(2026, 3, 1)) not in worked_pairs  # Trailing 6 forces Mar 1 off

    # Pinning emp 2 (trailing streak == 6) on Mar 1 must be INFEASIBLE.
    infeasible_streak_pin = problem.model_copy(
        update={
            "pinned_cells": (
                PinnedCell(
                    employee_id=employees[2].id,
                    work_date=date(2026, 3, 1),
                    shift_template_id=m1.id,
                ),
            )
        }
    )
    assert solve_schedule(infeasible_streak_pin).status == SolverStatus.INFEASIBLE


# ---------------------------------------------------------------------------
# 7. DST spring-forward & fall-back integration (NFR-024)
# ---------------------------------------------------------------------------


@pytest.mark.dst
def test_dst_spring_forward_rest_forbidden_and_night_paid_7h() -> None:
    """Spring-forward (2026-03-28 -> 29): 21:00->07:00 (9h UTC) forbidden under LTr; night = 7h."""
    ltr = build_preset(LegalPresetType.LTR_45)  # 11h min rest
    morning = ShiftTemplate(
        id=UUID("24000000-0000-4000-8000-000000000001"),
        erp_code="MAT",
        label="Matin 07-15",
        segments=(ShiftSegment(start_time=time(7, 0), end_time=time(15, 0)),),
        unpaid_break_min=30,
        paid_duration_h=None,
    )
    evening = ShiftTemplate(
        id=UUID("24000000-0000-4000-8000-000000000002"),
        erp_code="SOIR",
        label="Soir 13-21",
        segments=(ShiftSegment(start_time=time(13, 0), end_time=time(21, 0)),),
        unpaid_break_min=30,
        paid_duration_h=None,
    )
    night_dynamic = ShiftTemplate(
        id=UUID("24000000-0000-4000-8000-000000000003"),
        erp_code="NDST",
        label="Nuit DST",
        segments=(
            ShiftSegment(start_time=time(22, 0), end_time=time(6, 0), crosses_midnight=True),
        ),
        unpaid_break_min=0,
        paid_on_post_break=True,
        paid_duration_h=None,  # Dynamic exact UTC elapsed duration!
        is_night_shift=True,
    )

    employees = _make_employees(5, pensums=(Decimal("80.00"),), corridor_h=Decimal("25.00"))
    coverage = _uniform_coverage(
        (
            (morning.id, 1, 1),
            (evening.id, 1, 1),
            (night_dynamic.id, 1, 1),
        )
    )

    # First verify: pinning evening on 2026-03-28 + morning on 2026-03-29 for same employee
    # is INFEASIBLE under LTr (actual UTC rest is 9h = 540 min < 11h = 660 min).
    infeasible_dst_rest = _make_problem(
        year_month="2026-03",
        legal_rules=ltr,
        shift_templates=(morning, evening, night_dynamic),
        coverage_matrix=coverage,
        employees=employees,
        pinned_cells=(
            PinnedCell(
                employee_id=employees[0].id,
                work_date=date(2026, 3, 28),
                shift_template_id=evening.id,
            ),
            PinnedCell(
                employee_id=employees[0].id,
                work_date=date(2026, 3, 29),
                shift_template_id=morning.id,
            ),
        ),
        allow_pouliste=False,
    )
    assert solve_schedule(infeasible_dst_rest).status == SolverStatus.INFEASIBLE

    # Now solve without the forbidden pair and verify 2026-03-28 night shift pays exactly 7.00h.
    feasible_spring = infeasible_dst_rest.model_copy(update={"pinned_cells": ()})
    output = solve_schedule(feasible_spring)
    _assert_valid_solution(feasible_spring, output)

    sol = output.solutions[0]
    spring_night = [
        a
        for a in sol.assignments
        if a.work_date == date(2026, 3, 28) and a.shift_template_id == night_dynamic.id
    ]
    normal_night = [
        a
        for a in sol.assignments
        if a.work_date == date(2026, 3, 27) and a.shift_template_id == night_dynamic.id
    ]
    assert len(spring_night) == 1
    assert len(normal_night) == 1
    assert spring_night[0].paid_hours == Decimal("7.00")
    assert normal_night[0].paid_hours == Decimal("8.00")


@pytest.mark.dst
def test_dst_fall_back_night_paid_9h() -> None:
    """Fall-back (2026-10-24 -> 25): 22:00-06:00 night with paid_duration_h=None pays 9.00h."""
    night_dynamic = ShiftTemplate(
        id=UUID("24000000-0000-4000-8000-000000000004"),
        erp_code="NDST",
        label="Nuit DST Automne",
        segments=(
            ShiftSegment(start_time=time(22, 0), end_time=time(6, 0), crosses_midnight=True),
        ),
        unpaid_break_min=0,
        paid_on_post_break=True,
        paid_duration_h=None,
        is_night_shift=True,
    )
    employees = _make_employees(2, pensums=(Decimal("65.00"),), corridor_h=Decimal("25.00"))
    coverage = _uniform_coverage(((night_dynamic.id, 1, 1),))

    problem = _make_problem(
        year_month="2026-10",
        legal_rules=build_preset(LegalPresetType.LTR_45),
        shift_templates=(night_dynamic,),
        coverage_matrix=coverage,
        employees=employees,
        allow_pouliste=False,
    )
    output = solve_schedule(problem)
    _assert_valid_solution(problem, output)

    sol = output.solutions[0]
    fallback_night = [
        a
        for a in sol.assignments
        if a.work_date == date(2026, 10, 24) and a.shift_template_id == night_dynamic.id
    ]
    normal_night = [
        a
        for a in sol.assignments
        if a.work_date == date(2026, 10, 23) and a.shift_template_id == night_dynamic.id
    ]
    assert len(fallback_night) == 1
    assert len(normal_night) == 1
    assert fallback_night[0].paid_hours == Decimal("9.00")
    assert normal_night[0].paid_hours == Decimal("8.00")


# ---------------------------------------------------------------------------
# 8. Determinism, break warnings & same-day SDE conflict (NFR-019, NFR-002)
# ---------------------------------------------------------------------------


def test_determinism_identical_json_across_repeated_solves() -> None:
    """Repeated solves with identical random_seed yield byte-for-byte identical JSON outputs."""
    mc1, m1, s1, night = _make_standard_shifts()
    employees = _make_employees(
        6,
        pensums=(
            Decimal("100.00"),
            Decimal("100.00"),
            Decimal("80.00"),
            Decimal("80.00"),
            Decimal("80.00"),
            Decimal("80.00"),
        ),
    )
    coverage = _uniform_coverage(((mc1.id, 1, 1), (m1.id, 1, 1), (s1.id, 1, 1), (night.id, 1, 1)))
    problem = _make_problem(
        legal_rules=build_preset(LegalPresetType.OLT2_CARE),
        shift_templates=(mc1, m1, s1, night),
        coverage_matrix=coverage,
        employees=employees,
        random_seed=202603,
        allow_pouliste=False,
    )

    out1 = solve_schedule(problem)
    out2 = solve_schedule(problem)
    _assert_valid_solution(problem, out1)
    _assert_valid_solution(problem, out2)

    json1 = out1.model_copy(update={"solve_duration_ms": 0}).model_dump_json()
    json2 = out2.model_copy(update={"solve_duration_ms": 0}).model_dump_json()
    assert json1 == json2


def test_break_warnings_populated_for_non_compliant_shift() -> None:
    """Art. 15 LTr break warnings are surfaced on SolverOutput for non-compliant templates."""
    non_compliant = ShiftTemplate(
        id=UUID("25000000-0000-4000-8000-000000000001"),
        erp_code="LONG",
        label="Long sans pause",
        segments=(ShiftSegment(start_time=time(7, 0), end_time=time(17, 0)),),
        unpaid_break_min=0,  # 10h > 9h requires 60 min break!
        paid_on_post_break=False,
        paid_duration_h=Decimal("10.00"),
    )
    employees = _make_employees(2, pensums=(Decimal("80.00"),), corridor_h=Decimal("25.00"))
    coverage = _uniform_coverage(((non_compliant.id, 1, 1),))
    problem = _make_problem(
        shift_templates=(non_compliant,),
        coverage_matrix=coverage,
        employees=employees,
        allow_pouliste=False,
    )
    output = solve_schedule(problem)
    _assert_valid_solution(problem, output)

    assert len(output.break_warnings) == 1
    warning = output.break_warnings[0]
    assert warning.shift_template_id == non_compliant.id
    assert warning.code == "LTR_BREAK_60M"
    assert warning.required_break_min == 60
    assert warning.configured_break_min == 0


def test_overlapping_same_day_fixed_sde_returns_infeasible() -> None:
    """Two overlapping approved FIXED_SDE requests on the same day return INFEASIBLE."""
    _, m1, _, _ = _make_standard_shifts()
    employees = _make_employees(2, pensums=(Decimal("60.00"),), corridor_h=Decimal("25.00"))
    coverage = _uniform_coverage(((m1.id, 1, 1),))

    overlap_sdes = (
        AvailabilityRequest(
            id=uuid4(),
            employee_id=employees[0].id,
            request_date=date(2026, 3, 12),
            kind=RequestKind.FIXED_SDE,
            custom_interval=ShiftSegment(start_time=time(9, 0), end_time=time(11, 0)),
            sde_label="SDE/09/11",
            approved=True,
        ),
        AvailabilityRequest(
            id=uuid4(),
            employee_id=employees[0].id,
            request_date=date(2026, 3, 12),
            kind=RequestKind.FIXED_SDE,
            custom_interval=ShiftSegment(start_time=time(10, 30), end_time=time(12, 0)),
            sde_label="SDE/1030/12",
            approved=True,
        ),
    )

    problem = _make_problem(
        shift_templates=(m1,),
        coverage_matrix=coverage,
        employees=employees,
        availability_requests=overlap_sdes,
        allow_pouliste=True,
    )
    output = solve_schedule(problem)
    assert output.status == SolverStatus.INFEASIBLE
    assert len(output.conflict_cards) >= 1


def test_olt2_enforces_11h_rest_conservatively_until_rolling_average_modeled() -> None:
    """OLT2_CARE enforces 11h daily rest conservatively when 14d rolling average is configured."""
    evening = ShiftTemplate(
        id=uuid4(),
        erp_code="EVE",
        label="Evening 14:00-21:00",
        segments=(ShiftSegment(start_time=time(14, 0), end_time=time(21, 0)),),
        paid_duration_h=Decimal("7.00"),
    )
    morning = ShiftTemplate(
        id=uuid4(),
        erp_code="MORN",
        label="Morning 07:00-14:00",
        segments=(ShiftSegment(start_time=time(7, 0), end_time=time(14, 0)),),
        paid_duration_h=Decimal("7.00"),
    )
    employees = _make_employees(1, pensums=(Decimal("50.00"),), corridor_h=Decimal("100.00"))
    coverage = CoverageMatrix(
        rules=(
            CoverageRule(
                shift_template_id=evening.id,
                override_date=date(2026, 3, 10),
                min_headcount=1,
                target_headcount=1,
            ),
            CoverageRule(
                shift_template_id=morning.id,
                override_date=date(2026, 3, 11),
                min_headcount=1,
                target_headcount=1,
            ),
        )
    )
    # 21:00 -> 07:00 is 10h rest (< 11h min_daily_rest_h): must be forbidden under OLT2_CARE.
    problem = _make_problem(
        shift_templates=(evening, morning),
        coverage_matrix=coverage,
        employees=employees,
        legal_rules=build_preset(LegalPresetType.OLT2_CARE),
        allow_pouliste=False,
    )
    output = solve_schedule(problem)
    assert output.status == SolverStatus.INFEASIBLE


@pytest.mark.dst
def test_dst_spring_forward_gap_shift_does_not_crash() -> None:
    """A shift endpoint in the 02:00-02:59 spring-forward gap is ineligible, never crashing."""
    gap_shift = ShiftTemplate(
        id=uuid4(),
        erp_code="GAP",
        label="Early 02:30-10:30",
        segments=(ShiftSegment(start_time=time(2, 30), end_time=time(10, 30)),),
        paid_duration_h=Decimal("8.00"),
    )
    employees = _make_employees(2, pensums=(Decimal("50.00"),), corridor_h=Decimal("100.00"))
    coverage = CoverageMatrix(
        rules=(
            CoverageRule(
                shift_template_id=gap_shift.id,
                override_date=date(2026, 3, 29),
                min_headcount=1,
                target_headcount=1,
            ),
            CoverageRule(
                shift_template_id=gap_shift.id,
                override_date=date(2026, 3, 30),
                min_headcount=1,
                target_headcount=1,
            ),
        )
    )
    problem = _make_problem(
        year_month="2026-03",
        shift_templates=(gap_shift,),
        coverage_matrix=coverage,
        employees=employees,
        allow_pouliste=True,
    )
    output = solve_schedule(problem)
    assert output.status in (SolverStatus.OPTIMAL, SolverStatus.FEASIBLE)
    sol = output.solutions[0]
    gap_dates = {g.work_date for g in sol.pouliste_gaps}
    assert date(2026, 3, 29) in gap_dates
    assert date(2026, 3, 30) not in gap_dates

    # Pinning an employee onto the nonexistent DST-gap shift returns INFEASIBLE cleanly.
    pinned_problem = _make_problem(
        year_month="2026-03",
        shift_templates=(gap_shift,),
        coverage_matrix=coverage,
        employees=employees,
        pinned_cells=(
            PinnedCell(
                employee_id=employees[0].id,
                work_date=date(2026, 3, 29),
                shift_template_id=gap_shift.id,
            ),
        ),
        allow_pouliste=True,
    )
    assert solve_schedule(pinned_problem).status == SolverStatus.INFEASIBLE

    # Shortened spring-forward night where unpaid_break_min exceeds elapsed UTC duration.
    short_night = ShiftTemplate(
        id=uuid4(),
        erp_code="SN",
        label="Short night 01:00-03:30",
        segments=(ShiftSegment(start_time=time(1, 0), end_time=time(3, 30)),),
        unpaid_break_min=120,
        paid_duration_h=None,
    )
    short_cov = CoverageMatrix(
        rules=(
            CoverageRule(
                shift_template_id=short_night.id,
                override_date=date(2026, 3, 29),
                min_headcount=1,
                target_headcount=1,
            ),
        )
    )
    short_problem = _make_problem(
        year_month="2026-03",
        shift_templates=(short_night,),
        coverage_matrix=short_cov,
        employees=employees,
        allow_pouliste=True,
    )
    short_out = solve_schedule(short_problem)
    assert short_out.status in (SolverStatus.OPTIMAL, SolverStatus.FEASIBLE)
    assert len(short_out.solutions[0].pouliste_gaps) == 1


@pytest.mark.dst
def test_dst_gap_fixed_sde_infeasible_and_invalid_prior_record_error() -> None:
    """DST-gap FIXED_SDE yields INFEASIBLE; DST-gap PriorDayRecord yields SolverStatus.ERROR."""
    _, m1, _, _ = _make_standard_shifts()
    employees = _make_employees(1, pensums=(Decimal("50.00"),), corridor_h=Decimal("100.00"))
    empty_cov = CoverageMatrix(rules=())

    bad_sde_problem = _make_problem(
        year_month="2026-03",
        shift_templates=(m1,),
        coverage_matrix=empty_cov,
        employees=employees,
        availability_requests=(
            AvailabilityRequest(
                id=uuid4(),
                employee_id=employees[0].id,
                request_date=date(2026, 3, 29),
                kind=RequestKind.FIXED_SDE,
                custom_interval=ShiftSegment(start_time=time(2, 30), end_time=time(4, 0)),
                sde_label="SDE/GAP",
                approved=True,
            ),
        ),
        allow_pouliste=True,
    )
    assert solve_schedule(bad_sde_problem).status == SolverStatus.INFEASIBLE

    # April 2026 with a prior-month record on 2026-03-29 (within 7-day boundary) at 02:30.
    bad_prior_problem = _make_problem(
        year_month="2026-04",
        shift_templates=(m1,),
        coverage_matrix=empty_cov,
        employees=employees,
        prior_month_boundary=PriorMonthBoundary(
            days=(
                PriorDayRecord(
                    employee_id=employees[0].id,
                    work_date=date(2026, 3, 29),
                    segments=(ShiftSegment(start_time=time(2, 30), end_time=time(6, 0)),),
                    paid_hours=Decimal("3.50"),
                ),
            )
        ),
        allow_pouliste=True,
    )
    err_out = solve_schedule(bad_prior_problem)
    assert err_out.status == SolverStatus.ERROR
    assert err_out.error_message is not None
    assert "prior-month boundary" in err_out.error_message


def test_fixed_sde_conflicts_with_hard_unavail_and_pinned_day_off() -> None:
    """Approved FIXED_SDE colliding with VACATION_V or a pinned day off returns INFEASIBLE."""
    _, m1, _, _ = _make_standard_shifts()
    employees = _make_employees(1, pensums=(Decimal("50.00"),), corridor_h=Decimal("100.00"))
    empty_cov = CoverageMatrix(rules=())
    sde_req = AvailabilityRequest(
        id=uuid4(),
        employee_id=employees[0].id,
        request_date=date(2026, 3, 12),
        kind=RequestKind.FIXED_SDE,
        custom_interval=ShiftSegment(start_time=time(9, 0), end_time=time(11, 0)),
        sde_label="SDE/09/11",
        approved=True,
    )
    vac_req = AvailabilityRequest(
        id=uuid4(),
        employee_id=employees[0].id,
        request_date=date(2026, 3, 12),
        kind=RequestKind.VACATION_V,
        approved=True,
    )

    vac_conflict = _make_problem(
        shift_templates=(m1,),
        coverage_matrix=empty_cov,
        employees=employees,
        availability_requests=(sde_req, vac_req),
        allow_pouliste=True,
    )
    assert solve_schedule(vac_conflict).status == SolverStatus.INFEASIBLE

    pin_conflict = _make_problem(
        shift_templates=(m1,),
        coverage_matrix=empty_cov,
        employees=employees,
        availability_requests=(sde_req,),
        pinned_cells=(
            PinnedCell(
                employee_id=employees[0].id,
                work_date=date(2026, 3, 12),
                is_day_off=True,
            ),
        ),
        allow_pouliste=True,
    )
    assert solve_schedule(pin_conflict).status == SolverStatus.INFEASIBLE


def test_single_event_sde_and_standalone_shift_enforce_daily_span_and_work_limits() -> None:
    """Single-event SDEs and standalone regular shifts enforce daily span and work limits."""
    _, m1, _, _ = _make_standard_shifts()
    employees = _make_employees(1, pensums=(Decimal("50.00"),), corridor_h=Decimal("100.00"))
    empty_cov = CoverageMatrix(rules=())

    # Lone 15h FIXED_SDE violates max_daily_span_h=14.0h and max_daily_work_h=12.5h.
    long_sde = AvailabilityRequest(
        id=uuid4(),
        employee_id=employees[0].id,
        request_date=date(2026, 3, 12),
        kind=RequestKind.FIXED_SDE,
        custom_interval=ShiftSegment(start_time=time(6, 0), end_time=time(21, 0)),
        sde_label="SDE/LONG",
        approved=True,
    )
    long_sde_problem = _make_problem(
        shift_templates=(m1,),
        coverage_matrix=empty_cov,
        employees=employees,
        availability_requests=(long_sde,),
        allow_pouliste=True,
    )
    assert solve_schedule(long_sde_problem).status == SolverStatus.INFEASIBLE

    # Standalone split shift with 15h span (06:00-08:00 + 16:00-21:00) > 14h max_daily_span_h.
    over_span_shift = ShiftTemplate(
        id=uuid4(),
        erp_code="SPAN15",
        label="Split 15h span",
        segments=(
            ShiftSegment(start_time=time(6, 0), end_time=time(8, 0)),
            ShiftSegment(start_time=time(16, 0), end_time=time(21, 0)),
        ),
        paid_duration_h=Decimal("7.00"),
    )
    span_cov = CoverageMatrix(
        rules=(
            CoverageRule(
                shift_template_id=over_span_shift.id,
                override_date=date(2026, 3, 12),
                min_headcount=1,
                target_headcount=1,
            ),
        )
    )
    span_problem = _make_problem(
        shift_templates=(over_span_shift,),
        coverage_matrix=span_cov,
        employees=employees,
        allow_pouliste=False,
    )
    assert solve_schedule(span_problem).status == SolverStatus.INFEASIBLE

    # Standalone 13h paid shift (07:00-20:00) > 12.5h max_daily_work_h (within 14h span).
    over_work_shift = ShiftTemplate(
        id=uuid4(),
        erp_code="WORK13",
        label="13h work",
        segments=(ShiftSegment(start_time=time(7, 0), end_time=time(20, 0)),),
        paid_duration_h=Decimal("13.00"),
    )
    work_cov = CoverageMatrix(
        rules=(
            CoverageRule(
                shift_template_id=over_work_shift.id,
                override_date=date(2026, 3, 12),
                min_headcount=1,
                target_headcount=1,
            ),
        )
    )
    work_problem = _make_problem(
        shift_templates=(over_work_shift,),
        coverage_matrix=work_cov,
        employees=employees,
        allow_pouliste=False,
    )
    assert solve_schedule(work_problem).status == SolverStatus.INFEASIBLE
