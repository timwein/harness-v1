"""
rubric_system - Core modules for the rubric generation-verification loop.

Canonical data models: rubric_system.models
Canonical harness: rubric_harness (top-level)

All models re-exported here for convenience:
    from rubric_system import Rubric, Criterion, LoopResult
"""

from rubric_system.models import (
    ScoringMethod,
    SubAttribute,
    ScoringRubric,
    SubScore,
    CriterionScore,
    Criterion,
    Rubric,
    Iteration,
    LoopResult,
    DocumentScore,
    ScoredRubricRecord,
    CriterionStats,
    FileScore,
    CIResult,
)

__all__ = [
    "ScoringMethod",
    "SubAttribute",
    "ScoringRubric",
    "SubScore",
    "CriterionScore",
    "Criterion",
    "Rubric",
    "Iteration",
    "LoopResult",
    "DocumentScore",
    "ScoredRubricRecord",
    "CriterionStats",
    "FileScore",
    "CIResult",
]
