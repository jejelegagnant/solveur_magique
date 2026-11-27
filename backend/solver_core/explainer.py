"""Infeasibility core explainer translating CP-SAT assumptions to i18n cards (Issue #6 stub)."""

from __future__ import annotations

from collections.abc import Sequence

from solver_core.schemas.common import Locale
from solver_core.schemas.input import SolverInput
from solver_core.schemas.output import ConflictCard


def explain_infeasibility(
    problem: SolverInput,
    failed_assumption_ids: Sequence[str],
    *,
    locale: Locale = Locale.FR_CH,
) -> tuple[ConflictCard, ...]:
    """Translate minimal CP-SAT infeasibility assumptions into localized conflict cards (FR-030)."""
    _ = (problem, failed_assumption_ids, locale)
    msg = "Implemented in Issue #6"
    raise NotImplementedError(msg)
