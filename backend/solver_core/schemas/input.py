"""Root SolverInput problem snapshot, TeamContext, and SolverOptions schemas."""

from __future__ import annotations

import calendar
from datetime import date, timedelta
from decimal import Decimal
from uuid import UUID

from pydantic import Field, model_validator

from solver_core.schemas.common import Locale, StrictBaseModel, SwissCanton
from solver_core.schemas.legal import LegalRuleSet
from solver_core.schemas.requests import (
    AvailabilityRequest,
    PinnedCell,
    PriorDraftAssignment,
    RecurringPreference,
)
from solver_core.schemas.shifts import CoverageMatrix, NonShiftCodes, ShiftTemplate
from solver_core.schemas.staff import EmployeeProfile, PriorMonthBoundary


def _parse_year_month_bounds(year_month: str) -> tuple[date, date]:
    year_str, month_str = year_month.split("-")
    year = int(year_str)
    month = int(month_str)
    last_day = calendar.monthrange(year, month)[1]
    return date(year, month, 1), date(year, month, last_day)


class TeamContext(StrictBaseModel):
    """Team-level scheduling parameters and cantonal configuration (FR-006, FR-010, FR-013)."""

    team_id: UUID
    name: str = Field(min_length=1)
    canton_code: SwissCanton
    base_fulltime_weekly_h: Decimal = Field(
        default=Decimal("42.00"),
        gt=Decimal("0"),
        le=Decimal("50.0"),
    )
    default_corridor_h: Decimal = Field(default=Decimal("10.00"), ge=Decimal("0"))
    auto_vacation_weekend_buffer: bool = True
    non_shift_codes: NonShiftCodes = Field(default_factory=NonShiftCodes)
    locale: Locale = Locale.FR_CH


class SolverOptions(StrictBaseModel):
    """Execution guardrails and optimization switches for a solve job (FR-027 to FR-033)."""

    timeout_sec: int = Field(default=15, ge=1, le=300)
    allow_pouliste: bool = True
    num_alternatives: int = Field(default=1, ge=1, le=3)
    random_seed: int = Field(default=42, ge=0)
    num_search_workers: int = Field(default=1, ge=1, le=16)
    enable_rolling_equity: bool = True
    stability_weight: int = Field(default=10, ge=0)
    locale: Locale = Locale.FR_CH


