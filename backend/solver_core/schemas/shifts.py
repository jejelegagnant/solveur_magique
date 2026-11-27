"""Shift template, split-shift segment, non-shift code, and coverage schemas."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date, time
from decimal import Decimal
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from solver_core.schemas.common import DayType, StrictBaseModel

_MINUTES_PER_DAY = 24 * 60


def _time_to_minutes(t: time) -> int:
    return t.hour * 60 + t.minute


def validate_segments_chronology(
    segments: Sequence[ShiftSegment],
    *,
    context: str,
) -> None:
    """Validate segments are ordered, non-overlapping, and at most the final crosses midnight."""
    last_idx = len(segments) - 1
    prev_end_min: int | None = None

    for idx, seg in enumerate(segments):
        if seg.crosses_midnight and idx != last_idx:
            msg = f"Only the final segment of a {context} may cross midnight."
            raise ValueError(msg)

        start_min = _time_to_minutes(seg.start_time)
        end_min = _time_to_minutes(seg.end_time) + (_MINUTES_PER_DAY if seg.crosses_midnight else 0)
        if prev_end_min is not None and start_min < prev_end_min:
            msg = f"{context} segments must be in chronological order with zero overlap."
            raise ValueError(msg)
        prev_end_min = end_min


class ShiftSegment(StrictBaseModel):
    """A single continuous work interval in local Europe/Zurich wall time (FR-008)."""

    start_time: time
    end_time: time
    crosses_midnight: bool = False

    @field_validator("start_time", "end_time")
    @classmethod
    def _validate_naive_minute_time(cls, value: time) -> time:
        if value.tzinfo is not None:
            msg = "ShiftSegment times must be timezone-naive local wall times."
            raise ValueError(msg)
        if value.second != 0 or value.microsecond != 0:
            msg = "ShiftSegment times must have minute precision (second=0, microsecond=0)."
            raise ValueError(msg)
        return value

    @model_validator(mode="after")
    def _validate_time_order(self) -> ShiftSegment:
        if self.start_time == self.end_time:
            msg = "ShiftSegment start_time and end_time cannot be equal."
            raise ValueError(msg)
        if self.end_time < self.start_time and not self.crosses_midnight:
            msg = "crosses_midnight must be True when end_time < start_time."
            raise ValueError(msg)
        if self.end_time > self.start_time and self.crosses_midnight:
            msg = "crosses_midnight must be False when end_time > start_time."
            raise ValueError(msg)
        return self


class ShiftTemplate(StrictBaseModel):
    """Reusable discrete shift definition including split shifts (FR-007, FR-008, ADR-002)."""

    id: UUID
    erp_code: str = Field(min_length=1, max_length=16)
    label: str = Field(min_length=1)
    segments: tuple[ShiftSegment, ...] = Field(min_length=1)
    unpaid_break_min: int = Field(default=0, ge=0, le=480)
    paid_on_post_break: bool = False
    paid_duration_h: Decimal | None = Field(default=None, ge=Decimal("0"))
    color_hex: str = Field(default="#3B82F6", pattern=r"^#[0-9A-Fa-f]{6}$")
    is_night_shift: bool = False
    required_role_tag: str | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def _validate_segments_chronology(self) -> ShiftTemplate:
        validate_segments_chronology(self.segments, context="ShiftTemplate")
        nominal_elapsed_min = sum(
            _time_to_minutes(seg.end_time)
            + (_MINUTES_PER_DAY if seg.crosses_midnight else 0)
            - _time_to_minutes(seg.start_time)
            for seg in self.segments
        )
        if self.unpaid_break_min > nominal_elapsed_min:
            msg = (
                f"unpaid_break_min ({self.unpaid_break_min}) cannot exceed nominal shift "
                f"duration ({nominal_elapsed_min} min)."
            )
            raise ValueError(msg)
        return self


class NonShiftCodes(StrictBaseModel):
    """Configurable ERP short codes for non-shift cells and fixed SDE events (FR-010)."""

    vacation_code: str = Field(default="V", min_length=1, max_length=16)
    rest_code: str = Field(default="X", min_length=1, max_length=16)
    unavailable_code: str = Field(default="ABS", min_length=1, max_length=16)
    pouliste_code: str = Field(default="POULISTE", min_length=1, max_length=16)
    sde_prefix: str = Field(default="SDE", min_length=1, max_length=16)


class CoverageRule(StrictBaseModel):
    """Minimum and target headcount requirement for a shift on a day type or specific date."""

    shift_template_id: UUID
    day_type: DayType | None = None
    override_date: date | None = None
    min_headcount: int = Field(ge=0)
    target_headcount: int = Field(ge=0)

    @model_validator(mode="after")
    def _validate_rule(self) -> CoverageRule:
        if (self.day_type is None) == (self.override_date is None):
            msg = "Exactly one of day_type or override_date must be specified."
            raise ValueError(msg)
        if self.target_headcount < self.min_headcount:
            msg = "target_headcount must be greater than or equal to min_headcount."
            raise ValueError(msg)
        return self


class CoverageMatrix(StrictBaseModel):
    """Complete team coverage matrix with deterministic day-type / date-override lookup (FR-009)."""

    rules: tuple[CoverageRule, ...] = ()

    @model_validator(mode="after")
    def _validate_no_duplicates(self) -> CoverageMatrix:
        seen_day_types: set[tuple[UUID, DayType]] = set()
        seen_overrides: set[tuple[UUID, date]] = set()

        for rule in self.rules:
            if rule.day_type is not None:
                key_dt = (rule.shift_template_id, rule.day_type)
                if key_dt in seen_day_types:
                    msg = (
                        f"Duplicate coverage rule for shift {rule.shift_template_id} "
                        f"on {rule.day_type}."
                    )
                    raise ValueError(msg)
                seen_day_types.add(key_dt)
            elif rule.override_date is not None:
                key_date = (rule.shift_template_id, rule.override_date)
                if key_date in seen_overrides:
                    msg = (
                        f"Duplicate coverage override for shift {rule.shift_template_id} "
                        f"on {rule.override_date}."
                    )
                    raise ValueError(msg)
                seen_overrides.add(key_date)

        return self

    def resolve(
        self,
        shift_template_id: UUID,
        work_date: date,
        day_type: DayType,
    ) -> tuple[int, int]:
        """Resolve (min_headcount, target_headcount), giving override_date precedence."""
        day_type_match: tuple[int, int] | None = None
        for rule in self.rules:
            if rule.shift_template_id != shift_template_id:
                continue
            if rule.override_date == work_date:
                return (rule.min_headcount, rule.target_headcount)
            if rule.day_type == day_type:
                day_type_match = (rule.min_headcount, rule.target_headcount)
        return day_type_match if day_type_match is not None else (0, 0)
