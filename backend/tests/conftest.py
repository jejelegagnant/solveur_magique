"""Shared pytest fixtures and deterministic Hypothesis profile configuration (NFR-019)."""

from __future__ import annotations

import os
from datetime import date, time
from decimal import Decimal
from uuid import UUID

import pytest
from hypothesis import settings

from solver_core import (
    AvailabilityRequest,
    ConflictCard,
    ConflictResolutionHint,
    CoverageMatrix,
    CoverageRule,
    DailyCoverageSummaryOut,
    DayType,
    DoublureConfig,
    EmployeeProfile,
    EmployeeSummaryOut,
    LegalPresetType,
    LegalRuleSet,
    Locale,
    LocalizedMessage,
    NonShiftCodes,
    PinnedCell,
    PoulisteGapOut,
    PreferenceWeight,
    PriorDayRecord,
    PriorDraftAssignment,
    PriorMonthBoundary,
    RecurringPreference,
    RequestKind,
    RequestSource,
    ScheduleKPIs,
    ScheduleSolution,
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
)

# Register deterministic Hypothesis profiles (NFR-019).
settings.register_profile(
    "default",
    derandomize=True,
    deadline=None,
    max_examples=100,
)
settings.register_profile(
    "ci",
    derandomize=True,
    deadline=None,
    max_examples=200,
)
settings.load_profile(os.getenv("HYPOTHESIS_PROFILE", "default"))

# Deterministic UUID constants for the anonymized Fondation Les Tilleuls unit.
TEAM_ID = UUID("10000000-0000-4000-8000-000000000001")
PERIOD_ID = UUID("10000000-0000-4000-8000-000000000002")

SHIFT_MC1_ID = UUID("20000000-0000-4000-8000-000000000001")
SHIFT_M1_ID = UUID("20000000-0000-4000-8000-000000000002")
SHIFT_N_ID = UUID("20000000-0000-4000-8000-000000000003")

EMP_MENTOR_ID = UUID("30000000-0000-4000-8000-000000000001")
EMP_CAREGIVER_ID = UUID("30000000-0000-4000-8000-000000000002")
EMP_TRAINEE_ID = UUID("30000000-0000-4000-8000-000000000003")

REQ_VACATION_ID = UUID("40000000-0000-4000-8000-000000000001")
REQ_BUFFER_X_ID = UUID("40000000-0000-4000-8000-000000000002")
REQ_SDE_ID = UUID("40000000-0000-4000-8000-000000000003")
REQ_PREFER_ID = UUID("40000000-0000-4000-8000-000000000004")
PREF_RECURRING_ID = UUID("40000000-0000-4000-8000-000000000005")


@pytest.fixture
def shift_mc1() -> ShiftTemplate:
    """Split shift MC1: 07:00-09:00 + 16:00-21:00 (Fondation Les Tilleuls)."""
    return ShiftTemplate(
        id=SHIFT_MC1_ID,
        erp_code="MC1",
        label="Matin-Soir coupe 1",
        segments=(
            ShiftSegment(start_time=time(7, 0), end_time=time(9, 0)),
            ShiftSegment(start_time=time(16, 0), end_time=time(21, 0)),
        ),
        unpaid_break_min=0,
        paid_on_post_break=False,
        paid_duration_h=Decimal("7.00"),
        color_hex="#2563EB",
        is_night_shift=False,
        required_role_tag="soins",
    )


@pytest.fixture
def shift_m1() -> ShiftTemplate:
    """Standard morning shift M1: 07:00-15:30 with 30 min unpaid break."""
    return ShiftTemplate(
        id=SHIFT_M1_ID,
        erp_code="M1",
        label="Matin 1",
        segments=(ShiftSegment(start_time=time(7, 0), end_time=time(15, 30)),),
        unpaid_break_min=30,
        paid_on_post_break=False,
        paid_duration_h=Decimal("8.00"),
        color_hex="#10B981",
        is_night_shift=False,
    )


