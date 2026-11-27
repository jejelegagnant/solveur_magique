"""CP-SAT model builder entry point (stub for Issue #3)."""

from __future__ import annotations

from solver_core.schemas.input import SolverInput
from solver_core.schemas.output import SolverOutput


def solve_schedule(problem: SolverInput) -> SolverOutput:
    """Build and solve the discrete shift-scheduling CP-SAT model (FR-027)."""
    _ = problem
    msg = "Implemented in Issue #3"
    raise NotImplementedError(msg)
