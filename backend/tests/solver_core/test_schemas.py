"""Comprehensive unit tests for solver_core Pydantic v2 schemas, legal presets, and stubs."""

from __future__ import annotations

from datetime import UTC, date, time
from decimal import Decimal
from uuid import uuid4

import pytest
from pydantic import ValidationError

from solver_core import (
    AvailabilityRequest,
    ConflictCard,
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
    ObjectiveWeights,
    PinnedCell,
    PoulisteGapOut,
    PriorDayRecord,
    PriorDraftAssignment,
    PriorMonthBoundary,
    RecurringPreference,
    RequestKind,
    ScheduleKPIs,
    ScheduleSolution,
    ShiftAssignmentOut,
    ShiftSegment,
    ShiftTemplate,
    SolverInput,
    SolverOutput,
    SolverStatus,
    build_preset,
    explain_infeasibility,
    solve_schedule,
)

# ---------------------------------------------------------------------------
# Round-trip serialization, properties, and immutability
# ---------------------------------------------------------------------------


def test_solver_input_json_round_trip(tilleuls_solver_input: SolverInput) -> None:
    """Valid SolverInput serializes and deserializes losslessly via JSON."""
    payload = tilleuls_solver_input.model_dump_json()
    restored = SolverInput.model_validate_json(payload)
    assert restored == tilleuls_solver_input
    assert restored.period_start == date(2026, 3, 1)
    assert restored.period_end == date(2026, 3, 31)


def test_solver_output_optimal_json_round_trip(sample_optimal_output: SolverOutput) -> None:
    """Valid optimal SolverOutput round-trips cleanly through JSON."""
    payload = sample_optimal_output.model_dump_json()
    restored = SolverOutput.model_validate_json(payload)
    assert restored == sample_optimal_output


def test_solver_output_infeasible_json_round_trip(
    sample_conflict_card: ConflictCard,
) -> None:
    """Valid infeasible SolverOutput round-trips cleanly through JSON."""
    output = SolverOutput(
        period_id=uuid4(),
        status=SolverStatus.INFEASIBLE,
        solve_duration_ms=85,
        conflict_cards=(sample_conflict_card,),
    )
    restored = SolverOutput.model_validate_json(output.model_dump_json())
    assert restored == output


def test_strict_base_model_immutability(
    tilleuls_solver_input: SolverInput,
    sample_optimal_output: SolverOutput,
) -> None:
    """All schemas inherit frozen=True and reject attribute mutation."""
    mutations: tuple[tuple[object, str, object], ...] = (
        (tilleuls_solver_input, "year_month", "2026-04"),
        (tilleuls_solver_input.employees[0], "display_label", "Mutated"),
        (tilleuls_solver_input.shift_templates[0], "erp_code", "X9"),
        (sample_optimal_output, "status", SolverStatus.ERROR),
    )
    for model, attr, value in mutations:
        with pytest.raises(ValidationError):
            setattr(model, attr, value)


def test_strict_base_model_strips_whitespace() -> None:
    """StrictBaseModel trims leading and trailing whitespace on string fields."""
    emp = EmployeeProfile(
        id=uuid4(),
        display_label="  Soignant Trim  ",
        pensum_pct=Decimal("80.00"),
    )
    assert emp.display_label == "Soignant Trim"


# ---------------------------------------------------------------------------
# nLPD data minimization (FR-014, ADR-006)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "forbidden_field",
    ["medical_reason", "illness_note", "ahv_number", "salary", "email"],
)
def test_nlpd_employee_profile_rejects_forbidden_fields(forbidden_field: str) -> None:
    """EmployeeProfile rejects non-scheduling personal/sensitive fields (nLPD FR-014)."""
    data: dict[str, object] = {
        "id": str(uuid4()),
        "display_label": "Soignant A",
        "pensum_pct": "100.00",
        forbidden_field: "sensitive-value",
    }
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        EmployeeProfile.model_validate(data)


@pytest.mark.parametrize(
    "forbidden_field",
    ["medical_reason", "illness_note", "ahv_number", "salary", "email"],
)
def test_nlpd_availability_request_rejects_forbidden_fields(forbidden_field: str) -> None:
    """AvailabilityRequest rejects medical or PII fields (nLPD FR-014, ADR-006)."""
    data: dict[str, object] = {
        "id": str(uuid4()),
        "employee_id": str(uuid4()),
        "request_date": "2026-03-10",
        "kind": "hard_unavail",
        forbidden_field: "burnout / private info",
    }
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        AvailabilityRequest.model_validate(data)