@pytest.fixture
def shift_night() -> ShiftTemplate:
    """Overnight shift N: 22:00-06:00 crossing midnight with paid on-post break."""
    return ShiftTemplate(
        id=SHIFT_N_ID,
        erp_code="N",
        label="Nuit",
        segments=(
            ShiftSegment(
                start_time=time(22, 0),
                end_time=time(6, 0),
                crosses_midnight=True,
            ),
        ),
        unpaid_break_min=0,
        paid_on_post_break=True,
        paid_duration_h=Decimal("8.00"),
        color_hex="#1E293B",
        is_night_shift=True,
    )


@pytest.fixture
def tilleuls_shifts(
    shift_mc1: ShiftTemplate,
    shift_m1: ShiftTemplate,
    shift_night: ShiftTemplate,
) -> tuple[ShiftTemplate, ...]:
    """Canonical 3-shift catalog for the Fondation Les Tilleuls care unit."""
    return (shift_mc1, shift_m1, shift_night)


@pytest.fixture
def tilleuls_employees() -> tuple[EmployeeProfile, ...]:
    """Anonymized 3-person Swiss care team with doublure trainee/mentor pairing."""
    mentor = EmployeeProfile(
        id=EMP_MENTOR_ID,
        display_label="Soignant A",
        erp_employee_code="EMP001",
        pensum_pct=Decimal("100.00"),
        base_fulltime_weekly_h=Decimal("42.00"),
        corridor_h=Decimal("10.00"),
        current_solde_h=Decimal("2.50"),
        rolling_equity_score=Decimal("0.92"),
        qualified_shift_ids=(SHIFT_MC1_ID, SHIFT_M1_ID, SHIFT_N_ID),
        role_tags=("soins", "referent"),
        free_sundays_ytd=3,
    )
    caregiver = EmployeeProfile(
        id=EMP_CAREGIVER_ID,
        display_label="Soignant B",
        erp_employee_code="EMP002",
        pensum_pct=Decimal("80.00"),
        current_solde_h=Decimal("-1.25"),
        rolling_equity_score=Decimal("0.85"),
        qualified_shift_ids=(SHIFT_MC1_ID, SHIFT_M1_ID, SHIFT_N_ID),
        role_tags=("soins",),
        free_sundays_ytd=4,
    )
    trainee = EmployeeProfile(
        id=EMP_TRAINEE_ID,
        display_label="Stagiaire C",
        erp_employee_code="EMP003",
        pensum_pct=Decimal("60.00"),
        current_solde_h=Decimal("0.00"),
        rolling_equity_score=Decimal("1.00"),
        qualified_shift_ids=(SHIFT_MC1_ID, SHIFT_M1_ID),
        role_tags=("soins", "stagiaire"),
        doublure=DoublureConfig(
            is_trainee=True,
            mentor_ids=(EMP_MENTOR_ID,),
            start_date=date(2026, 3, 1),
            end_date=date(2026, 3, 15),
            counts_toward_solo_coverage=False,
            allow_surplus_hours_completion=True,
        ),
        free_sundays_ytd=5,
    )
    return (mentor, caregiver, trainee)


@pytest.fixture
def tilleuls_team() -> TeamContext:
    """Fondation Les Tilleuls team context in canton Vaud (VD)."""
    return TeamContext(
        team_id=TEAM_ID,
        name="Fondation Les Tilleuls - Unite A",
        canton_code=SwissCanton.VD,
        base_fulltime_weekly_h=Decimal("42.00"),
        default_corridor_h=Decimal("10.00"),
        auto_vacation_weekend_buffer=True,
        non_shift_codes=NonShiftCodes(
            vacation_code="V",
            rest_code="X",
            unavailable_code="ABS",
            pouliste_code="POULISTE",
            sde_prefix="SDE",
        ),
        locale=Locale.FR_CH,
    )


@pytest.fixture
def olt2_rules() -> LegalRuleSet:
    """Standard OLT 2 care-sector legal rule set."""
    return build_preset(LegalPresetType.OLT2_CARE)


