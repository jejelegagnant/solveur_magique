"""Core discrete fixed-shift CP-SAT optimization model (FR-009, FR-012, FR-013, FR-027, FR-028)."""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from time import perf_counter
from typing import Any, Final
from uuid import UUID

from ortools.sat.python import cp_model

from solver_core.calendar_utils import (
    classify_day_type,
    compute_employee_corridor_minutes,
    compute_monthly_target_minutes,
    compute_trailing_work_streak,
    iter_period_dates,
)
from solver_core.objective import ObjectiveWeights
from solver_core.schemas.common import LocalizedMessage, RequestKind, SolverStatus
from solver_core.schemas.input import SolverInput
from solver_core.schemas.legal import BreakWarning
from solver_core.schemas.output import (
    ConflictCard,
    ConflictResolutionHint,
    DailyCoverageSummaryOut,
    EmployeeSummaryOut,
    PoulisteGapOut,
    ScheduleKPIs,
    ScheduleSolution,
    ShiftAssignmentOut,
    SolverOutput,
)
from solver_core.schemas.requests import AvailabilityRequest, PinnedCell
from solver_core.schemas.shifts import ShiftTemplate
from solver_core.schemas.staff import EmployeeProfile
from solver_core.time_utils import (
    check_ltr_break_compliance,
    hours_to_minutes,
    intervals_overlap,
    is_nonexistent_local_time,
    minutes_to_hours,
    night_window_overlap_minutes,
    paid_minutes,
    segment_utc_interval,
    segments_utc_intervals,
)

__all__ = ["solve_schedule"]

_ONE_MINUTE_DELTA: Final[timedelta] = timedelta(minutes=1)
_HUNDRED: Final[Decimal] = Decimal(100)
_ONE_UNIT: Final[Decimal] = Decimal("1")
_TWO_DECIMALS: Final[Decimal] = Decimal("0.01")
_ZERO_HOURS: Final[Decimal] = Decimal("0.00")
_FULL_PCT: Final[Decimal] = Decimal("100.00")
_MAX_CELL_CODE_LEN: Final[int] = 32
_SUNDAY_WEEKDAY: Final[int] = 6

_POULISTE_SCALE: Final[int] = 1_000
_TARGET_SHORTFALL_SCALE: Final[int] = 500

_HARD_UNAVAIL_KINDS: Final[frozenset[RequestKind]] = frozenset(
    {
        RequestKind.VACATION_V,
        RequestKind.WEEKEND_BUFFER_X,
        RequestKind.HARD_UNAVAIL,
    }
)


@dataclass(frozen=True, slots=True)
class _SdeEvent:
    request: AvailabilityRequest
    interval: tuple[datetime, datetime]
    elapsed_min: int
    night_supp_min: int
    cell_code: str


@dataclass(frozen=True, slots=True)
class _PrecomputedContext:
    period_dates: tuple[date, ...]
    sunday_indices: frozenset[int]
    break_warnings: tuple[BreakWarning, ...]
    shift_intervals: dict[tuple[int, int], tuple[tuple[datetime, datetime], ...]]
    shift_paid_min: dict[tuple[int, int], int]
    shift_night_supp_min: dict[tuple[int, int], int]
    ineligible_day_shifts: frozenset[tuple[int, int]]
    coverage_reqs: dict[tuple[int, int], tuple[int, int]]
    min_rest_min: int
    max_daily_span_min: int
    max_daily_work_min: int
    employee_sdes: tuple[dict[int, list[_SdeEvent]], ...]
    employee_target_min: tuple[int, ...]
    employee_corridor_min: tuple[int, ...]
    employee_starting_solde_min: tuple[int, ...]
    employee_trailing_streak: tuple[int, ...]
    pinned_by_emp_day: dict[tuple[int, int], PinnedCell]
    pinned_shift_info: dict[tuple[int, int], tuple[int, bool]]
    hard_unavail_days: tuple[set[int], ...]
    hard_unavail_shifts: tuple[set[tuple[int, int]], ...]
    prior_rest_forbidden: set[tuple[int, int, int]]
    hard_infeasible: bool
    precompute_error: str | None


def _compute_night_supplement_minutes(night_min: int, bonus_pct: Decimal) -> int:
    """Compute rounded integer night-work time supplement minutes."""
    if night_min <= 0 or bonus_pct <= 0:
        return 0
    return int((Decimal(night_min) * bonus_pct / _HUNDRED).quantize(_ONE_UNIT, ROUND_HALF_UP))


def _pick_canonical_shift_date(shift: ShiftTemplate, period_dates: Sequence[date]) -> date:
    """Return the first date in ``period_dates`` where shift endpoints avoid DST spring gaps."""
    for candidate in period_dates:
        has_gap = False
        for seg in shift.segments:
            end_date = candidate + timedelta(days=1) if seg.crosses_midnight else candidate
            if is_nonexistent_local_time(candidate, seg.start_time) or is_nonexistent_local_time(
                end_date, seg.end_time
            ):
                has_gap = True
                break
        if not has_gap:
            return candidate
    return period_dates[0]


def _collect_break_warnings(
    shift_templates: Sequence[ShiftTemplate],
    period_dates: Sequence[date],
) -> tuple[BreakWarning, ...]:
    """Collect Art. 15 LTr break compliance warnings across all shift templates (FR-008)."""
    warnings: list[BreakWarning] = []
    for shift in shift_templates:
        canonical_date = _pick_canonical_shift_date(shift, period_dates)
        try:
            shift_warnings = check_ltr_break_compliance(
                canonical_date,
                shift.segments,
                shift.unpaid_break_min,
                paid_on_post_break=shift.paid_on_post_break,
                shift_template_id=shift.id,
            )
        except ValueError:
            continue
        warnings.extend(shift_warnings)
    return tuple(warnings)


def _is_employee_qualified(emp: EmployeeProfile, shift: ShiftTemplate) -> bool:
    """Return True if ``emp`` is qualified and holds any required role tag for ``shift``."""
    if emp.qualified_shift_ids and shift.id not in emp.qualified_shift_ids:
        return False
    return shift.required_role_tag is None or shift.required_role_tag in emp.role_tags