# ---------------------------------------------------------------------------
# ShiftSegment & ShiftTemplate invariants
# ---------------------------------------------------------------------------


def test_shift_segment_rejects_aware_times() -> None:
    """ShiftSegment requires timezone-naive Europe/Zurich wall times."""
    with pytest.raises(ValidationError, match="timezone-naive"):
        ShiftSegment(start_time=time(7, 0, tzinfo=UTC), end_time=time(15, 0))
    with pytest.raises(ValidationError, match="timezone-naive"):
        ShiftSegment(start_time=time(7, 0), end_time=time(15, 0, tzinfo=UTC))


def test_shift_segment_rejects_equal_start_and_end() -> None:
    """Zero-duration segment with start_time == end_time is invalid."""
    with pytest.raises(ValidationError, match="cannot be equal"):
        ShiftSegment(start_time=time(8, 0), end_time=time(8, 0))


def test_shift_segment_rejects_crosses_midnight_mismatch() -> None:
    """crosses_midnight flag must match whether end_time < start_time."""
    with pytest.raises(ValidationError, match="crosses_midnight must be True"):
        ShiftSegment(start_time=time(22, 0), end_time=time(6, 0), crosses_midnight=False)
    with pytest.raises(ValidationError, match="crosses_midnight must be False"):
        ShiftSegment(start_time=time(7, 0), end_time=time(15, 0), crosses_midnight=True)


def test_shift_template_rejects_overlapping_and_out_of_order_segments() -> None:
    """Split-shift segments must be chronologically ordered with zero overlap."""
    with pytest.raises(ValidationError, match="chronological order with zero overlap"):
        ShiftTemplate(
            id=uuid4(),
            erp_code="BAD1",
            label="Overlapping",
            segments=(
                ShiftSegment(start_time=time(7, 0), end_time=time(12, 0)),
                ShiftSegment(start_time=time(11, 30), end_time=time(16, 0)),
            ),
        )

    with pytest.raises(ValidationError, match="chronological order with zero overlap"):
        ShiftTemplate(
            id=uuid4(),
            erp_code="BAD2",
            label="Out of order",
            segments=(
                ShiftSegment(start_time=time(16, 0), end_time=time(21, 0)),
                ShiftSegment(start_time=time(7, 0), end_time=time(9, 0)),
            ),
        )


def test_shift_template_rejects_non_final_midnight_crossing() -> None:
    """Only the final segment of a ShiftTemplate may cross midnight."""
    with pytest.raises(ValidationError, match="Only the final segment"):
        ShiftTemplate(
            id=uuid4(),
            erp_code="BADN",
            label="Bad night split",
            segments=(
                ShiftSegment(start_time=time(22, 0), end_time=time(2, 0), crosses_midnight=True),
                ShiftSegment(start_time=time(3, 0), end_time=time(6, 0)),
            ),
        )


def test_solver_input_rejects_duplicate_shift_erp_codes_and_ids(
    tilleuls_solver_input: SolverInput,
) -> None:
    """SolverInput enforces unique ShiftTemplate ids and erp_codes."""
    first = tilleuls_solver_input.shift_templates[0]
    dup_code_shift = first.model_copy(update={"id": uuid4()})
    data = tilleuls_solver_input.model_dump()
    data["shift_templates"] = [*data["shift_templates"], dup_code_shift.model_dump()]
    with pytest.raises(ValidationError, match="Duplicate ShiftTemplate erp_code"):
        SolverInput.model_validate(data)

    dup_id_shift = first.model_copy(update={"erp_code": "MC99"})
    data_dup_id = tilleuls_solver_input.model_dump()
    data_dup_id["shift_templates"] = [*data_dup_id["shift_templates"], dup_id_shift.model_dump()]
    with pytest.raises(ValidationError, match="Duplicate ShiftTemplate id"):
        SolverInput.model_validate(data_dup_id)


# ---------------------------------------------------------------------------
# CoverageRule & CoverageMatrix
# ---------------------------------------------------------------------------


def test_coverage_rule_xor_and_headcount_ordering() -> None:
    """CoverageRule enforces XOR(day_type, override_date) and min <= target."""
    sid = uuid4()
    with pytest.raises(ValidationError, match="Exactly one of day_type or override_date"):
        CoverageRule(shift_template_id=sid, min_headcount=1, target_headcount=2)

    with pytest.raises(ValidationError, match="Exactly one of day_type or override_date"):
        CoverageRule(
            shift_template_id=sid,
            day_type=DayType.WEEKDAY,
            override_date=date(2026, 3, 10),
            min_headcount=1,
            target_headcount=2,
        )

    with pytest.raises(ValidationError, match="target_headcount must be greater than or equal"):
        CoverageRule(
            shift_template_id=sid,
            day_type=DayType.WEEKDAY,
            min_headcount=3,
            target_headcount=2,
        )


