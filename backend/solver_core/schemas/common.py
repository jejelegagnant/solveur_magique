"""Shared base models, enums, and localization primitives for solver_core."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class StrictBaseModel(BaseModel):
    """Immutable base model forbidding unknown fields (enforces nLPD FR-014 data minimization)."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        str_strip_whitespace=True,
    )


class Locale(StrEnum):
    """Supported trilingual locales (FR-048)."""

    FR_CH = "fr_CH"
    DE_CH = "de_CH"
    EN = "en"


class SwissCanton(StrEnum):
    """All 26 official two-letter Swiss canton codes (FR-006)."""

    AG = "AG"
    AI = "AI"
    AR = "AR"
    BE = "BE"
    BL = "BL"
    BS = "BS"
    FR = "FR"
    GE = "GE"
    GL = "GL"
    GR = "GR"
    JU = "JU"
    LU = "LU"
    NE = "NE"
    NW = "NW"
    OW = "OW"
    SG = "SG"
    SH = "SH"
    SO = "SO"
    SZ = "SZ"
    TG = "TG"
    TI = "TI"
    UR = "UR"
    VD = "VD"
    VS = "VS"
    ZG = "ZG"
    ZH = "ZH"


class DayType(StrEnum):
    """Calendar day classification for coverage matrices (FR-009)."""

    WEEKDAY = "weekday"
    SATURDAY = "saturday"
    SUNDAY = "sunday"
    HOLIDAY = "holiday"


class RequestKind(StrEnum):
    """Employee availability request and soft-preference categories (FR-017 to FR-019)."""

    VACATION_V = "vacation_v"
    WEEKEND_BUFFER_X = "weekend_buffer_x"
    HARD_UNAVAIL = "hard_unavail"
    FIXED_SDE = "fixed_sde"
    SOFT_PREFER = "soft_prefer"
    SOFT_AVOID = "soft_avoid"


class PreferenceWeight(StrEnum):
    """Priority tier for soft preferences (FR-019)."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class RequestSource(StrEnum):
    """Origin of an availability request (FR-021)."""

    MANAGER = "manager"
    EMPLOYEE_PORTAL = "employee_portal"


class LegalPresetType(StrEnum):
    """Built-in Swiss labor law presets and custom CCT overrides (FR-022, FR-026)."""

    LTR_45 = "ltr_45"
    LTR_50 = "ltr_50"
    OLT2_CARE = "olt2_care"
    LGAV = "lgav"
    CUSTOM_CCT = "custom_cct"


class SolverStatus(StrEnum):
    """Terminal execution status of a CP-SAT solve job (FR-027, FR-030)."""

    OPTIMAL = "optimal"
    FEASIBLE = "feasible"
    INFEASIBLE = "infeasible"
    TIMEOUT = "timeout"
    ERROR = "error"


class LocalizedMessage(StrictBaseModel):
    """Trilingual user-facing message payload (FR-030, FR-048)."""

    fr_CH: str = Field(min_length=1)  # noqa: N815
    de_CH: str = Field(min_length=1)  # noqa: N815
    en: str = Field(min_length=1)