@pytest.fixture
def tilleuls_coverage() -> CoverageMatrix:
    """Coverage matrix with weekday/weekend defaults and a specific date override."""
    return CoverageMatrix(
        rules=(
            CoverageRule(
                shift_template_id=SHIFT_MC1_ID,
                day_type=DayType.WEEKDAY,
                min_headcount=1,
                target_headcount=2,
            ),
            CoverageRule(
                shift_template_id=SHIFT_MC1_ID,
                day_type=DayType.SATURDAY,
                min_headcount=1,
                target_headcount=1,
            ),
            CoverageRule(
                shift_template_id=SHIFT_MC1_ID,
                day_type=DayType.SUNDAY,
                min_headcount=1,
                target_headcount=1,
            ),
            CoverageRule(
                shift_template_id=SHIFT_MC1_ID,
                override_date=date(2026, 3, 29),
                min_headcount=2,
                target_headcount=2,
            ),
            CoverageRule(
                shift_template_id=SHIFT_N_ID,
                day_type=DayType.WEEKDAY,
                min_headcount=1,
                target_headcount=1,
            ),
        )
    )


@pytest.fixture
def tilleuls_prior_boundary() -> PriorMonthBoundary:
    """7-day prior-month boundary (2026-02-22..2026-02-28) for March 2026."""
    return PriorMonthBoundary(
        days=(
            PriorDayRecord(
                employee_id=EMP_MENTOR_ID,
                work_date=date(2026, 2, 22),
                shift_template_id=SHIFT_MC1_ID,
                segments=(
                    ShiftSegment(start_time=time(7, 0), end_time=time(9, 0)),
                    ShiftSegment(start_time=time(16, 0), end_time=time(21, 0)),
                ),
                paid_hours=Decimal("7.00"),
                is_rest_day=False,
                is_sunday_worked_over_5h=True,
            ),
            PriorDayRecord(
                employee_id=EMP_MENTOR_ID,
                work_date=date(2026, 2, 28),
                shift_template_id=SHIFT_N_ID,
                segments=(
                    ShiftSegment(
                        start_time=time(22, 0),
                        end_time=time(6, 0),
                        crosses_midnight=True,
                    ),
                ),
                paid_hours=Decimal("8.00"),
                is_rest_day=False,
                is_sunday_worked_over_5h=False,
            ),
            PriorDayRecord(
                employee_id=EMP_CAREGIVER_ID,
                work_date=date(2026, 2, 28),
                shift_template_id=None,
                segments=(),
                paid_hours=Decimal("0.00"),
                is_rest_day=True,
                is_sunday_worked_over_5h=False,
            ),
        ),
        consecutive_work_days_at_month_end={
            EMP_MENTOR_ID: 4,
            EMP_CAREGIVER_ID: 0,
            EMP_TRAINEE_ID: 2,
        },
        rolling_14d_rest_minutes_by_employee={
            EMP_MENTOR_ID: (660, 720, 600, 780),
            EMP_CAREGIVER_ID: (720, 720),
        },
    )