def test_coverage_matrix_resolve_precedence_and_duplicate_rejection() -> None:
    """CoverageMatrix gives override_date precedence and rejects duplicate keys."""
    sid = uuid4()
    other_sid = uuid4()
    matrix = CoverageMatrix(
        rules=(
            CoverageRule(
                shift_template_id=sid,
                day_type=DayType.SUNDAY,
                min_headcount=1,
                target_headcount=1,
            ),
            CoverageRule(
                shift_template_id=sid,
                override_date=date(2026, 3, 29),
                min_headcount=2,
                target_headcount=3,
            ),
        )
    )
    assert matrix.resolve(sid, date(2026, 3, 29), DayType.SUNDAY) == (2, 3)
    assert matrix.resolve(sid, date(2026, 3, 22), DayType.SUNDAY) == (1, 1)
    assert matrix.resolve(sid, date(2026, 3, 23), DayType.WEEKDAY) == (0, 0)
    assert matrix.resolve(other_sid, date(2026, 3, 29), DayType.SUNDAY) == (0, 0)

    with pytest.raises(ValidationError, match="Duplicate coverage rule"):
        CoverageMatrix(
            rules=(
                CoverageRule(
                    shift_template_id=sid,
                    day_type=DayType.WEEKDAY,
                    min_headcount=1,
                    target_headcount=1,
                ),
                CoverageRule(
                    shift_template_id=sid,
                    day_type=DayType.WEEKDAY,
                    min_headcount=2,
                    target_headcount=2,
                ),
            )
        )

    with pytest.raises(ValidationError, match="Duplicate coverage override"):
        CoverageMatrix(
            rules=(
                CoverageRule(
                    shift_template_id=sid,
                    override_date=date(2026, 3, 15),
                    min_headcount=1,
                    target_headcount=1,
                ),
                CoverageRule(
                    shift_template_id=sid,
                    override_date=date(2026, 3, 15),
                    min_headcount=2,
                    target_headcount=2,
                ),
            )
        )


# ---------------------------------------------------------------------------
# DoublureConfig & EmployeeProfile
# ---------------------------------------------------------------------------


def test_doublure_config_validation() -> None:
    """DoublureConfig requires mentors for trainees, unique mentors, and start <= end."""
    mentor_id = uuid4()
    with pytest.raises(ValidationError, match="mentor_ids must be non-empty"):
        DoublureConfig(is_trainee=True, mentor_ids=())

    with pytest.raises(ValidationError, match="duplicate UUIDs"):
        DoublureConfig(is_trainee=True, mentor_ids=(mentor_id, mentor_id))

    with pytest.raises(ValidationError, match="start_date must be less than or equal"):
        DoublureConfig(
            is_trainee=True,
            mentor_ids=(mentor_id,),
            start_date=date(2026, 3, 20),
            end_date=date(2026, 3, 10),
        )


def test_employee_profile_rejects_self_mentoring() -> None:
    """An employee cannot list their own UUID in doublure.mentor_ids."""
    emp_id = uuid4()
    with pytest.raises(ValidationError, match="cannot be their own doublure mentor"):
        EmployeeProfile(
            id=emp_id,
            display_label="Self Mentor",
            pensum_pct=Decimal("80.00"),
            doublure=DoublureConfig(is_trainee=True, mentor_ids=(emp_id,)),
        )


# ---------------------------------------------------------------------------
# AvailabilityRequest & PinnedCell
# ---------------------------------------------------------------------------


