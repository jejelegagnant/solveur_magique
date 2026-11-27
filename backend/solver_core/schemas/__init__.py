"""Public re-exports for all solver_core Pydantic v2 I/O schemas and enums."""

from __future__ import annotations

from solver_core.schemas.common import (
    DayType,
    LegalPresetType,
    Locale,
    LocalizedMessage,
    PreferenceWeight,
    RequestKind,
    RequestSource,
    SolverStatus,
    StrictBaseModel,
    SwissCanton,
)
from solver_core.schemas.input import SolverInput, SolverOptions, TeamContext
from solver_core.schemas.legal import BreakWarning, LegalRuleSet
from solver_core.schemas.output import (
    ConflictCard,
    ConflictResolutionHint,
    DailyCoverageSummaryOut,
    EmployeeSummaryOut,
    PoulisteGapOut,
    ScheduleKPIs,
    ScheduleSolution,
    ShiftAssignmentOut,
    SolverOutput,
)
from solver_core.schemas.requests import (
    AvailabilityRequest,
    PinnedCell,
    PriorDraftAssignment,
    RecurringPreference,
)
from solver_core.schemas.shifts import (
    CoverageMatrix,
    CoverageRule,
    NonShiftCodes,
    ShiftSegment,
    ShiftTemplate,
)
from solver_core.schemas.staff import (
    DoublureConfig,
    EmployeeProfile,
    PriorDayRecord,
    PriorMonthBoundary,
)

__all__ = [
    "AvailabilityRequest",
    "BreakWarning",
    "ConflictCard",
    "ConflictResolutionHint",
    "CoverageMatrix",
    "CoverageRule",
    "DailyCoverageSummaryOut",
    "DayType",
    "DoublureConfig",
    "EmployeeProfile",
    "EmployeeSummaryOut",
    "LegalPresetType",
    "LegalRuleSet",
    "Locale",
    "LocalizedMessage",
    "NonShiftCodes",
    "PinnedCell",
    "PoulisteGapOut",
    "PreferenceWeight",
    "PriorDayRecord",
    "PriorDraftAssignment",
    "PriorMonthBoundary",
    "RecurringPreference",
    "RequestKind",
    "RequestSource",
    "ScheduleKPIs",
    "ScheduleSolution",
    "ShiftAssignmentOut",
    "ShiftSegment",
    "ShiftTemplate",
    "SolverInput",
    "SolverOptions",
    "SolverOutput",
    "SolverStatus",
    "StrictBaseModel",
    "SwissCanton",
    "TeamContext",
]