def _format_sde_cell_code(req: AvailabilityRequest, sde_prefix: str) -> str:
    """Format the ERP cell code for an approved FIXED_SDE event, capped at 32 chars."""
    assert req.custom_interval is not None
    if req.sde_label is not None:
        raw_code = req.sde_label
    else:
        seg = req.custom_interval
        raw_code = f"{sde_prefix}/{seg.start_time.hour:02d}/{seg.end_time.hour:02d}"
    return raw_code[:_MAX_CELL_CODE_LEN]


def _shift_conflicts_with_sdes(
    d_idx: int,
    shift_ivs: tuple[tuple[datetime, datetime], ...],
    paid_min: int,
    sdes_by_day: dict[int, list[_SdeEvent]],
    *,
    min_rest_min: int,
    max_daily_span_min: int,
    max_daily_work_min: int,
) -> bool:
    """Return True if assigning this shift on ``d_idx`` conflicts with approved SDEs."""
    shift_start = shift_ivs[0][0]
    shift_end = shift_ivs[-1][1]

    # Previous day SDE -> current day shift rest & overlap check.
    for prev_sde in sdes_by_day.get(d_idx - 1, ()):
        if any(intervals_overlap(seg_iv, prev_sde.interval) for seg_iv in shift_ivs):
            return True
        if (shift_start - prev_sde.interval[1]) // _ONE_MINUTE_DELTA < min_rest_min:
            return True

    # Current day shift -> next day SDE rest & overlap check.
    for next_sde in sdes_by_day.get(d_idx + 1, ()):
        if any(intervals_overlap(seg_iv, next_sde.interval) for seg_iv in shift_ivs):
            return True
        if (next_sde.interval[0] - shift_end) // _ONE_MINUTE_DELTA < min_rest_min:
            return True

    # Same-day SDE overlap, combined span, and combined work checks.
    same_day_sdes = sdes_by_day.get(d_idx)
    if same_day_sdes:
        for sde in same_day_sdes:
            if any(intervals_overlap(seg_iv, sde.interval) for seg_iv in shift_ivs):
                return True

        combined_start = min(shift_start, *(sde.interval[0] for sde in same_day_sdes))
        combined_end = max(shift_end, *(sde.interval[1] for sde in same_day_sdes))
        if (combined_end - combined_start) // _ONE_MINUTE_DELTA > max_daily_span_min:
            return True

        combined_work = paid_min + sum(sde.elapsed_min for sde in same_day_sdes)
        if combined_work > max_daily_work_min:
            return True

    return False