@pytest.fixture
def tilleuls_solver_input(
    tilleuls_team: TeamContext,
    olt2_rules: LegalRuleSet,
    tilleuls_shifts: tuple[ShiftTemplate, ...],
    tilleuls_coverage: CoverageMatrix,
    tilleuls_employees: tuple[EmployeeProfile, ...],
    tilleuls_prior_boundary: PriorMonthBoundary,
) -> SolverInput:
    """Complete valid March 2026 SolverInput snapshot for Fondation Les Tilleuls."""
    return SolverInput(
        period_id=PERIOD_ID,
        year_month="2026-03",
        team=tilleuls_team,
        legal_rules=olt2_rules,
        shift_templates=tilleuls_shifts,
        coverage_matrix=tilleuls_coverage,
        employees=tilleuls_employees,
        availability_requests=(
            AvailabilityRequest(
                id=REQ_VACATION_ID,
                employee_id=EMP_CAREGIVER_ID,
                request_date=date(2026, 3, 9),
                kind=RequestKind.VACATION_V,
                source=RequestSource.MANAGER,
                approved=True,
            ),
            AvailabilityRequest(
                id=REQ_BUFFER_X_ID,
                employee_id=EMP_CAREGIVER_ID,
                request_date=date(2026, 3, 8),
                kind=RequestKind.WEEKEND_BUFFER_X,
                source=RequestSource.MANAGER,
                approved=True,
            ),
            AvailabilityRequest(
                id=REQ_SDE_ID,
                employee_id=EMP_MENTOR_ID,
                request_date=date(2026, 3, 12),
                kind=RequestKind.FIXED_SDE,
                custom_interval=ShiftSegment(start_time=time(9, 0), end_time=time(11, 0)),
                sde_label="SDE/9/11",
                source=RequestSource.MANAGER,
                approved=True,
            ),
            AvailabilityRequest(
                id=REQ_PREFER_ID,
                employee_id=EMP_TRAINEE_ID,
                request_date=date(2026, 3, 5),
                kind=RequestKind.SOFT_PREFER,
                shift_template_id=SHIFT_MC1_ID,
                weight=PreferenceWeight.HIGH,
                source=RequestSource.EMPLOYEE_PORTAL,
                approved=True,
            ),
        ),
        recurring_preferences=(
            RecurringPreference(
                id=PREF_RECURRING_ID,
                employee_id=EMP_CAREGIVER_ID,
                weekday=2,
                kind=RequestKind.SOFT_AVOID,
                shift_template_id=SHIFT_N_ID,
                weight=PreferenceWeight.MEDIUM,
            ),
        ),
        pinned_cells=(
            PinnedCell(
                employee_id=EMP_MENTOR_ID,
                work_date=date(2026, 3, 2),
                shift_template_id=SHIFT_MC1_ID,
                is_doublure=False,
                is_day_off=False,
            ),
            PinnedCell(
                employee_id=EMP_CAREGIVER_ID,
                work_date=date(2026, 3, 3),
                shift_template_id=None,
                is_doublure=False,
                is_day_off=True,
            ),
        ),
        prior_draft_assignments=(
            PriorDraftAssignment(
                employee_id=EMP_MENTOR_ID,
                work_date=date(2026, 3, 2),
                shift_template_id=SHIFT_MC1_ID,
            ),
        ),
        prior_month_boundary=tilleuls_prior_boundary,
        public_holidays=(date(2026, 3, 19),),
        options=SolverOptions(
            timeout_sec=15,
            allow_pouliste=True,
            num_alternatives=2,
            random_seed=42,
            num_search_workers=1,
            enable_rolling_equity=True,
            stability_weight=10,
            locale=Locale.FR_CH,
        ),
    )