def test_availability_request_fixed_sde_invariants() -> None:
    """fixed_sde requires custom_interval and forbids shift_template_id; non-SDE forbids SDE."""
    emp_id = uuid4()
    shift_id = uuid4()
    interval = ShiftSegment(start_time=time(9, 0), end_time=time(11, 0))

    with pytest.raises(ValidationError, match="custom_interval is required"):
        AvailabilityRequest(
            id=uuid4(),
            employee_id=emp_id,
            request_date=date(2026, 3, 12),
            kind=RequestKind.FIXED_SDE,
            sde_label="SDE/9/11",
        )

    with pytest.raises(ValidationError, match="shift_template_id must be None"):
        AvailabilityRequest(
            id=uuid4(),
            employee_id=emp_id,
            request_date=date(2026, 3, 12),
            kind=RequestKind.FIXED_SDE,
            shift_template_id=shift_id,
            custom_interval=interval,
        )

    for non_sde_kind in (
        RequestKind.VACATION_V,
        RequestKind.WEEKEND_BUFFER_X,
        RequestKind.HARD_UNAVAIL,
        RequestKind.SOFT_PREFER,
        RequestKind.SOFT_AVOID,
    ):
        with pytest.raises(ValidationError, match="custom_interval is only allowed"):
            AvailabilityRequest(
                id=uuid4(),
                employee_id=emp_id,
                request_date=date(2026, 3, 12),
                kind=non_sde_kind,
                custom_interval=interval,
            )
        with pytest.raises(ValidationError, match="sde_label is only allowed"):
            AvailabilityRequest(
                id=uuid4(),
                employee_id=emp_id,
                request_date=date(2026, 3, 12),
                kind=non_sde_kind,
                sde_label="SDE/9/11",
            )


def test_pinned_cell_exclusivity_and_doublure_invariants(
    tilleuls_solver_input: SolverInput,
) -> None:
    """PinnedCell enforces XOR(shift_template_id, is_day_off), forbids doublure on day off."""
    emp_id = tilleuls_solver_input.employees[0].id
    shift_id = tilleuls_solver_input.shift_templates[0].id

    with pytest.raises(ValidationError, match="Exactly one of shift_template_id or is_day_off"):
        PinnedCell(employee_id=emp_id, work_date=date(2026, 3, 4))

    with pytest.raises(ValidationError, match="Exactly one of shift_template_id or is_day_off"):
        PinnedCell(
            employee_id=emp_id,
            work_date=date(2026, 3, 4),
            shift_template_id=shift_id,
            is_day_off=True,
        )

    with pytest.raises(ValidationError, match="is_doublure cannot be True"):
        PinnedCell(
            employee_id=emp_id,
            work_date=date(2026, 3, 4),
            is_day_off=True,
            is_doublure=True,
        )

    # Duplicate pin in SolverInput
    dup_pin = tilleuls_solver_input.pinned_cells[0]
    data = tilleuls_solver_input.model_dump()
    data["pinned_cells"] = [*data["pinned_cells"], dup_pin.model_dump()]
    with pytest.raises(ValidationError, match="Duplicate PinnedCell"):
        SolverInput.model_validate(data)


# ---------------------------------------------------------------------------
# PriorDayRecord & PriorMonthBoundary
# ---------------------------------------------------------------------------


def test_prior_day_record_rest_day_invariants() -> None:
    """PriorDayRecord with is_rest_day=True forbids segments, paid_hours > 0, and Sunday flag."""
    emp_id = uuid4()
    with pytest.raises(ValidationError, match="cannot have shift segments"):
        PriorDayRecord(
            employee_id=emp_id,
            work_date=date(2026, 2, 28),
            segments=(ShiftSegment(start_time=time(7, 0), end_time=time(15, 0)),),
            is_rest_day=True,
        )

    with pytest.raises(ValidationError, match="cannot have paid_hours > 0"):
        PriorDayRecord(
            employee_id=emp_id,
            work_date=date(2026, 2, 28),
            paid_hours=Decimal("4.00"),
            is_rest_day=True,
        )

    with pytest.raises(ValidationError, match="cannot have is_sunday_worked_over_5h"):
        PriorDayRecord(
            employee_id=emp_id,
            work_date=date(2026, 2, 22),
            is_rest_day=True,
            is_sunday_worked_over_5h=True,
        )