def _precompute_context(problem: SolverInput) -> _PrecomputedContext:
    """Precompute exact DST-safe shift durations, coverage, requests, and boundary context."""
    period_dates = iter_period_dates(problem.year_month)
    num_days = len(period_dates)
    num_emps = len(problem.employees)
    public_holidays = frozenset(problem.public_holidays)

    date_to_idx: dict[date, int] = {d: idx for idx, d in enumerate(period_dates)}
    emp_id_to_idx: dict[UUID, int] = {emp.id: idx for idx, emp in enumerate(problem.employees)}
    shift_id_to_idx: dict[UUID, int] = {
        shift.id: idx for idx, shift in enumerate(problem.shift_templates)
    }

    sunday_indices = frozenset(
        d_idx
        for d_idx, work_date in enumerate(period_dates)
        if work_date.weekday() == _SUNDAY_WEEKDAY
    )
    break_warnings = _collect_break_warnings(problem.shift_templates, period_dates)

    legal = problem.legal_rules
    # Conservatively enforce full min_daily_rest_h whenever reduced rest requires a rolling
    # averaging window (encoded in Issue #4) so no illegal consecutive reduced-rest pairs occur.
    min_rest_min = hours_to_minutes(
        legal.min_daily_rest_h
        if legal.reduced_rest_avg_window_days is not None or legal.min_reduced_rest_h is None
        else legal.min_reduced_rest_h
    )
    max_daily_span_min = hours_to_minutes(legal.max_daily_span_h)
    max_daily_work_min = hours_to_minutes(legal.max_daily_work_h)

    shift_intervals: dict[tuple[int, int], tuple[tuple[datetime, datetime], ...]] = {}
    shift_paid_min: dict[tuple[int, int], int] = {}
    shift_night_supp_min: dict[tuple[int, int], int] = {}
    ineligible_day_shifts: set[tuple[int, int]] = set()
    coverage_reqs: dict[tuple[int, int], tuple[int, int]] = {}

    for d_idx, work_date in enumerate(period_dates):
        day_type = classify_day_type(work_date, public_holidays)
        for s_idx, shift in enumerate(problem.shift_templates):
            key = (d_idx, s_idx)
            coverage_reqs[key] = problem.coverage_matrix.resolve(shift.id, work_date, day_type)
            try:
                ivs = segments_utc_intervals(work_date, shift.segments)
                if shift.paid_duration_h is not None:
                    paid_min = hours_to_minutes(shift.paid_duration_h)
                else:
                    paid_min = paid_minutes(work_date, shift.segments, shift.unpaid_break_min)
                night_min = night_window_overlap_minutes(
                    work_date,
                    shift.segments,
                    legal.night_window_start,
                    legal.night_window_end,
                )
            except ValueError:
                ineligible_day_shifts.add(key)
                continue

            shift_intervals[key] = ivs
            shift_paid_min[key] = paid_min
            shift_night_supp_min[key] = _compute_night_supplement_minutes(
                night_min,
                legal.night_bonus_pct,
            )

            shift_span_min = (ivs[-1][1] - ivs[0][0]) // _ONE_MINUTE_DELTA
            if shift_span_min > max_daily_span_min or paid_min > max_daily_work_min:
                ineligible_day_shifts.add(key)

    hard_unavail_days: tuple[set[int], ...] = tuple(set() for _ in range(num_emps))
    hard_unavail_shifts: tuple[set[tuple[int, int]], ...] = tuple(set() for _ in range(num_emps))
    approved_vacation_dates: tuple[set[date], ...] = tuple(set() for _ in range(num_emps))
    employee_sdes: tuple[dict[int, list[_SdeEvent]], ...] = tuple({} for _ in range(num_emps))
    sde_prefix = problem.team.non_shift_codes.sde_prefix
    hard_infeasible = False
    precompute_error: str | None = None

    for req in problem.availability_requests:
        if not req.approved:
            continue
        e_idx = emp_id_to_idx[req.employee_id]
        d_idx = date_to_idx[req.request_date]

        if req.kind in _HARD_UNAVAIL_KINDS:
            if req.kind == RequestKind.VACATION_V:
                approved_vacation_dates[e_idx].add(req.request_date)
            if req.shift_template_id is None:
                hard_unavail_days[e_idx].add(d_idx)
            else:
                hard_unavail_shifts[e_idx].add((d_idx, shift_id_to_idx[req.shift_template_id]))
        elif req.kind == RequestKind.FIXED_SDE and req.custom_interval is not None:
            seg = req.custom_interval
            try:
                sde_iv = segment_utc_interval(req.request_date, seg)
                sde_night_min = night_window_overlap_minutes(
                    req.request_date,
                    (seg,),
                    legal.night_window_start,
                    legal.night_window_end,
                )
            except ValueError:
                hard_infeasible = True
                continue
            sde_elapsed_min = (sde_iv[1] - sde_iv[0]) // _ONE_MINUTE_DELTA
            sde_night_supp_min = _compute_night_supplement_minutes(
                sde_night_min,
                legal.night_bonus_pct,
            )
            event = _SdeEvent(
                request=req,
                interval=sde_iv,
                elapsed_min=sde_elapsed_min,
                night_supp_min=sde_night_supp_min,
                cell_code=_format_sde_cell_code(req, sde_prefix),
            )
            employee_sdes[e_idx].setdefault(d_idx, []).append(event)

    # Check same-day and adjacent-day FIXED_SDE overlap, unavailability, span, work, and rest.
    for e_idx in range(num_emps):
        sdes_by_day = employee_sdes[e_idx]
        unavail_days = hard_unavail_days[e_idx]
        for d_idx, day_sdes in sdes_by_day.items():
            if d_idx in unavail_days:
                hard_infeasible = True

            sorted_sdes = sorted(day_sdes, key=lambda ev: ev.interval[0])
            if len(sorted_sdes) > 1:
                for idx in range(len(sorted_sdes) - 1):
                    if intervals_overlap(sorted_sdes[idx].interval, sorted_sdes[idx + 1].interval):
                        hard_infeasible = True

            combined_start = sorted_sdes[0].interval[0]
            combined_end = max(ev.interval[1] for ev in sorted_sdes)
            if (combined_end - combined_start) // _ONE_MINUTE_DELTA > max_daily_span_min:
                hard_infeasible = True
            if sum(ev.elapsed_min for ev in sorted_sdes) > max_daily_work_min:
                hard_infeasible = True

            next_sdes = sdes_by_day.get(d_idx + 1)
            if not next_sdes:
                continue
            latest_end = max(sde.interval[1] for sde in day_sdes)
            earliest_next_start = min(sde.interval[0] for sde in next_sdes)
            if (earliest_next_start - latest_end) // _ONE_MINUTE_DELTA < min_rest_min:
                hard_infeasible = True

    # Cross-month 1st-of-month rest continuity against prior_month_boundary.days (FR-028).
    prior_rest_forbidden: set[tuple[int, int, int]] = set()
    boundary_check_days = range(min(2, num_days))
    for rec in problem.prior_month_boundary.days:
        if not rec.segments:
            continue
        e_idx = emp_id_to_idx[rec.employee_id]
        try:
            prior_ivs = segments_utc_intervals(rec.work_date, rec.segments)
        except ValueError as exc:
            precompute_error = (
                f"Invalid prior-month boundary record for employee {rec.employee_id} "
                f"on {rec.work_date.isoformat()}: {exc}"
            )
            break
        prior_end = prior_ivs[-1][1]

        for d_idx in boundary_check_days:
            for s_idx in range(len(problem.shift_templates)):
                shift_ivs = shift_intervals.get((d_idx, s_idx))
                if shift_ivs is None:
                    continue
                rest_min = (shift_ivs[0][0] - prior_end) // _ONE_MINUTE_DELTA
                if rest_min < min_rest_min:
                    prior_rest_forbidden.add((e_idx, d_idx, s_idx))

            for sde in employee_sdes[e_idx].get(d_idx, ()):
                if (sde.interval[0] - prior_end) // _ONE_MINUTE_DELTA < min_rest_min:
                    hard_infeasible = True

    pinned_by_emp_day: dict[tuple[int, int], PinnedCell] = {}
    pinned_shift_info: dict[tuple[int, int], tuple[int, bool]] = {}
    for pin in problem.pinned_cells:
        e_idx = emp_id_to_idx[pin.employee_id]
        d_idx = date_to_idx[pin.work_date]
        pinned_by_emp_day[(e_idx, d_idx)] = pin
        if pin.is_day_off and d_idx in employee_sdes[e_idx]:
            hard_infeasible = True
        if pin.shift_template_id is not None:
            pinned_shift_info[(e_idx, d_idx)] = (
                shift_id_to_idx[pin.shift_template_id],
                pin.is_doublure,
            )

    employee_target_min = tuple(
        compute_monthly_target_minutes(
            emp,
            period_dates,
            public_holidays,
            approved_vacation_dates[e_idx],
            problem.team.base_fulltime_weekly_h,
        )
        for e_idx, emp in enumerate(problem.employees)
    )
    employee_corridor_min = tuple(
        compute_employee_corridor_minutes(emp, problem.team.default_corridor_h)
        for emp in problem.employees
    )
    employee_starting_solde_min = tuple(
        hours_to_minutes(emp.current_solde_h) for emp in problem.employees
    )
    employee_trailing_streak = tuple(
        compute_trailing_work_streak(emp.id, period_dates[0], problem.prior_month_boundary)
        for emp in problem.employees
    )

    return _PrecomputedContext(
        period_dates=period_dates,
        sunday_indices=sunday_indices,
        break_warnings=break_warnings,
        shift_intervals=shift_intervals,
        shift_paid_min=shift_paid_min,
        shift_night_supp_min=shift_night_supp_min,
        ineligible_day_shifts=frozenset(ineligible_day_shifts),
        coverage_reqs=coverage_reqs,
        min_rest_min=min_rest_min,
        max_daily_span_min=max_daily_span_min,
        max_daily_work_min=max_daily_work_min,
        employee_sdes=employee_sdes,
        employee_target_min=employee_target_min,
        employee_corridor_min=employee_corridor_min,
        employee_starting_solde_min=employee_starting_solde_min,
        employee_trailing_streak=employee_trailing_streak,
        pinned_by_emp_day=pinned_by_emp_day,
        pinned_shift_info=pinned_shift_info,
        hard_unavail_days=hard_unavail_days,
        hard_unavail_shifts=hard_unavail_shifts,
        prior_rest_forbidden=prior_rest_forbidden,
        hard_infeasible=hard_infeasible,
        precompute_error=precompute_error,
    )


