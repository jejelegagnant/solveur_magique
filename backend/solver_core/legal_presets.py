"""Canonical Swiss labor law preset builders (FR-022 to FR-026)."""

from __future__ import annotations

from datetime import time
from decimal import Decimal

from solver_core.schemas.common import LegalPresetType
from solver_core.schemas.legal import LegalRuleSet


def build_preset(preset_type: LegalPresetType) -> LegalRuleSet:
    """Return canonical Swiss legal parameters for a built-in preset (FR-022).

    Raises ValueError for LegalPresetType.CUSTOM_CCT because custom collective
    agreement parameters must be supplied explicitly.
    """
    if preset_type == LegalPresetType.LTR_45:
        return LegalRuleSet(
            preset_type=LegalPresetType.LTR_45,
            max_weekly_hours=Decimal("45.0"),
            min_daily_rest_h=Decimal("11.0"),
            min_reduced_rest_h=None,
            reduced_rest_avg_window_days=None,
            reduced_rest_min_avg_h=None,
            max_daily_span_h=Decimal("14.0"),
            max_daily_work_h=Decimal("12.5"),
            max_consecutive_days=6,
            min_weekly_rest_days=1,
            sunday_comp_rest_threshold_h=Decimal("5.0"),
            sunday_comp_rest_h=Decimal("35.0"),
            min_free_sundays_year=26,
            night_window_start=time(23, 0),
            night_window_end=time(6, 0),
            night_bonus_pct=Decimal("10.0"),
        )

    if preset_type == LegalPresetType.LTR_50:
        return LegalRuleSet(
            preset_type=LegalPresetType.LTR_50,
            max_weekly_hours=Decimal("50.0"),
            min_daily_rest_h=Decimal("11.0"),
            min_reduced_rest_h=None,
            reduced_rest_avg_window_days=None,
            reduced_rest_min_avg_h=None,
            max_daily_span_h=Decimal("14.0"),
            max_daily_work_h=Decimal("12.5"),
            max_consecutive_days=6,
            min_weekly_rest_days=1,
            sunday_comp_rest_threshold_h=Decimal("5.0"),
            sunday_comp_rest_h=Decimal("35.0"),
            min_free_sundays_year=26,
            night_window_start=time(23, 0),
            night_window_end=time(6, 0),
            night_bonus_pct=Decimal("10.0"),
        )

    if preset_type == LegalPresetType.OLT2_CARE:
        return LegalRuleSet(
            preset_type=LegalPresetType.OLT2_CARE,
            max_weekly_hours=Decimal("50.0"),
            min_daily_rest_h=Decimal("11.0"),
            min_reduced_rest_h=Decimal("9.0"),
            reduced_rest_avg_window_days=14,
            reduced_rest_min_avg_h=Decimal("12.0"),
            max_daily_span_h=Decimal("14.0"),
            max_daily_work_h=Decimal("12.5"),
            max_consecutive_days=7,
            min_weekly_rest_days=1,
            sunday_comp_rest_threshold_h=Decimal("5.0"),
            sunday_comp_rest_h=Decimal("35.0"),
            min_free_sundays_year=12,
            night_window_start=time(23, 0),
            night_window_end=time(6, 0),
            night_bonus_pct=Decimal("10.0"),
        )

    if preset_type == LegalPresetType.LGAV:
        return LegalRuleSet(
            preset_type=LegalPresetType.LGAV,
            max_weekly_hours=Decimal("42.0"),
            min_daily_rest_h=Decimal("11.0"),
            min_reduced_rest_h=None,
            reduced_rest_avg_window_days=None,
            reduced_rest_min_avg_h=None,
            max_daily_span_h=Decimal("14.0"),
            max_daily_work_h=Decimal("12.5"),
            max_consecutive_days=6,
            min_weekly_rest_days=2,
            sunday_comp_rest_threshold_h=Decimal("5.0"),
            sunday_comp_rest_h=Decimal("35.0"),
            min_free_sundays_year=12,
            night_window_start=time(23, 0),
            night_window_end=time(6, 0),
            night_bonus_pct=Decimal("10.0"),
        )

    if preset_type == LegalPresetType.CUSTOM_CCT:
        msg = "custom_cct preset requires explicit LegalRuleSet parameters."
        raise ValueError(msg)

    msg = f"Unsupported legal preset type: {preset_type!r}."
    raise ValueError(msg)