def test_prior_month_boundary_duplicates_and_bounds(
    tilleuls_solver_input: SolverInput,
) -> None:
    """PriorMonthBoundary rejects duplicate (employee_id, work_date) and out-of-range values."""
    emp_id = tilleuls_solver_input.employees[0].id

    with pytest.raises(ValidationError, match="Duplicate PriorDayRecord"):
        PriorMonthBoundary(
            days=(
                PriorDayRecord(employee_id=emp_id, work_date=date(2026, 2, 27), is_rest_day=True),
                PriorDayRecord(employee_id=emp_id, work_date=date(2026, 2, 27), is_rest_day=True),
            )
        )

    with pytest.raises(ValidationError, match="must be between 0 and 14"):
        PriorMonthBoundary(consecutive_work_days_at_month_end={emp_id: 15})

    with pytest.raises(ValidationError, match="must be >= 0"):
        PriorMonthBoundary(rolling_14d_rest_minutes_by_employee={emp_id: (660, -10)})

    # 8 days prior to 2026-03-01 (2026-02-21) is outside 7-day window [2026-02-22, 2026-02-28].
    too_old = tilleuls_solver_input.model_dump()
    too_old["prior_month_boundary"]["days"] = [
        PriorDayRecord(
            employee_id=emp_id,
            work_date=date(2026, 2, 21),
            is_rest_day=True,
        ).model_dump()
    ]
    with pytest.raises(ValidationError, match="prior 7-day boundary"):
        SolverInput.model_validate(too_old)

    # First day of target month (2026-03-01) is also outside prior boundary.
    in_period = tilleuls_solver_input.model_dump()
    in_period["prior_month_boundary"]["days"] = [
        PriorDayRecord(
            employee_id=emp_id,
            work_date=date(2026, 3, 1),
            is_rest_day=True,
        ).model_dump()
    ]
    with pytest.raises(ValidationError, match="prior 7-day boundary"):
        SolverInput.model_validate(in_period)


# ---------------------------------------------------------------------------
# SolverInput out-of-month dates & foreign-key referential integrity
# ---------------------------------------------------------------------------


def test_solver_input_rejects_out_of_month_dates(tilleuls_solver_input: SolverInput) -> None:
    """Holidays, requests, pins, coverage overrides, and prior drafts must fall in year_month."""
    emp_id = tilleuls_solver_input.employees[0].id
    shift_id = tilleuls_solver_input.shift_templates[0].id

    # Holiday outside 2026-03
    data = tilleuls_solver_input.model_dump()
    data["public_holidays"] = [date(2026, 4, 1)]
    with pytest.raises(ValidationError, match="public_holidays date"):
        SolverInput.model_validate(data)

    # Duplicate holiday
    data_dup_hol = tilleuls_solver_input.model_dump()
    data_dup_hol["public_holidays"] = [date(2026, 3, 19), date(2026, 3, 19)]
    with pytest.raises(ValidationError, match="Duplicate date"):
        SolverInput.model_validate(data_dup_hol)

    # Request outside 2026-03
    data_req = tilleuls_solver_input.model_dump()
    data_req["availability_requests"] = [
        AvailabilityRequest(
            id=uuid4(),
            employee_id=emp_id,
            request_date=date(2026, 2, 28),
            kind=RequestKind.VACATION_V,
        ).model_dump()
    ]
    with pytest.raises(ValidationError, match="outside period"):
        SolverInput.model_validate(data_req)

    # PinnedCell outside 2026-03
    data_pin = tilleuls_solver_input.model_dump()
    data_pin["pinned_cells"] = [
        PinnedCell(
            employee_id=emp_id,
            work_date=date(2026, 4, 2),
            is_day_off=True,
        ).model_dump()
    ]
    with pytest.raises(ValidationError, match="PinnedCell date"):
        SolverInput.model_validate(data_pin)

    # CoverageRule override_date outside 2026-03
    data_cov = tilleuls_solver_input.model_dump()
    data_cov["coverage_matrix"] = CoverageMatrix(
        rules=(
            CoverageRule(
                shift_template_id=shift_id,
                override_date=date(2026, 4, 1),
                min_headcount=1,
                target_headcount=1,
            ),
        )
    ).model_dump()
    with pytest.raises(ValidationError, match="CoverageRule override_date"):
        SolverInput.model_validate(data_cov)

    # PriorDraftAssignment outside 2026-03
    data_draft = tilleuls_solver_input.model_dump()
    data_draft["prior_draft_assignments"] = [
        PriorDraftAssignment(
            employee_id=emp_id,
            work_date=date(2026, 2, 28),
            shift_template_id=shift_id,
        ).model_dump()
    ]
    with pytest.raises(ValidationError, match="PriorDraftAssignment date"):
        SolverInput.model_validate(data_draft)

    # Duplicate PriorDraftAssignment
    data_dup_draft = tilleuls_solver_input.model_dump()
    draft_item = PriorDraftAssignment(
        employee_id=emp_id,
        work_date=date(2026, 3, 2),
        shift_template_id=shift_id,
    ).model_dump()
    data_dup_draft["prior_draft_assignments"] = [draft_item, draft_item]
    with pytest.raises(ValidationError, match="Duplicate PriorDraftAssignment"):
        SolverInput.model_validate(data_dup_draft)


