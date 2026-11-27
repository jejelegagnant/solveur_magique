"""Employee profile, doublure onboarding, and prior-month boundary schemas (FR-012 to FR-016)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from solver_core.schemas.common import StrictBaseModel
from solver_core.schemas.shifts import ShiftSegment, validate_segments_chronology


class DoublureConfig(StrictBaseModel):
    """Onboarding trainee/mentor pairing configuration (FR-015, FR-016)."""

    is_trainee: bool = False
    mentor_ids: tuple[UUID, ...] = ()
    start_date: date | None = None
    end_date: date | None = None
    counts_toward_solo_coverage: bool = False
    allow_surplus_hours_completion: bool = False

    @model_validator(mode="after")
    def _validate_doublure(self) -> DoublureConfig:
        if len(set(self.mentor_ids)) != len(self.mentor_ids):
            msg = "mentor_ids must not contain duplicate UUIDs."
            raise ValueError(msg)
        if self.is_trainee and not self.mentor_ids:
            msg = "mentor_ids must be non-empty when is_trainee is True."
            raise ValueError(msg)
        if (
            self.start_date is not None
            and self.end_date is not None
            and self.start_date > self.end_date
        ):
            msg = "doublure start_date must be less than or equal to end_date."
            raise ValueError(msg)
        return self


class EmployeeProfile(StrictBaseModel):
    """Scheduling-only staff profile enforcing nLPD Art. 5 let. c data minimization (FR-014).

    Intentionally excludes email, medical/absence reasons, salary, and AHV/AVS identifiers.
    """

    id: UUID
    display_label: str = Field(min_length=1)
    erp_employee_code: str | None = None
    pensum_pct: Decimal = Field(ge=Decimal("5.00"), le=Decimal("100.00"))
    base_fulltime_weekly_h: Decimal | None = Field(
        default=None,
        gt=Decimal("0"),
        le=Decimal("50.0"),
    )
    corridor_h: Decimal | None = Field(default=None, ge=Decimal("0"))
    current_solde_h: Decimal = Decimal("0.00")
    rolling_equity_score: Decimal = Field(
        default=Decimal("1.00"),
        ge=Decimal("0.00"),
        le=Decimal("1.00"),
    )
    qualified_shift_ids: tuple[UUID, ...] = ()
    role_tags: tuple[str, ...] = ()
    doublure: DoublureConfig | None = None
    free_sundays_ytd: int = Field(default=0, ge=0, le=53)

    @model_validator(mode="after")
    def _validate_no_self_mentoring(self) -> EmployeeProfile:
        if self.doublure is not None and self.id in self.doublure.mentor_ids:
            msg = f"Employee {self.id} cannot be their own doublure mentor."
            raise ValueError(msg)
        return self


class PriorDayRecord(StrictBaseModel):
    """Fixed historical shift or rest record from the final 7 days of the prior month (FR-028)."""

    employee_id: UUID
    work_date: date
    shift_template_id: UUID | None = None
    segments: tuple[ShiftSegment, ...] = ()
    paid_hours: Decimal = Field(default=Decimal("0.00"), ge=Decimal("0.00"))
    is_rest_day: bool = False
    is_sunday_worked_over_5h: bool = False

    @model_validator(mode="after")
    def _validate_rest_day_consistency(self) -> PriorDayRecord:
        if self.is_rest_day:
            if self.segments:
                msg = "PriorDayRecord with is_rest_day=True cannot have shift segments."
                raise ValueError(msg)
            if self.paid_hours > Decimal("0"):
                msg = "PriorDayRecord with is_rest_day=True cannot have paid_hours > 0."
                raise ValueError(msg)
            if self.is_sunday_worked_over_5h:
                msg = "PriorDayRecord with is_rest_day=True cannot have is_sunday_worked_over_5h."
                raise ValueError(msg)
        elif self.segments:
            validate_segments_chronology(self.segments, context="PriorDayRecord")
        return self


class PriorMonthBoundary(StrictBaseModel):
    """Cross-month legal continuity context for rest, streaks, and OLT 2 averaging (FR-028)."""

    days: tuple[PriorDayRecord, ...] = ()
    consecutive_work_days_at_month_end: dict[UUID, int] = Field(default_factory=dict)
    rolling_14d_rest_minutes_by_employee: dict[UUID, tuple[int, ...]] = Field(default_factory=dict)

    @field_validator("consecutive_work_days_at_month_end")
    @classmethod
    def _validate_streaks(cls, value: dict[UUID, int]) -> dict[UUID, int]:
        for emp_id, streak in value.items():
            if not (0 <= streak <= 14):
                msg = (
                    f"consecutive_work_days_at_month_end for {emp_id} must be between 0 and 14, "
                    f"got {streak}."
                )
                raise ValueError(msg)
        return value

    @field_validator("rolling_14d_rest_minutes_by_employee")
    @classmethod
    def _validate_rest_minutes(
        cls,
        value: dict[UUID, tuple[int, ...]],
    ) -> dict[UUID, tuple[int, ...]]:
        for emp_id, rests in value.items():
            if any(minutes < 0 for minutes in rests):
                msg = f"rolling_14d_rest_minutes_by_employee for {emp_id} must be >= 0."
                raise ValueError(msg)
        return value

    @model_validator(mode="after")
    def _validate_unique_days(self) -> PriorMonthBoundary:
        seen: set[tuple[UUID, date]] = set()
        for day in self.days:
            key = (day.employee_id, day.work_date)
            if key in seen:
                msg = f"Duplicate PriorDayRecord for employee {day.employee_id} on {day.work_date}."
                raise ValueError(msg)
            seen.add(key)
        return self