def _build_pouliste_gap_reason(
    work_date: date,
    shift_erp_code: str,
    missing_headcount: int,
) -> LocalizedMessage:
    """Build a concise trilingual explanation for a pouliste open slot (FR-031)."""
    iso_date = work_date.isoformat()
    return LocalizedMessage(
        fr_CH=(
            f"{missing_headcount} poste(s) {shift_erp_code} non couvert(s) le {iso_date} "
            "par l'équipe permanente sous les contraintes actives."
        ),
        de_CH=(
            f"{missing_headcount} Schicht(en) {shift_erp_code} am {iso_date} "
            "durch das Stammteam unter den aktiven Regeln nicht abdeckbar."
        ),
        en=(
            f"{missing_headcount} {shift_erp_code} slot(s) on {iso_date} "
            "could not be covered by permanent staff under active constraints."
        ),
    )


def _build_basic_infeasible_card(problem: SolverInput) -> ConflictCard:
    """Build a valid trilingual infeasibility conflict card (Issue #6 refines via assumptions)."""
    hints: list[ConflictResolutionHint] = []
    if not problem.options.allow_pouliste:
        hints.append(
            ConflictResolutionHint(
                action_code="ENABLE_POULISTE",
                label=LocalizedMessage(
                    fr_CH="Autoriser les postes ouverts (poulistes)",
                    de_CH="Offene Pool-Schichten (Poulisten) zulassen",
                    en="Allow Pouliste open replacement slots",
                ),
            )
        )
    if problem.pinned_cells:
        hints.append(
            ConflictResolutionHint(
                action_code="REVIEW_PINNED_CELLS",
                label=LocalizedMessage(
                    fr_CH="Vérifier ou déverrouiller les cellules épinglées",
                    de_CH="Fixierte Zellen prüfen oder entsperren",
                    en="Review or unpin locked schedule cells",
                ),
            )
        )
    hints.append(
        ConflictResolutionHint(
            action_code="RELAX_CONSTRAINTS",
            label=LocalizedMessage(
                fr_CH="Assouplir la couverture, les absences ou le corridor d'heures",
                de_CH="Bedarf, Abwesenheiten oder Stundenkorridor lockern",
                en="Relax coverage minimums, unavailabilities, or hour corridors",
            ),
        )
    )
    return ConflictCard(
        conflict_id="infeasible-core-basic",
        rule_code="SCHEDULE_INFEASIBLE",
        title=LocalizedMessage(
            fr_CH="Planning impossible sous les contraintes actuelles",
            de_CH="Dienstplan unter den aktuellen Regeln nicht lösbar",
            en="No feasible schedule under current constraints",
        ),
        explanation=LocalizedMessage(
            fr_CH=(
                "Aucune affectation ne permet de satisfaire simultanément la couverture requise, "
                "les temps de repos, les cellules épinglées et les corridors horaires."
            ),
            de_CH=(
                "Keine Zuteilung erfüllt gleichzeitig den Mindestbedarf, die Ruhezeiten, "
                "fixierte Zellen und die Stundenkorridore."
            ),
            en=(
                "No assignment can simultaneously satisfy required shift coverage, "
                "rest rules, pinned cells, and monthly hour corridors."
            ),
        ),
        resolution_hints=tuple(hints),
    )