@pytest.fixture
def sample_optimal_output() -> SolverOutput:
    """Valid optimal SolverOutput containing assignments, a POULISTE gap, and summaries."""
    solution = ScheduleSolution(
        option_index=0,
        assignments=(
            ShiftAssignmentOut(
                employee_id=EMP_MENTOR_ID,
                work_date=date(2026, 3, 2),
                shift_template_id=SHIFT_MC1_ID,
                cell_code="MC1",
                is_pinned=True,
                is_doublure=False,
                is_sde=False,
                paid_hours=Decimal("7.00"),
                night_supplement_hours=Decimal("0.00"),
            ),
            ShiftAssignmentOut(
                employee_id=EMP_TRAINEE_ID,
                work_date=date(2026, 3, 2),
                shift_template_id=SHIFT_MC1_ID,
                cell_code="MC1",
                is_pinned=False,
                is_doublure=True,
                is_sde=False,
                paid_hours=Decimal("7.00"),
                night_supplement_hours=Decimal("0.00"),
                satisfied_preference_ids=(REQ_PREFER_ID,),
            ),
            ShiftAssignmentOut(
                employee_id=EMP_MENTOR_ID,
                work_date=date(2026, 3, 12),
                shift_template_id=None,
                cell_code="SDE/9/11",
                is_pinned=False,
                is_doublure=False,
                is_sde=True,
                paid_hours=Decimal("2.00"),
                night_supplement_hours=Decimal("0.00"),
            ),
        ),
        pouliste_gaps=(
            PoulisteGapOut(
                work_date=date(2026, 3, 29),
                shift_template_id=SHIFT_N_ID,
                shift_erp_code="N",
                missing_headcount=1,
                reason=LocalizedMessage(
                    fr_CH="Poste de nuit non couvert (POULISTE requis)",
                    de_CH="Nachtschicht unbesetzt (Springer erforderlich)",
                    en="Uncovered night shift (replacement pool required)",
                ),
            ),
        ),
        employee_summaries=(
            EmployeeSummaryOut(
                employee_id=EMP_MENTOR_ID,
                target_hours=Decimal("168.00"),
                scheduled_hours=Decimal("166.00"),
                night_supplement_hours=Decimal("1.60"),
                monthly_delta_h=Decimal("-2.00"),
                starting_solde_h=Decimal("2.50"),
                ending_solde_h=Decimal("0.50"),
                corridor_breached=False,
                sundays_worked=2,
                free_sundays_in_period=3,
                preferences_satisfied=1,
                preferences_total=1,
                satisfaction_rate_pct=Decimal("100.00"),
            ),
        ),
        daily_coverage=(
            DailyCoverageSummaryOut(
                work_date=date(2026, 3, 29),
                shift_template_id=SHIFT_N_ID,
                shift_erp_code="N",
                min_headcount=1,
                target_headcount=1,
                assigned_headcount=0,
                pouliste_gaps=1,
            ),
        ),
        kpis=ScheduleKPIs(
            objective_value=Decimal("10025.00"),
            total_pouliste_gaps=1,
            wish_satisfaction_pct=Decimal("100.00"),
            max_abs_delta_h=Decimal("2.00"),
            corridor_breach_count=0,
            pin_churn_count=0,
            total_scheduled_hours=Decimal("166.00"),
            total_night_supplement_hours=Decimal("1.60"),
        ),
    )
    return SolverOutput(
        period_id=PERIOD_ID,
        status=SolverStatus.OPTIMAL,
        solve_duration_ms=245,
        solutions=(solution,),
    )


@pytest.fixture
def sample_conflict_card() -> ConflictCard:
    """Valid localized infeasibility ConflictCard."""
    return ConflictCard(
        conflict_id="conf-2026-03-29-n",
        rule_code="COVERAGE_MIN_UNMET",
        title=LocalizedMessage(
            fr_CH="Couverture minimale impossible le 29 mars",
            de_CH="Mindestbesetzung am 29. Maerz nicht erreichbar",
            en="Minimum coverage impossible on March 29",
        ),
        explanation=LocalizedMessage(
            fr_CH="Aucun soignant disponible ne respecte le repos minimal OLT 2.",
            de_CH="Keine verfuegbare Pflegeperson erfuellt die ArGV-2-Ruhezeit.",
            en="No available caregiver satisfies the OLT 2 minimum daily rest.",
        ),
        affected_dates=(date(2026, 3, 29),),
        affected_employee_ids=(EMP_MENTOR_ID, EMP_CAREGIVER_ID),
        affected_shift_template_ids=(SHIFT_N_ID,),
        resolution_hints=(
            ConflictResolutionHint(
                action_code="ENABLE_POULISTE",
                label=LocalizedMessage(
                    fr_CH="Autoriser un poste POULISTE",
                    de_CH="Springereinsatz zulassen",
                    en="Allow a replacement pool gap",
                ),
                target_dates=(date(2026, 3, 29),),
                target_shift_template_ids=(SHIFT_N_ID,),
            ),
        ),
    )
