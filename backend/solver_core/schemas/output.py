"""Solver output schemas: assignments, pouliste gaps, KPIs, and infeasibility conflict cards."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

from pydantic import Field, model_validator

from solver_core.schemas.common import LocalizedMessage, SolverStatus, StrictBaseModel
from solver_core.schemas.legal import BreakWarning


class ShiftAssignmentOut(StrictBaseModel):
    """Single employee-day cell assignment in a solved schedule (FR-027, FR-036)."""

    employee_id: UUID
    work_date: date
    shift_template_id: UUID | None = None
    cell_code: str = Field(min_length=1, max_length=32)
    is_pinned: bool = False
    is_doublure: bool = False
    is_sde: bool = False
    paid_hours: Decimal = Field(default=Decimal("0.00"), ge=Decimal("0.00"))
    night_supplement_hours: Decimal = Field(default=Decimal("0.00"), ge=Decimal("0.00"))
    satisfied_preference_ids: tuple[UUID, ...] = ()
    violated_preference_ids: tuple[UUID, ...] = ()


class PoulisteGapOut(StrictBaseModel):
    """Uncovered shift headcount flagged for external replacement pool workers (FR-031)."""

    work_date: date
    shift_template_id: UUID
    shift_erp_code: str = Field(min_length=1, max_length=16)
    missing_headcount: int = Field(ge=1)
    reason: LocalizedMessage | None = None


class EmployeeSummaryOut(StrictBaseModel):
    """Per-employee monthly hour balance, Sunday count, and preference satisfaction summary."""

    employee_id: UUID
    target_hours: Decimal = Field(ge=Decimal("0.00"))
    scheduled_hours: Decimal = Field(ge=Decimal("0.00"))
    night_supplement_hours: Decimal = Field(default=Decimal("0.00"), ge=Decimal("0.00"))
    monthly_delta_h: Decimal
    starting_solde_h: Decimal
    ending_solde_h: Decimal
    corridor_breached: bool = False
    sundays_worked: int = Field(default=0, ge=0, le=6)
    free_sundays_in_period: int = Field(default=0, ge=0, le=6)
    preferences_satisfied: int = Field(default=0, ge=0)
    preferences_total: int = Field(default=0, ge=0)
    satisfaction_rate_pct: Decimal = Field(
        default=Decimal("100.00"),
        ge=Decimal("0.00"),
        le=Decimal("100.00"),
    )

    @model_validator(mode="after")
    def _validate_preference_counts(self) -> EmployeeSummaryOut:
        if self.preferences_satisfied > self.preferences_total:
            msg = "preferences_satisfied cannot exceed preferences_total."
            raise ValueError(msg)
        return self


class DailyCoverageSummaryOut(StrictBaseModel):
    """Per-day, per-shift coverage fulfillment counter for the matrix footer (FR-035)."""

    work_date: date
    shift_template_id: UUID
    shift_erp_code: str = Field(min_length=1, max_length=16)
    min_headcount: int = Field(ge=0)
    target_headcount: int = Field(ge=0)
    assigned_headcount: int = Field(ge=0)
    pouliste_gaps: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def _validate_headcounts(self) -> DailyCoverageSummaryOut:
        if self.target_headcount < self.min_headcount:
            msg = "target_headcount must be greater than or equal to min_headcount."
            raise ValueError(msg)
        return self


class ScheduleKPIs(StrictBaseModel):
    """Aggregate quality metrics used to compare schedule alternatives (FR-033)."""

    objective_value: Decimal = Decimal("0.00")
    total_pouliste_gaps: int = Field(default=0, ge=0)
    wish_satisfaction_pct: Decimal = Field(
        default=Decimal("100.00"),
        ge=Decimal("0.00"),
        le=Decimal("100.00"),
    )
    max_abs_delta_h: Decimal = Field(default=Decimal("0.00"), ge=Decimal("0.00"))
    corridor_breach_count: int = Field(default=0, ge=0)
    pin_churn_count: int = Field(default=0, ge=0)
    total_scheduled_hours: Decimal = Field(default=Decimal("0.00"), ge=Decimal("0.00"))
    total_night_supplement_hours: Decimal = Field(default=Decimal("0.00"), ge=Decimal("0.00"))


class ConflictResolutionHint(StrictBaseModel):
    """Actionable 1-click resolution suggestion attached to an infeasibility card (FR-030)."""

    action_code: str = Field(min_length=1)
    label: LocalizedMessage
    target_dates: tuple[date, ...] = ()
    target_employee_ids: tuple[UUID, ...] = ()
    target_shift_template_ids: tuple[UUID, ...] = ()


class ConflictCard(StrictBaseModel):
    """Human-readable localized explanation of a minimal CP-SAT infeasibility core (FR-030)."""

    conflict_id: str = Field(min_length=1)
    rule_code: str = Field(min_length=1)
    title: LocalizedMessage
    explanation: LocalizedMessage
    affected_dates: tuple[date, ...] = ()
    affected_employee_ids: tuple[UUID, ...] = ()
    affected_shift_template_ids: tuple[UUID, ...] = ()
    resolution_hints: tuple[ConflictResolutionHint, ...] = Field(min_length=1)


class ScheduleSolution(StrictBaseModel):
    """Single feasible or optimal schedule alternative with KPIs and summaries (FR-033)."""

    option_index: int = Field(default=0, ge=0)
    assignments: tuple[ShiftAssignmentOut, ...] = ()
    pouliste_gaps: tuple[PoulisteGapOut, ...] = ()
    employee_summaries: tuple[EmployeeSummaryOut, ...] = ()
    daily_coverage: tuple[DailyCoverageSummaryOut, ...] = ()
    kpis: ScheduleKPIs


class SolverOutput(StrictBaseModel):
    """Root deterministic output returned by solver_core (FR-027, FR-030, NFR-020)."""

    period_id: UUID
    status: SolverStatus
    solve_duration_ms: int = Field(ge=0)
    solutions: tuple[ScheduleSolution, ...] = ()
    conflict_cards: tuple[ConflictCard, ...] = ()
    break_warnings: tuple[BreakWarning, ...] = ()
    error_message: str | None = None
    solver_version: str = Field(default="0.1.0", min_length=1)

    @model_validator(mode="after")
    def _validate_status_payload_invariants(self) -> SolverOutput:
        if self.status in (SolverStatus.OPTIMAL, SolverStatus.FEASIBLE):
            if not self.solutions:
                msg = f"SolverOutput with status={self.status.value} must include >= 1 solution."
                raise ValueError(msg)
            if self.conflict_cards:
                msg = (
                    f"SolverOutput with status={self.status.value} must not include conflict_cards."
                )
                raise ValueError(msg)
            if self.error_message is not None:
                msg = (
                    f"SolverOutput with status={self.status.value} must not include error_message."
                )
                raise ValueError(msg)
        elif self.status == SolverStatus.INFEASIBLE:
            if self.solutions:
                msg = "SolverOutput with status=infeasible must not include solutions."
                raise ValueError(msg)
            if not self.conflict_cards:
                msg = "SolverOutput with status=infeasible must include >= 1 conflict card."
                raise ValueError(msg)
            if self.error_message is not None:
                msg = "SolverOutput with status=infeasible must not include error_message."
                raise ValueError(msg)
        elif self.status == SolverStatus.TIMEOUT:
            if self.solutions:
                msg = "SolverOutput with status=timeout must not include solutions."
                raise ValueError(msg)
            if self.conflict_cards:
                msg = "SolverOutput with status=timeout must not include conflict_cards."
                raise ValueError(msg)
            if self.error_message is not None:
                msg = "SolverOutput with status=timeout must not include error_message."
                raise ValueError(msg)
        elif self.status == SolverStatus.ERROR:
            if self.solutions:
                msg = "SolverOutput with status=error must not include solutions."
                raise ValueError(msg)
            if self.conflict_cards:
                msg = "SolverOutput with status=error must not include conflict_cards."
                raise ValueError(msg)
            if not self.error_message:
                msg = "SolverOutput with status=error must provide a non-empty error_message."
                raise ValueError(msg)
        return self