def _extract_solution(
    problem: SolverInput,
    ctx: _PrecomputedContext,
    solver: cp_model.CpSolver,
    x: dict[tuple[int, int, int], Any],
    *,
    objective_scale: int,
    objective_offset: int,
    has_objective: bool,
) -> ScheduleSolution:
    """Extract deterministic ScheduleSolution, summaries, coverage, and KPIs from CP-SAT."""
    num_days = len(ctx.period_dates)
    num_emps = len(problem.employees)
    num_shifts = len(problem.shift_templates)
    total_sundays = len(ctx.sunday_indices)

    assignments: list[ShiftAssignmentOut] = []
    assigned_count: dict[tuple[int, int], int] = {}
    emp_scheduled_min = [0] * num_emps
    emp_night_supp_min = [0] * num_emps
    emp_worked_days: list[set[int]] = [set() for _ in range(num_emps)]

    # Extract regular shift assignments.
    for (e_idx, d_idx, s_idx), var in x.items():
        if not bool(solver.boolean_value(var)):
            continue
        emp = problem.employees[e_idx]
        shift = problem.shift_templates[s_idx]
        work_date = ctx.period_dates[d_idx]
        paid_min = ctx.shift_paid_min[(d_idx, s_idx)]
        night_supp_min = ctx.shift_night_supp_min[(d_idx, s_idx)]

        pin_info = ctx.pinned_shift_info.get((e_idx, d_idx))
        is_pinned = pin_info is not None and pin_info[0] == s_idx
        is_doublure = pin_info[1] if is_pinned and pin_info is not None else False

        assignments.append(
            ShiftAssignmentOut(
                employee_id=emp.id,
                work_date=work_date,
                shift_template_id=shift.id,
                cell_code=shift.erp_code,
                is_pinned=is_pinned,
                is_doublure=is_doublure,
                is_sde=False,
                paid_hours=minutes_to_hours(paid_min),
                night_supplement_hours=minutes_to_hours(night_supp_min),
            )
        )
        assigned_count[(d_idx, s_idx)] = assigned_count.get((d_idx, s_idx), 0) + 1
        emp_scheduled_min[e_idx] += paid_min
        emp_night_supp_min[e_idx] += night_supp_min
        emp_worked_days[e_idx].add(d_idx)

    # Extract approved FIXED_SDE assignments.
    for e_idx, emp in enumerate(problem.employees):
        for d_idx, day_sdes in ctx.employee_sdes[e_idx].items():
            work_date = ctx.period_dates[d_idx]
            for sde in day_sdes:
                assignments.append(
                    ShiftAssignmentOut(
                        employee_id=emp.id,
                        work_date=work_date,
                        shift_template_id=None,
                        cell_code=sde.cell_code,
                        is_pinned=False,
                        is_doublure=False,
                        is_sde=True,
                        paid_hours=minutes_to_hours(sde.elapsed_min),
                        night_supplement_hours=minutes_to_hours(sde.night_supp_min),
                    )
                )
                emp_scheduled_min[e_idx] += sde.elapsed_min
                emp_night_supp_min[e_idx] += sde.night_supp_min
                emp_worked_days[e_idx].add(d_idx)

    assignments.sort(key=lambda a: (a.work_date, a.employee_id, a.cell_code))

    # Build daily coverage summaries and pouliste gap records.
    daily_coverage: list[DailyCoverageSummaryOut] = []
    pouliste_gaps: list[PoulisteGapOut] = []
    for d_idx in range(num_days):
        work_date = ctx.period_dates[d_idx]
        for s_idx in range(num_shifts):
            shift = problem.shift_templates[s_idx]
            min_hc, target_hc = ctx.coverage_reqs[(d_idx, s_idx)]
            assigned_hc = assigned_count.get((d_idx, s_idx), 0)
            actual_gap = max(0, min_hc - assigned_hc)
            if actual_gap > 0:
                pouliste_gaps.append(
                    PoulisteGapOut(
                        work_date=work_date,
                        shift_template_id=shift.id,
                        shift_erp_code=shift.erp_code,
                        missing_headcount=actual_gap,
                        reason=_build_pouliste_gap_reason(work_date, shift.erp_code, actual_gap),
                    )
                )
            if min_hc > 0 or target_hc > 0 or assigned_hc > 0:
                daily_coverage.append(
                    DailyCoverageSummaryOut(
                        work_date=work_date,
                        shift_template_id=shift.id,
                        shift_erp_code=shift.erp_code,
                        min_headcount=min_hc,
                        target_headcount=target_hc,
                        assigned_headcount=assigned_hc,
                        pouliste_gaps=actual_gap,
                    )
                )

    # Build per-employee summaries.
    employee_summaries: list[EmployeeSummaryOut] = []
    for e_idx, emp in enumerate(problem.employees):
        target_min = ctx.employee_target_min[e_idx]
        corridor_min = ctx.employee_corridor_min[e_idx]
        starting_solde_min = ctx.employee_starting_solde_min[e_idx]
        scheduled_min = emp_scheduled_min[e_idx]
        night_supp_min = emp_night_supp_min[e_idx]
        monthly_delta_min = scheduled_min - target_min
        ending_solde_min = starting_solde_min + monthly_delta_min
        corridor_breached = (
            abs(monthly_delta_min) > corridor_min or abs(ending_solde_min) > corridor_min
        )
        sundays_worked = sum(1 for d_idx in ctx.sunday_indices if d_idx in emp_worked_days[e_idx])
        free_sundays = total_sundays - sundays_worked

        employee_summaries.append(
            EmployeeSummaryOut(
                employee_id=emp.id,
                target_hours=minutes_to_hours(target_min),
                scheduled_hours=minutes_to_hours(scheduled_min),
                night_supplement_hours=minutes_to_hours(night_supp_min),
                monthly_delta_h=minutes_to_hours(monthly_delta_min),
                starting_solde_h=minutes_to_hours(starting_solde_min),
                ending_solde_h=minutes_to_hours(ending_solde_min),
                corridor_breached=corridor_breached,
                sundays_worked=sundays_worked,
                free_sundays_in_period=free_sundays,
                preferences_satisfied=0,
                preferences_total=0,
                satisfaction_rate_pct=_FULL_PCT,
            )
        )

    objective_int = (
        round(float(solver.objective_value)) * objective_scale + objective_offset
        if has_objective
        else objective_offset
    )
    kpis = ScheduleKPIs(
        objective_value=Decimal(objective_int).quantize(_TWO_DECIMALS),
        total_pouliste_gaps=sum(gap.missing_headcount for gap in pouliste_gaps),
        wish_satisfaction_pct=_FULL_PCT,
        max_abs_delta_h=max(
            (abs(summary.monthly_delta_h) for summary in employee_summaries),
            default=_ZERO_HOURS,
        ),
        corridor_breach_count=sum(1 for summary in employee_summaries if summary.corridor_breached),
        pin_churn_count=0,
        total_scheduled_hours=sum(
            (summary.scheduled_hours for summary in employee_summaries),
            _ZERO_HOURS,
        ),
        total_night_supplement_hours=sum(
            (summary.night_supplement_hours for summary in employee_summaries),
            _ZERO_HOURS,
        ),
    )

    return ScheduleSolution(
        option_index=0,
        assignments=tuple(assignments),
        pouliste_gaps=tuple(pouliste_gaps),
        employee_summaries=tuple(employee_summaries),
        daily_coverage=tuple(daily_coverage),
        kpis=kpis,
    )


