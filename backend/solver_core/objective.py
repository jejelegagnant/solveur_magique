"""Soft-objective weight configuration for the CP-SAT solver."""

from __future__ import annotations

from pydantic import Field

from solver_core.schemas.common import StrictBaseModel

__all__ = ["ObjectiveWeights"]


class ObjectiveWeights(StrictBaseModel):
    """Integer weights for the multi-term CP-SAT soft objective.

    Covers coverage target shortfalls, pouliste open slots, hour-balance corridor
    and cumulative solde drift, soft wishes, pin churn, and surplus doublure
    (FR-009, FR-013, FR-019, FR-020, FR-029, FR-031).
    """

    pouliste_gap_penalty: int = Field(default=10_000, ge=0)
    corridor_breach_penalty: int = Field(default=5_000, ge=0)
    hour_balance_drift_penalty: int = Field(default=100, ge=0)
    soft_wish_low_weight: int = Field(default=10, ge=0)
    soft_wish_medium_weight: int = Field(default=30, ge=0)
    soft_wish_high_weight: int = Field(default=80, ge=0)
    pin_churn_penalty: int = Field(default=25, ge=0)
    surplus_doublure_penalty: int = Field(default=500, ge=0)
    target_shortfall_penalty: int = Field(default=300, ge=0)
    ending_solde_drift_penalty: int = Field(default=150, ge=0)
