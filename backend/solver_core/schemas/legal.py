"""Swiss labor law rule set and Art. 15 LTr break warning schemas."""

from __future__ import annotations

from datetime import date, time
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from solver_core.schemas.common import LegalPresetType, StrictBaseModel


class LegalRuleSet(StrictBaseModel):
    """Parameterized Swiss labor law constraints (LTr, OLT 2, L-GAV, custom CCT)."""

    preset_type: LegalPresetType
    max_weekly_hours: Decimal = Field(gt=Decimal("0"), le=Decimal("60.0"))
    min_daily_rest_h: Decimal = Field(default=Decimal("11.0"), gt=Decimal("0"), le=Decimal("24.0"))
    min_reduced_rest_h: Decimal | None = Field(
        default=None,
        gt=Decimal("0"),
        le=Decimal("24.0"),
    )
    reduced_rest_avg_window_days: int | None = Field(default=None, ge=1, le=28)
    reduced_rest_min_avg_h: Decimal | None = Field(
        default=None,
        gt=Decimal("0"),
        le=Decimal("24.0"),
    )
    max_daily_span_h: Decimal = Field(default=Decimal("14.0"), gt=Decimal("0"), le=Decimal("24.0"))
    max_daily_work_h: Decimal = Field(default=Decimal("12.5"), gt=Decimal("0"), le=Decimal("24.0"))
    max_consecutive_days: int = Field(default=6, ge=1, le=7)
    min_weekly_rest_days: int = Field(default=1, ge=1, le=3)
    sunday_comp_rest_threshold_h: Decimal = Field(
        default=Decimal("5.0"),
        ge=Decimal("0"),
        le=Decimal("24.0"),
    )
    sunday_comp_rest_h: Decimal = Field(
        default=Decimal("35.0"),
        ge=Decimal("0"),
        le=Decimal("72.0"),
    )
    min_free_sundays_year: int = Field(default=12, ge=0, le=52)
    night_window_start: time = time(23, 0)
    night_window_end: time = time(6, 0)
    night_bonus_pct: Decimal = Field(
        default=Decimal("10.0"),
        ge=Decimal("0.0"),
        le=Decimal("100.0"),
    )
    effective_from: date | None = None

    @field_validator("night_window_start", "night_window_end")
    @classmethod
    def _validate_naive_night_time(cls, value: time) -> time:
        if value.tzinfo is not None:
            msg = "Night window boundary times must be timezone-naive local wall times."
            raise ValueError(msg)
        if value.second != 0 or value.microsecond != 0:
            msg = (
                "Night window boundary times must have minute precision (second=0, microsecond=0)."
            )
            raise ValueError(msg)
        return value

    @model_validator(mode="after")
    def _validate_legal_consistency(self) -> LegalRuleSet:
        if self.max_daily_work_h > self.max_daily_span_h:
            msg = "max_daily_work_h must be less than or equal to max_daily_span_h."
            raise ValueError(msg)
        if self.min_reduced_rest_h is not None and self.min_reduced_rest_h > self.min_daily_rest_h:
            msg = "min_reduced_rest_h must be less than or equal to min_daily_rest_h."
            raise ValueError(msg)
        has_avg_window = self.reduced_rest_avg_window_days is not None
        has_avg_min = self.reduced_rest_min_avg_h is not None
        if has_avg_window != has_avg_min:
            msg = (
                "reduced_rest_avg_window_days and reduced_rest_min_avg_h "
                "must either both be set or both be None."
            )
            raise ValueError(msg)
        if has_avg_window and self.min_reduced_rest_h is None:
            msg = (
                "min_reduced_rest_h must be set when reduced-rest "
                "averaging parameters are provided."
            )
            raise ValueError(msg)
        if (
            self.min_reduced_rest_h is not None
            and self.reduced_rest_min_avg_h is not None
            and self.reduced_rest_min_avg_h < self.min_reduced_rest_h
        ):
            msg = "reduced_rest_min_avg_h must be greater than or equal to min_reduced_rest_h."
            raise ValueError(msg)
        if self.night_window_start == self.night_window_end:
            msg = "night_window_start and night_window_end cannot be equal."
            raise ValueError(msg)
        return self


class BreakWarning(StrictBaseModel):
    """Non-blocking compliance warning for unmet Art. 15 LTr break thresholds (FR-008)."""

    shift_template_id: UUID | None = None
    work_duration_min: int = Field(ge=0)
    required_break_min: int = Field(ge=0)
    configured_break_min: int = Field(ge=0)
    code: Literal["LTR_BREAK_15M", "LTR_BREAK_30M", "LTR_BREAK_60M"]