def test_solver_input_rejects_unknown_foreign_uuids(tilleuls_solver_input: SolverInput) -> None:
    """All employee_id, shift_template_id, and mentor_id references must exist in SolverInput."""
    unknown_id = uuid4()
    emp_id = tilleuls_solver_input.employees[0].id
    shift_id = tilleuls_solver_input.shift_templates[0].id

    # Unknown qualified_shift_id on employee
    d1 = tilleuls_solver_input.model_dump()
    d1["employees"][0]["qualified_shift_ids"] = [unknown_id]
    with pytest.raises(ValidationError, match="unknown qualified_shift_id"):
        SolverInput.model_validate(d1)

    # Unknown mentor_id on doublure
    d2 = tilleuls_solver_input.model_dump()
    d2["employees"][2]["doublure"]["mentor_ids"] = [unknown_id]
    with pytest.raises(ValidationError, match="unknown mentor_id"):
        SolverInput.model_validate(d2)

    # Unknown shift_template_id in coverage rule
    d3 = tilleuls_solver_input.model_dump()
    d3["coverage_matrix"]["rules"] = [
        CoverageRule(
            shift_template_id=unknown_id,
            day_type=DayType.WEEKDAY,
            min_headcount=1,
            target_headcount=1,
        ).model_dump()
    ]
    with pytest.raises(ValidationError, match="unknown shift_template_id"):
        SolverInput.model_validate(d3)

    # Unknown employee_id in AvailabilityRequest
    d4 = tilleuls_solver_input.model_dump()
    d4["availability_requests"] = [
        AvailabilityRequest(
            id=uuid4(),
            employee_id=unknown_id,
            request_date=date(2026, 3, 10),
            kind=RequestKind.VACATION_V,
        ).model_dump()
    ]
    with pytest.raises(ValidationError, match="unknown employee"):
        SolverInput.model_validate(d4)

    # Unknown shift_template_id in AvailabilityRequest
    d5 = tilleuls_solver_input.model_dump()
    d5["availability_requests"] = [
        AvailabilityRequest(
            id=uuid4(),
            employee_id=emp_id,
            request_date=date(2026, 3, 10),
            kind=RequestKind.SOFT_PREFER,
            shift_template_id=unknown_id,
        ).model_dump()
    ]
    with pytest.raises(ValidationError, match="unknown shift_template_id"):
        SolverInput.model_validate(d5)

    # Unknown employee_id in RecurringPreference
    d6 = tilleuls_solver_input.model_dump()
    d6["recurring_preferences"] = [
        RecurringPreference(
            id=uuid4(),
            employee_id=unknown_id,
            weekday=1,
            kind=RequestKind.SOFT_AVOID,
            shift_template_id=shift_id,
        ).model_dump()
    ]
    with pytest.raises(ValidationError, match="unknown employee"):
        SolverInput.model_validate(d6)

    # Unknown employee_id in PinnedCell
    d7 = tilleuls_solver_input.model_dump()
    d7["pinned_cells"] = [
        PinnedCell(
            employee_id=unknown_id,
            work_date=date(2026, 3, 5),
            is_day_off=True,
        ).model_dump()
    ]
    with pytest.raises(ValidationError, match="unknown employee"):
        SolverInput.model_validate(d7)

    # Unknown shift_template_id in PriorDraftAssignment
    d8 = tilleuls_solver_input.model_dump()
    d8["prior_draft_assignments"] = [
        PriorDraftAssignment(
            employee_id=emp_id,
            work_date=date(2026, 3, 5),
            shift_template_id=unknown_id,
        ).model_dump()
    ]
    with pytest.raises(ValidationError, match="unknown shift_template_id"):
        SolverInput.model_validate(d8)

    # Unknown employee_id in PriorMonthBoundary
    d9 = tilleuls_solver_input.model_dump()
    d9["prior_month_boundary"]["consecutive_work_days_at_month_end"] = {unknown_id: 2}
    with pytest.raises(ValidationError, match="unknown employee"):
        SolverInput.model_validate(d9)

    d10 = tilleuls_solver_input.model_dump()
    d10["prior_month_boundary"]["rolling_14d_rest_minutes_by_employee"] = {unknown_id: (660,)}
    with pytest.raises(ValidationError, match="unknown employee"):
        SolverInput.model_validate(d10)


# ---------------------------------------------------------------------------
# LegalRuleSet & build_preset()
# ---------------------------------------------------------------------------