def solve_schedule(
    problem: SolverInput,
    *,
    weights: ObjectiveWeights | None = None,
) -> SolverOutput:
    """Build and solve the discrete shift-scheduling CP-SAT model (FR-027).

    ``problem.public_holidays`` is treated as the authoritative explicit holiday
    snapshot for the period (callers can populate it via ``get_cantonal_holidays``
    or pass custom overrides).
    """
    start_time = perf_counter()
    active_weights = weights if weights is not None else ObjectiveWeights()
    ctx = _precompute_context(problem)

    if ctx.precompute_error is not None:
        duration_ms = max(0, round((perf_counter() - start_time) * 1000))
        return SolverOutput(
            period_id=problem.period_id,
            status=SolverStatus.ERROR,
            solve_duration_ms=duration_ms,
            break_warnings=ctx.break_warnings,
            error_message=ctx.precompute_error,
        )

    num_days = len(ctx.period_dates)
    num_emps = len(problem.employees)
    num_shifts = len(problem.shift_templates)

    model = cp_model.CpModel()
    hard_infeasible = ctx.hard_infeasible

    # 1. Create lean binary decision variables x[e, d, s] only for statically eligible triples.
    x: dict[tuple[int, int, int], Any] = {}
    emp_day_vars: list[list[list[Any]]] = [[[] for _ in range(num_days)] for _ in range(num_emps)]
    emp_day_shifts: list[list[list[int]]] = [[[] for _ in range(num_days)] for _ in range(num_emps)]
    day_shift_vars: list[list[list[Any]]] = [
        [[] for _ in range(num_shifts)] for _ in range(num_days)
    ]

    qualified: list[list[bool]] = [
        [_is_employee_qualified(emp, shift) for shift in problem.shift_templates]
        for emp in problem.employees
    ]

    for e_idx in range(num_emps):
        unavail_days = ctx.hard_unavail_days[e_idx]
        unavail_shifts = ctx.hard_unavail_shifts[e_idx]
        sdes_by_day = ctx.employee_sdes[e_idx]

        for d_idx in range(num_days):
            pin = ctx.pinned_by_emp_day.get((e_idx, d_idx))
            if pin is not None and pin.is_day_off:
                continue

            pinned_shift_idx = (
                ctx.pinned_shift_info[(e_idx, d_idx)][0]
                if (e_idx, d_idx) in ctx.pinned_shift_info
                else None
            )

            for s_idx in range(num_shifts):
                if pinned_shift_idx is not None and s_idx != pinned_shift_idx:
                    continue

                _, target_hc = ctx.coverage_reqs[(d_idx, s_idx)]
                statically_forbidden = (
                    not qualified[e_idx][s_idx]
                    or (d_idx, s_idx) in ctx.ineligible_day_shifts
                    or d_idx in unavail_days
                    or (d_idx, s_idx) in unavail_shifts
                    or (e_idx, d_idx, s_idx) in ctx.prior_rest_forbidden
                    or target_hc == 0
                    or _shift_conflicts_with_sdes(
                        d_idx,
                        ctx.shift_intervals[(d_idx, s_idx)],
                        ctx.shift_paid_min[(d_idx, s_idx)],
                        sdes_by_day,
                        min_rest_min=ctx.min_rest_min,
                        max_daily_span_min=ctx.max_daily_span_min,
                        max_daily_work_min=ctx.max_daily_work_min,
                    )
                )

                if statically_forbidden:
                    if pinned_shift_idx == s_idx:
                        # Never silently ignore a pin that conflicts with hard rules.
                        hard_infeasible = True
                    continue

                var = model.new_bool_var(f"x_{e_idx}_{d_idx}_{s_idx}")
                x[(e_idx, d_idx, s_idx)] = var
                emp_day_vars[e_idx][d_idx].append(var)
                emp_day_shifts[e_idx][d_idx].append(s_idx)
                day_shift_vars[d_idx][s_idx].append(var)

                if pinned_shift_idx == s_idx:
                    model.add(var == 1)

    # 2. Hard constraint: At-most-one shift/day via compact worked[e, d] BoolVars.
    worked_grid: list[list[int | Any]] = [[0] * num_days for _ in range(num_emps)]
    for e_idx in range(num_emps):
        emp_sdes = ctx.employee_sdes[e_idx]
        for d_idx in range(num_days):
            day_vars = emp_day_vars[e_idx][d_idx]
            if d_idx in emp_sdes:
                worked_grid[e_idx][d_idx] = 1
                if len(day_vars) > 1:
                    model.add_at_most_one(day_vars)
            elif not day_vars:
                worked_grid[e_idx][d_idx] = 0
            elif len(day_vars) == 1:
                worked_grid[e_idx][d_idx] = day_vars[0]
            else:
                w_var = model.new_bool_var(f"w_{e_idx}_{d_idx}")
                model.add(cp_model.LinearExpr.sum(day_vars) == w_var)
                worked_grid[e_idx][d_idx] = w_var

    # 3. Hard constraint: Inter-day no-overlap & minimum daily rest via native clique cuts.
    for d_idx in range(num_days - 1):
        bad_groups: dict[frozenset[int], list[int]] = {}
        for s2 in range(num_shifts):
            next_ivs = ctx.shift_intervals.get((d_idx + 1, s2))
            if next_ivs is None:
                continue
            next_start = next_ivs[0][0]
            bad_prev = frozenset(
                s1
                for s1 in range(num_shifts)
                if (d_idx, s1) in ctx.shift_intervals
                and (next_start - ctx.shift_intervals[(d_idx, s1)][-1][1]) // _ONE_MINUTE_DELTA
                < ctx.min_rest_min
            )
            if bad_prev:
                bad_groups.setdefault(bad_prev, []).append(s2)

        if not bad_groups:
            continue

        for e_idx in range(num_emps):
            for bad_prev, next_shifts in bad_groups.items():
                prev_vars = [x[(e_idx, d_idx, s1)] for s1 in bad_prev if (e_idx, d_idx, s1) in x]
                if not prev_vars:
                    continue
                next_vars = [
                    x[(e_idx, d_idx + 1, s2)] for s2 in next_shifts if (e_idx, d_idx + 1, s2) in x
                ]
                if not next_vars:
                    continue
                model.add_at_most_one([*prev_vars, *next_vars])

    # 4. Hard constraint: Cross-month consecutive working days streak (FR-028).
    max_streak = problem.legal_rules.max_consecutive_days
    streak_window = max_streak + 1
    for e_idx in range(num_emps):
        trailing = ctx.employee_trailing_streak[e_idx]
        worked_seq: list[int | Any] = [1] * trailing + worked_grid[e_idx]

        if len(worked_seq) < streak_window:
            continue

        for start_idx in range(len(worked_seq) - streak_window + 1):
            window_slice = worked_seq[start_idx : start_idx + streak_window]
            const_ones = 0
            var_terms: list[Any] = []
            for entry in window_slice:
                if isinstance(entry, int):
                    const_ones += entry
                else:
                    var_terms.append(entry)

            if const_ones > max_streak:
                hard_infeasible = True
                break
            if not var_terms or const_ones + len(var_terms) <= max_streak:
                continue
            model.add(cp_model.LinearExpr.sum(var_terms) <= max_streak - const_ones)

    # 5. Hard/soft constraint: Daily shift coverage & optional pouliste slack (FR-009, FR-031).
    pouliste_coeff = active_weights.pouliste_gap_penalty * _POULISTE_SCALE
    breach_coeff = active_weights.corridor_breach_penalty
    shortfall_coeff = active_weights.target_shortfall_penalty * _TARGET_SHORTFALL_SCALE
    ending_solde_coeff = active_weights.ending_solde_drift_penalty
    monthly_delta_coeff = active_weights.hour_balance_drift_penalty

    obj_vars: list[Any] = []
    obj_coeffs: list[int] = []
    obj_constant_offset = 0
    dur_vars: dict[int, list[Any]] = {}
    dur_max_hc: dict[int, int] = {}

    for d_idx in range(num_days):
        for s_idx in range(num_shifts):
            min_hc, target_hc = ctx.coverage_reqs[(d_idx, s_idx)]
            eligible_vars = day_shift_vars[d_idx][s_idx]

            if not eligible_vars:
                if min_hc > 0:
                    if problem.options.allow_pouliste:
                        obj_constant_offset += pouliste_coeff * min_hc
                    else:
                        hard_infeasible = True
                if target_hc > min_hc and shortfall_coeff > 0:
                    obj_constant_offset += shortfall_coeff * target_hc
                continue

            assigned_expr = (
                eligible_vars[0]
                if len(eligible_vars) == 1
                else cp_model.LinearExpr.sum(eligible_vars)
            )
            model.add(assigned_expr <= target_hc)

            paid_min = ctx.shift_paid_min[(d_idx, s_idx)]
            if paid_min > 0:
                dur_vars.setdefault(paid_min, []).extend(eligible_vars)
                dur_max_hc[paid_min] = dur_max_hc.get(paid_min, 0) + min(
                    target_hc, len(eligible_vars)
                )

            if min_hc > 0:
                if problem.options.allow_pouliste:
                    gap = model.new_int_var(0, min_hc, f"gap_{d_idx}_{s_idx}")
                    model.add(assigned_expr + gap >= min_hc)
                    if pouliste_coeff > 0:
                        obj_vars.append(gap)
                        obj_coeffs.append(pouliste_coeff)
                else:
                    model.add(assigned_expr >= min_hc)

            if target_hc > min_hc and shortfall_coeff > 0:
                # Since assigned_expr <= target_hc is hard, shortfall == target_hc - assigned_expr.
                obj_constant_offset += shortfall_coeff * target_hc
                for var in eligible_vars:
                    obj_vars.append(var)
                    obj_coeffs.append(-shortfall_coeff)

    # 6. Contractual pensum target hours, monthly ±corridor, and carry-over solde (FR-012, FR-013).
    u_vars_all: list[Any] = []
    u_gcds_all: list[int] = []

    for e_idx in range(num_emps):
        target_min = ctx.employee_target_min[e_idx]
        corridor_min = ctx.employee_corridor_min[e_idx]
        starting_solde_min = ctx.employee_starting_solde_min[e_idx]
        sde_total_min = sum(
            sde.elapsed_min for day_sdes in ctx.employee_sdes[e_idx].values() for sde in day_sdes
        )

        shift_vars: list[Any] = []
        shift_coeffs: list[int] = []
        max_possible_min = sde_total_min
        for d_idx in range(num_days):
            day_s_indices = emp_day_shifts[e_idx][d_idx]
            if not day_s_indices:
                continue
            max_possible_min += max(ctx.shift_paid_min[(d_idx, s_idx)] for s_idx in day_s_indices)
            for s_idx in day_s_indices:
                paid_min = ctx.shift_paid_min[(d_idx, s_idx)]
                if paid_min > 0:
                    shift_vars.append(x[(e_idx, d_idx, s_idx)])
                    shift_coeffs.append(paid_min)

        lower_sched = max(0, target_min - corridor_min)
        upper_sched = min(max_possible_min, target_min + corridor_min)
        if lower_sched > upper_sched or sde_total_min > upper_sched:
            hard_infeasible = True
            continue

        if not shift_vars:
            if sde_total_min < lower_sched:
                hard_infeasible = True
                continue
            delta_const = abs(sde_total_min - target_min)
            ending_const = abs(starting_solde_min + sde_total_min - target_min)
            breach_const = max(0, ending_const - corridor_min)
            obj_constant_offset += (
                monthly_delta_coeff * delta_const
                + ending_solde_coeff * ending_const
                + breach_coeff * breach_const
            )
            continue

        # GCD domain reduction: sched = u_var * g + sde_total_min with tightened integer bounds.
        coeff_gcd = math.gcd(*shift_coeffs)
        min_u = (
            (lower_sched - sde_total_min + coeff_gcd - 1) // coeff_gcd
            if lower_sched > sde_total_min
            else 0
        )
        max_u = (upper_sched - sde_total_min) // coeff_gcd
        if min_u > max_u:
            hard_infeasible = True
            continue

        u_var = model.new_int_var(min_u, max_u, f"u_{e_idx}")
        reduced_coeffs = [c // coeff_gcd for c in shift_coeffs]
        model.add(u_var == cp_model.LinearExpr.weighted_sum(shift_vars, reduced_coeffs))
        u_vars_all.append(u_var)
        u_gcds_all.append(coeff_gcd)

        # Exact combined integer convex hull for all 3 hour-balance objective terms on u_var.
        # Since f(u) = c_d*|u*g+d0| + c_e*|u*g+e0| + c_b*max(0, |u*g+e0|-C) is convex on Z,
        # its exact lower envelope over u in [min_u, max_u] needs only one linear inequality
        # per distinct slope (typically 3-6 facets) with zero Boolean reification variables.
        delta_off = sde_total_min - target_min
        ending_off = starting_solde_min + sde_total_min - target_min
        if monthly_delta_coeff > 0 or ending_solde_coeff > 0 or breach_coeff > 0:
            cost_vals: list[int] = []
            for u_val in range(min_u, max_u + 1):
                d_abs = abs(u_val * coeff_gcd + delta_off)
                e_abs = abs(u_val * coeff_gcd + ending_off)
                e_breach = max(0, e_abs - corridor_min)
                cost_vals.append(
                    monthly_delta_coeff * d_abs
                    + ending_solde_coeff * e_abs
                    + breach_coeff * e_breach
                )

            min_cost = min(cost_vals)
            max_cost = max(cost_vals)
            if min_cost == max_cost:
                obj_constant_offset += min_cost
            else:
                # Shift by min_cost and factor delta GCD so LP coefficients stay compact.
                shifted_vals = [v - min_cost for v in cost_vals]
                cost_gcd = math.gcd(*(v for v in shifted_vals if v > 0))
                scaled_vals = [v // cost_gcd for v in shifted_vals]
                obj_constant_offset += min_cost
                emp_cost = model.new_int_var(0, max(scaled_vals), f"emp_cost_{e_idx}")
                prev_slope: int | None = None
                for offset in range(len(scaled_vals) - 1):
                    slope = scaled_vals[offset + 1] - scaled_vals[offset]
                    if slope != prev_slope:
                        u_k = min_u + offset
                        model.add(emp_cost >= scaled_vals[offset] + slope * (u_var - u_k))
                        prev_slope = slope
                obj_vars.append(emp_cost)
                obj_coeffs.append(cost_gcd)

    # Redundant global shift-duration conservation cut linking employee hours to duration counts.
    if not hard_infeasible and u_vars_all and dur_vars:
        global_gcd = math.gcd(*u_gcds_all, *dur_vars.keys())
        dur_count_vars: list[Any] = []
        dur_count_coeffs: list[int] = []
        for dur, d_vars in sorted(dur_vars.items()):
            dc_var = model.new_int_var(0, dur_max_hc[dur], f"dur_cnt_{dur}")
            model.add(dc_var == cp_model.LinearExpr.sum(d_vars))
            dur_count_vars.append(dc_var)
            dur_count_coeffs.append(dur // global_gcd)
        model.add(
            cp_model.LinearExpr.weighted_sum(u_vars_all, [g // global_gcd for g in u_gcds_all])
            == cp_model.LinearExpr.weighted_sum(dur_count_vars, dur_count_coeffs)
        )

    if hard_infeasible:
        model.add_bool_or([])

    # 7. Multi-term integer objective normalized by GCD for clean LP conditioning.
    objective_scale = 1
    has_objective = bool(obj_vars)
    if obj_vars:
        objective_scale = math.gcd(*(abs(c) for c in obj_coeffs))
        scaled_coeffs = [c // objective_scale for c in obj_coeffs]
        model.minimize(cp_model.LinearExpr.weighted_sum(obj_vars, scaled_coeffs))

    # 8. Execute CP-SAT solver with deterministic seed and wall-clock timeout (NFR-001, NFR-002).
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = float(problem.options.timeout_sec)
    solver.parameters.random_seed = problem.options.random_seed
    solver.parameters.num_search_workers = problem.options.num_search_workers
    solver.parameters.linearization_level = 2
    solver.parameters.relative_gap_limit = 0.01

    cp_status = solver.solve(model)
    duration_ms = max(0, round((perf_counter() - start_time) * 1000))

    if cp_status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        out_status = (
            SolverStatus.OPTIMAL if cp_status == cp_model.OPTIMAL else SolverStatus.FEASIBLE
        )
        solution = _extract_solution(
            problem,
            ctx,
            solver,
            x,
            objective_scale=objective_scale,
            objective_offset=obj_constant_offset,
            has_objective=has_objective,
        )
        return SolverOutput(
            period_id=problem.period_id,
            status=out_status,
            solve_duration_ms=duration_ms,
            solutions=(solution,),
            break_warnings=ctx.break_warnings,
        )

    if cp_status == cp_model.INFEASIBLE:
        return SolverOutput(
            period_id=problem.period_id,
            status=SolverStatus.INFEASIBLE,
            solve_duration_ms=duration_ms,
            conflict_cards=(_build_basic_infeasible_card(problem),),
            break_warnings=ctx.break_warnings,
        )

    if cp_status == cp_model.UNKNOWN:
        return SolverOutput(
            period_id=problem.period_id,
            status=SolverStatus.TIMEOUT,
            solve_duration_ms=duration_ms,
            break_warnings=ctx.break_warnings,
        )

    return SolverOutput(
        period_id=problem.period_id,
        status=SolverStatus.ERROR,
        solve_duration_ms=duration_ms,
        break_warnings=ctx.break_warnings,
        error_message=f"CP-SAT returned unexpected status: {solver.status_name(cp_status)}",
    )
