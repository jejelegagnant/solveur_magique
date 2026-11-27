"""Availability requests, recurring preferences, pinned cells, and prior-draft schemas."""

from __future__ import annotations

from datetime import date
from typing import Literal
from uuid import UUID

from pydantic import Field, model_validator

from solver_core.schemas.common import (
    PreferenceWeight,
    RequestKind,
    RequestSource,
    StrictBaseModel,
)
from solver_core.schemas.shifts import ShiftSegment


class AvailabilityRequest(StrictBaseModel):
    """Hard availability, vacation, fixed SDE event, or one-off preference (FR-017 to FR-019)."""

    id: UUID
    employee_id: UUID
    request_date: date
    kind: RequestKind
    shift_template_id: UUID | None = None
    custom_interval: ShiftSegment | None = None
    sde_label: str | None = Field(default=None, min_length=1)
    weight: PreferenceWeight = PreferenceWeight.MEDIUM
    source: RequestSource = RequestSource.MANAGER
    approved: bool = True

    @model_validator(mode="after")
    def _validate_kind_fields(self) -> AvailabilityRequest:
        if self.kind == RequestKind.FIXED_SDE:
            if self.custom_interval is None:
                msg = "custom_interval is required when kind is fixed_sde."
                raise ValueError(msg)
            if self.shift_template_id is not None:
                msg = "shift_template_id must be None when kind is fixed_sde."
                raise ValueError(msg)
        else:
            if self.custom_interval is not None:
                msg = "custom_interval is only allowed when kind is fixed_sde."
                raise ValueError(msg)
            if self.sde_label is not None:
                msg = "sde_label is only allowed when kind is fixed_sde."
                raise ValueError(msg)
            if (
                self.kind in (RequestKind.VACATION_V, RequestKind.WEEKEND_BUFFER_X)
                and self.shift_template_id is not None
            ):
                msg = f"shift_template_id must be None when kind is {self.kind.value}."
                raise ValueError(msg)
        return self


class RecurringPreference(StrictBaseModel):
    """Weekly recurring soft preference template (FR-019). Weekday follows ISO 0=Mon..6=Sun."""

    id: UUID
    employee_id: UUID
    weekday: int = Field(ge=0, le=6)
    kind: Literal[RequestKind.SOFT_PREFER, RequestKind.SOFT_AVOID]
    shift_template_id: UUID | None = None
    weight: PreferenceWeight = PreferenceWeight.MEDIUM


class PinnedCell(StrictBaseModel):
    """Immutable manager-locked cell preserved across partial re-solves (FR-029)."""

    employee_id: UUID
    work_date: date
    shift_template_id: UUID | None = None
    is_doublure: bool = False
    is_day_off: bool = False

    @model_validator(mode="after")
    def _validate_pin_exclusivity(self) -> PinnedCell:
        has_shift = self.shift_template_id is not None
        if has_shift == self.is_day_off:
            msg = "Exactly one of shift_template_id or is_day_off=True must be specified."
            raise ValueError(msg)
        if self.is_day_off and self.is_doublure:
            msg = "is_doublure cannot be True when is_day_off is True."
            raise ValueError(msg)
        return self


class PriorDraftAssignment(StrictBaseModel):
    """Previous unlocked draft cell used by the stability penalty during re-solves (FR-029)."""

    employee_id: UUID
    work_date: date
    shift_template_id: UUID | None = None