def test_legal_rule_set_cross_field_validation() -> None:
    """LegalRuleSet rejects inconsistent work/span, rest, and night-window bounds."""
    with pytest.raises(ValidationError, match="max_daily_work_h must be less than or equal"):
        LegalRuleSet(
            preset_type=LegalPresetType.CUSTOM_CCT,
            max_weekly_hours=Decimal("42.0"),
            max_daily_span_h=Decimal("10.0"),
            max_daily_work_h=Decimal("11.0"),
        )

    with pytest.raises(ValidationError, match="min_reduced_rest_h must be less than or equal"):
        LegalRuleSet(
            preset_type=LegalPresetType.CUSTOM_CCT,
            max_weekly_hours=Decimal("42.0"),
            min_daily_rest_h=Decimal("11.0"),
            min_reduced_rest_h=Decimal("12.0"),
        )

    with pytest.raises(ValidationError, match="cannot be equal"):
        LegalRuleSet(
            preset_type=LegalPresetType.CUSTOM_CCT,
            max_weekly_hours=Decimal("42.0"),
            night_window_start=time(23, 0),
            night_window_end=time(23, 0),
        )

    with pytest.raises(ValidationError, match="timezone-naive"):
        LegalRuleSet(
            preset_type=LegalPresetType.CUSTOM_CCT,
            max_weekly_hours=Decimal("42.0"),
            night_window_start=time(23, 0, tzinfo=UTC),
        )


def test_build_preset_canonical_swiss_rules() -> None:
    """build_preset returns accurate Swiss legal defaults and rejects custom_cct."""
    ltr_45 = build_preset(LegalPresetType.LTR_45)
    assert ltr_45.max_weekly_hours == Decimal("45.0")
    assert ltr_45.min_daily_rest_h == Decimal("11.0")
    assert ltr_45.min_reduced_rest_h is None
    assert ltr_45.max_consecutive_days == 6
    assert ltr_45.min_free_sundays_year == 26
    assert (ltr_45.night_window_start, ltr_45.night_window_end) == (time(23, 0), time(6, 0))

    ltr_50 = build_preset(LegalPresetType.LTR_50)
    assert ltr_50.max_weekly_hours == Decimal("50.0")
    assert ltr_50.max_consecutive_days == 6
    assert ltr_50.min_free_sundays_year == 26

    olt2 = build_preset(LegalPresetType.OLT2_CARE)
    assert olt2.max_weekly_hours == Decimal("50.0")
    assert olt2.min_reduced_rest_h == Decimal("9.0")
    assert olt2.reduced_rest_avg_window_days == 14
    assert olt2.reduced_rest_min_avg_h == Decimal("12.0")
    assert olt2.max_consecutive_days == 7
    assert olt2.min_free_sundays_year == 12

    lgav = build_preset(LegalPresetType.LGAV)
    assert lgav.max_weekly_hours == Decimal("42.0")
    assert lgav.min_weekly_rest_days == 2
    assert lgav.max_consecutive_days == 6
    assert lgav.min_free_sundays_year == 12

    with pytest.raises(ValueError, match="custom_cct preset requires explicit"):
        build_preset(LegalPresetType.CUSTOM_CCT)


# ---------------------------------------------------------------------------
# SolverOutput & output sub-model invariants
# ---------------------------------------------------------------------------