class SolverInput(StrictBaseModel):
    """Complete immutable input snapshot passed into pure-Python solver_core (NFR-020)."""

    period_id: UUID
    year_month: str = Field(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")
    team: TeamContext
    legal_rules: LegalRuleSet
    shift_templates: tuple[ShiftTemplate, ...] = Field(min_length=1)
    coverage_matrix: CoverageMatrix = Field(default_factory=CoverageMatrix)
    employees: tuple[EmployeeProfile, ...] = Field(min_length=1)
    availability_requests: tuple[AvailabilityRequest, ...] = ()
    recurring_preferences: tuple[RecurringPreference, ...] = ()
    pinned_cells: tuple[PinnedCell, ...] = ()
    prior_draft_assignments: tuple[PriorDraftAssignment, ...] = ()
    prior_month_boundary: PriorMonthBoundary = Field(default_factory=PriorMonthBoundary)
    public_holidays: tuple[date, ...] = ()
    options: SolverOptions = Field(default_factory=SolverOptions)

    @property
    def period_start(self) -> date:
        """First calendar date of the scheduling period."""
        return _parse_year_month_bounds(self.year_month)[0]

    @property
    def period_end(self) -> date:
        """Last calendar date of the scheduling period."""
        return _parse_year_month_bounds(self.year_month)[1]

    @model_validator(mode="after")
    def _validate_integrity(self) -> SolverInput:
        p_start, p_end = _parse_year_month_bounds(self.year_month)
        prior_start = p_start - timedelta(days=7)
        prior_end = p_start - timedelta(days=1)

        shift_ids = self._validate_shifts()
        employee_ids = self._validate_employees(shift_ids)
        self._validate_coverage(shift_ids, p_start, p_end)
        self._validate_requests(employee_ids, shift_ids, p_start, p_end)
        self._validate_recurring_preferences(employee_ids, shift_ids)
        self._validate_pinned_cells(employee_ids, shift_ids, p_start, p_end)
        self._validate_prior_drafts(employee_ids, shift_ids, p_start, p_end)
        self._validate_prior_boundary(employee_ids, shift_ids, prior_start, prior_end)
        self._validate_public_holidays(p_start, p_end)
        return self

    def _validate_shifts(self) -> set[UUID]:
        shift_ids: set[UUID] = set()
        erp_codes: set[str] = set()
        for shift in self.shift_templates:
            if shift.id in shift_ids:
                msg = f"Duplicate ShiftTemplate id: {shift.id}."
                raise ValueError(msg)
            if shift.erp_code in erp_codes:
                msg = f"Duplicate ShiftTemplate erp_code: {shift.erp_code!r}."
                raise ValueError(msg)
            shift_ids.add(shift.id)
            erp_codes.add(shift.erp_code)
        return shift_ids

    def _validate_employees(self, shift_ids: set[UUID]) -> set[UUID]:
        employee_ids: set[UUID] = set()
        for emp in self.employees:
            if emp.id in employee_ids:
                msg = f"Duplicate EmployeeProfile id: {emp.id}."
                raise ValueError(msg)
            employee_ids.add(emp.id)

        for emp in self.employees:
            for sid in emp.qualified_shift_ids:
                if sid not in shift_ids:
                    msg = f"Employee {emp.id} references unknown qualified_shift_id {sid}."
                    raise ValueError(msg)
            if emp.doublure is not None:
                for mentor_id in emp.doublure.mentor_ids:
                    if mentor_id == emp.id:
                        msg = f"Employee {emp.id} cannot be their own doublure mentor."
                        raise ValueError(msg)
                    if mentor_id not in employee_ids:
                        msg = (
                            f"Employee {emp.id} doublure references unknown mentor_id {mentor_id}."
                        )
                        raise ValueError(msg)
        return employee_ids

    def _validate_coverage(
        self,
        shift_ids: set[UUID],
        p_start: date,
        p_end: date,
    ) -> None:
        for rule in self.coverage_matrix.rules:
            if rule.shift_template_id not in shift_ids:
                msg = f"CoverageRule references unknown shift_template_id {rule.shift_template_id}."
                raise ValueError(msg)
            if rule.override_date is not None and not (p_start <= rule.override_date <= p_end):
                msg = (
                    f"CoverageRule override_date {rule.override_date} is outside period "
                    f"[{p_start}, {p_end}]."
                )
                raise ValueError(msg)

    def _validate_requests(
        self,
        employee_ids: set[UUID],
        shift_ids: set[UUID],
        p_start: date,
        p_end: date,
    ) -> None:
        seen_ids: set[UUID] = set()
        for req in self.availability_requests:
            if req.id in seen_ids:
                msg = f"Duplicate AvailabilityRequest id: {req.id}."
                raise ValueError(msg)
            seen_ids.add(req.id)
            if req.employee_id not in employee_ids:
                msg = f"AvailabilityRequest {req.id} references unknown employee {req.employee_id}."
                raise ValueError(msg)
            if req.shift_template_id is not None and req.shift_template_id not in shift_ids:
                msg = (
                    f"AvailabilityRequest {req.id} references unknown shift_template_id "
                    f"{req.shift_template_id}."
                )
                raise ValueError(msg)
            if not (p_start <= req.request_date <= p_end):
                msg = (
                    f"AvailabilityRequest {req.id} date {req.request_date} is outside period "
                    f"[{p_start}, {p_end}]."
                )
                raise ValueError(msg)

    def _validate_recurring_preferences(
        self,
        employee_ids: set[UUID],
        shift_ids: set[UUID],
    ) -> None:
        seen_ids: set[UUID] = set()
        for pref in self.recurring_preferences:
            if pref.id in seen_ids:
                msg = f"Duplicate RecurringPreference id: {pref.id}."
                raise ValueError(msg)
            seen_ids.add(pref.id)
            if pref.employee_id not in employee_ids:
                msg = (
                    f"RecurringPreference {pref.id} references unknown employee {pref.employee_id}."
                )
                raise ValueError(msg)
            if pref.shift_template_id is not None and pref.shift_template_id not in shift_ids:
                msg = (
                    f"RecurringPreference {pref.id} references unknown shift_template_id "
                    f"{pref.shift_template_id}."
                )
                raise ValueError(msg)

    def _validate_pinned_cells(
        self,
        employee_ids: set[UUID],
        shift_ids: set[UUID],
        p_start: date,
        p_end: date,
    ) -> None:
        seen_pins: set[tuple[UUID, date]] = set()
        for pin in self.pinned_cells:
            if pin.employee_id not in employee_ids:
                msg = f"PinnedCell references unknown employee {pin.employee_id}."
                raise ValueError(msg)
            if pin.shift_template_id is not None and pin.shift_template_id not in shift_ids:
                msg = f"PinnedCell references unknown shift_template_id {pin.shift_template_id}."
                raise ValueError(msg)
            if not (p_start <= pin.work_date <= p_end):
                msg = f"PinnedCell date {pin.work_date} is outside period [{p_start}, {p_end}]."
                raise ValueError(msg)
            key = (pin.employee_id, pin.work_date)
            if key in seen_pins:
                msg = f"Duplicate PinnedCell for employee {pin.employee_id} on {pin.work_date}."
                raise ValueError(msg)
            seen_pins.add(key)

    def _validate_prior_drafts(
        self,
        employee_ids: set[UUID],
        shift_ids: set[UUID],
        p_start: date,
        p_end: date,
    ) -> None:
        seen_drafts: set[tuple[UUID, date]] = set()
        for draft in self.prior_draft_assignments:
            if draft.employee_id not in employee_ids:
                msg = f"PriorDraftAssignment references unknown employee {draft.employee_id}."
                raise ValueError(msg)
            if draft.shift_template_id is not None and draft.shift_template_id not in shift_ids:
                msg = (
                    f"PriorDraftAssignment references unknown shift_template_id "
                    f"{draft.shift_template_id}."
                )
                raise ValueError(msg)
            if not (p_start <= draft.work_date <= p_end):
                msg = (
                    f"PriorDraftAssignment date {draft.work_date} is outside period "
                    f"[{p_start}, {p_end}]."
                )
                raise ValueError(msg)
            key = (draft.employee_id, draft.work_date)
            if key in seen_drafts:
                msg = (
                    f"Duplicate PriorDraftAssignment for employee {draft.employee_id} "
                    f"on {draft.work_date}."
                )
                raise ValueError(msg)
            seen_drafts.add(key)

    def _validate_prior_boundary(
        self,
        employee_ids: set[UUID],
        shift_ids: set[UUID],
        prior_start: date,
        prior_end: date,
    ) -> None:
        boundary = self.prior_month_boundary
        for day in boundary.days:
            if day.employee_id not in employee_ids:
                msg = f"PriorDayRecord references unknown employee {day.employee_id}."
                raise ValueError(msg)
            if day.shift_template_id is not None and day.shift_template_id not in shift_ids:
                msg = (
                    f"PriorDayRecord references unknown shift_template_id {day.shift_template_id}."
                )
                raise ValueError(msg)
            if not (prior_start <= day.work_date <= prior_end):
                msg = (
                    f"PriorDayRecord date {day.work_date} must fall within prior 7-day boundary "
                    f"[{prior_start}, {prior_end}]."
                )
                raise ValueError(msg)

        for emp_id in boundary.consecutive_work_days_at_month_end:
            if emp_id not in employee_ids:
                msg = f"consecutive_work_days_at_month_end references unknown employee {emp_id}."
                raise ValueError(msg)

        for emp_id in boundary.rolling_14d_rest_minutes_by_employee:
            if emp_id not in employee_ids:
                msg = f"rolling_14d_rest_minutes_by_employee references unknown employee {emp_id}."
                raise ValueError(msg)

    def _validate_public_holidays(self, p_start: date, p_end: date) -> None:
        seen: set[date] = set()
        for holiday_date in self.public_holidays:
            if not (p_start <= holiday_date <= p_end):
                msg = f"public_holidays date {holiday_date} is outside period [{p_start}, {p_end}]."
                raise ValueError(msg)
            if holiday_date in seen:
                msg = f"Duplicate date {holiday_date} in public_holidays."
                raise ValueError(msg)
            seen.add(holiday_date)