def test_solver_output_status_payload_invariants(
    sample_optimal_output: SolverOutput,
    sample_conflict_card: ConflictCard,
) -> None:
    """SolverOutput enforces strict mutually-exclusive status/payload contracts."""
    pid = uuid4()
    sol = sample_optimal_output.solutions[0]

    # OPTIMAL and FEASIBLE require >= 1 solution, zero conflicts, no error_message
    for ok_status in (SolverStatus.OPTIMAL, SolverStatus.FEASIBLE):
        with pytest.raises(ValidationError, match="must include >= 1 solution"):
            SolverOutput(period_id=pid, status=ok_status, solve_duration_ms=10)
        with pytest.raises(ValidationError, match="must not include conflict_cards"):
            SolverOutput(
                period_id=pid,
                status=ok_status,
                solve_duration_ms=10,
                solutions=(sol,),
                conflict_cards=(sample_conflict_card,),
            )
        with pytest.raises(ValidationError, match="must not include error_message"):
            SolverOutput(
                period_id=pid,
                status=ok_status,
                solve_duration_ms=10,
                solutions=(sol,),
                error_message="unexpected",
            )

    # INFEASIBLE requires empty solutions, >= 1 conflict card, no error_message
    with pytest.raises(ValidationError, match="must include >= 1 conflict card"):
        SolverOutput(period_id=pid, status=SolverStatus.INFEASIBLE, solve_duration_ms=10)
    with pytest.raises(ValidationError, match="must not include solutions"):
        SolverOutput(
            period_id=pid,
            status=SolverStatus.INFEASIBLE,
            solve_duration_ms=10,
            solutions=(sol,),
            conflict_cards=(sample_conflict_card,),
        )
    with pytest.raises(ValidationError, match="must not include error_message"):
        SolverOutput(
            period_id=pid,
            status=SolverStatus.INFEASIBLE,
            solve_duration_ms=10,
            conflict_cards=(sample_conflict_card,),
            error_message="should be none",
        )

    # TIMEOUT requires empty solutions, empty conflicts, no error_message
    timeout_out = SolverOutput(period_id=pid, status=SolverStatus.TIMEOUT, solve_duration_ms=15_000)
    assert timeout_out.status == SolverStatus.TIMEOUT
    with pytest.raises(ValidationError, match="must not include solutions"):
        SolverOutput(
            period_id=pid,
            status=SolverStatus.TIMEOUT,
            solve_duration_ms=15_000,
            solutions=(sol,),
        )

    # ERROR requires non-empty error_message and empty solutions/conflicts
    error_out = SolverOutput(
        period_id=pid,
        status=SolverStatus.ERROR,
        solve_duration_ms=5,
        error_message="Internal CP-SAT failure",
    )
    assert error_out.error_message == "Internal CP-SAT failure"
    with pytest.raises(ValidationError, match="non-empty error_message"):
        SolverOutput(period_id=pid, status=SolverStatus.ERROR, solve_duration_ms=5)
    with pytest.raises(ValidationError, match="must not include solutions"):
        SolverOutput(
            period_id=pid,
            status=SolverStatus.ERROR,
            solve_duration_ms=5,
            solutions=(sol,),
            error_message="boom",
        )


def test_output_submodel_invariants() -> None:
    """PoulisteGapOut, ShiftAssignmentOut, EmployeeSummaryOut, DailyCoverageSummaryOut checks."""
    with pytest.raises(ValidationError):
        PoulisteGapOut(
            work_date=date(2026, 3, 10),
            shift_template_id=uuid4(),
            shift_erp_code="N",
            missing_headcount=0,
        )

    assignment = ShiftAssignmentOut(
        employee_id=uuid4(),
        work_date=date(2026, 3, 10),
        shift_template_id=None,
        cell_code="POULISTE",
    )
    assert assignment.cell_code == "POULISTE"
    assert assignment.paid_hours == Decimal("0.00")

    with pytest.raises(ValidationError, match="preferences_satisfied cannot exceed"):
        EmployeeSummaryOut(
            employee_id=uuid4(),
            target_hours=Decimal("160.00"),
            scheduled_hours=Decimal("160.00"),
            monthly_delta_h=Decimal("0.00"),
            starting_solde_h=Decimal("0.00"),
            ending_solde_h=Decimal("0.00"),
            preferences_satisfied=3,
            preferences_total=2,
        )

    with pytest.raises(ValidationError, match="target_headcount must be greater than or equal"):
        DailyCoverageSummaryOut(
            work_date=date(2026, 3, 10),
            shift_template_id=uuid4(),
            shift_erp_code="MC1",
            min_headcount=2,
            target_headcount=1,
            assigned_headcount=2,
        )

    with pytest.raises(ValidationError):
        ConflictCard(
            conflict_id="c1",
            rule_code="R1",
            title=LocalizedMessage(fr_CH="Titre", de_CH="Titel", en="Title"),
            explanation=LocalizedMessage(fr_CH="Explication", de_CH="Erklaerung", en="Explanation"),
            resolution_hints=(),
        )

    weights = ObjectiveWeights()
    assert weights.pouliste_gap_penalty > weights.corridor_breach_penalty
    assert ScheduleSolution(kpis=ScheduleKPIs()).option_index == 0


# ---------------------------------------------------------------------------
# Entry-point stubs (Issues #3 & #6)
# ---------------------------------------------------------------------------


def test_entry_point_stubs_raise_not_implemented(tilleuls_solver_input: SolverInput) -> None:
    """solve_schedule and explain_infeasibility raise NotImplementedError until Issues #3 & #6."""
    with pytest.raises(NotImplementedError, match="Issue #3"):
        solve_schedule(tilleuls_solver_input)

    with pytest.raises(NotImplementedError, match="Issue #6"):
        explain_infeasibility(tilleuls_solver_input, ["assump_1"], locale=Locale.FR_CH)
