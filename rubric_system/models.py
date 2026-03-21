#!/usr/bin/env python3
"""
Rubric System - Canonical Data Models

All data models for the rubric generation-verification loop system.
Imported by rubric_harness, scoring_engine, rubric_claude_code, rubric_ci, etc.
"""

from dataclasses import dataclass, field
from typing import Optional
from enum import Enum


# ============================================================================
# Scoring Models
# ============================================================================

class ScoringMethod(Enum):
    """How to calculate points for a criterion."""
    BINARY = "binary"
    PERCENTAGE = "percentage"
    WEIGHTED_COMPONENTS = "weighted_components"
    PENALTY_BASED = "penalty_based"
    THRESHOLD_TIERS = "threshold_tiers"
    COUNT_BASED = "count_based"


@dataclass
class SubAttribute:
    """A measurable component within a criterion."""
    sub_id: str
    description: str
    weight: float  # 0.0-1.0
    measurement: str
    thresholds: dict = field(default_factory=dict)


@dataclass
class ScoringRubric:
    """Defines how to score a criterion."""
    method: ScoringMethod
    max_points: int
    sub_attributes: list[SubAttribute] = field(default_factory=list)
    penalties: dict = field(default_factory=dict)
    tiers: dict = field(default_factory=dict)
    points_per_instance: float = 1.0
    max_instances: int = 10


@dataclass
class SubScore:
    """Score for a sub-attribute."""
    sub_id: str
    raw_value: float
    weighted_value: float
    evidence: str
    target: float = 0.8
    details: dict = field(default_factory=dict)


@dataclass
class CriterionScore:
    """Complete granular score for a criterion."""
    criterion_id: str
    points_earned: float
    max_points: int
    percentage: float
    sub_scores: list[SubScore] = field(default_factory=list)
    penalties_applied: list[dict] = field(default_factory=list)
    evidence: str = ""
    methodology: str = ""
    improvement_hints: list[str] = field(default_factory=list)
    priority: int = 1


# ============================================================================
# Rubric Models
# ============================================================================

@dataclass
class Criterion:
    """Criterion with granular scoring configuration."""
    id: str
    category: str
    description: str
    pass_condition: str
    scoring: ScoringRubric = field(default_factory=lambda: ScoringRubric(
        method=ScoringMethod.BINARY,
        max_points=3
    ))
    source: str = "generated"
    pass_examples: list[str] = field(default_factory=list)
    fail_examples: list[str] = field(default_factory=list)
    domain: str = ""


@dataclass
class Rubric:
    task: str
    domain: str
    criteria: list[Criterion]
    total_points: int = 0
    pass_threshold: float = 0.85


# ============================================================================
# Loop Models
# ============================================================================

@dataclass
class Iteration:
    number: int
    attempt: str
    total_score: float
    max_score: int
    percentage: float
    criterion_scores: list[CriterionScore]
    focus_areas: list[str] = field(default_factory=list)


@dataclass
class LoopResult:
    success: bool
    output: str
    iterations: int
    final_score: float
    final_percentage: float
    rubric: Rubric
    history: list[Iteration]
    improvement_summary: list[str] = field(default_factory=list)


# ============================================================================
# Document Scoring Models
# ============================================================================

@dataclass
class DocumentScore:
    """Complete score for a document/artifact."""
    total_points: float
    max_points: int
    percentage: float
    criterion_scores: list[CriterionScore]
    passed: bool
    pass_threshold: float
    top_improvements: list[str] = field(default_factory=list)
    critical_failures: list[str] = field(default_factory=list)


# ============================================================================
# Learning Models
# ============================================================================

@dataclass
class ScoredRubricRecord:
    """A scored rubric with outcome tracking."""
    id: str
    task: str
    task_hash: str
    template_id: Optional[str]
    criteria: list[dict]
    scores: list[dict]
    overall_score: float
    outcome: Optional[str]
    outcome_details: Optional[str]
    days_to_bug: Optional[int]
    created_at: str
    project: Optional[str]
    author: Optional[str]
    iteration_count: int


@dataclass
class CriterionStats:
    """Statistics for a single criterion type."""
    criterion_id: str
    description: str
    times_used: int
    times_passed: int
    times_failed: int
    pass_then_bug: int
    fail_then_bug: int
    pass_then_success: int
    fail_then_success: int

    @property
    def pass_rate(self) -> float:
        return self.times_passed / self.times_used if self.times_used > 0 else 0

    @property
    def bug_prevention_rate(self) -> float:
        total_bugs = self.pass_then_bug + self.fail_then_bug
        if total_bugs == 0:
            return 0
        return self.fail_then_bug / total_bugs

    @property
    def false_positive_rate(self) -> float:
        if self.times_failed == 0:
            return 0
        return self.fail_then_success / self.times_failed

    @property
    def predictive_value(self) -> float:
        if self.times_used < 10:
            return 0.5
        true_positives = self.fail_then_bug
        true_negatives = self.pass_then_success
        false_positives = self.fail_then_success
        false_negatives = self.pass_then_bug
        total = true_positives + true_negatives + false_positives + false_negatives
        if total == 0:
            return 0.5
        return (true_positives + true_negatives) / total


# ============================================================================
# CI Models
# ============================================================================

@dataclass
class FileScore:
    """Score for a single file in CI."""
    path: str
    score: float
    passed: bool
    criteria_passed: int
    criteria_total: int
    critical_passed: bool
    details: list[dict]
    is_new_file: bool


@dataclass
class CIResult:
    """Overall CI check result."""
    passed: bool
    status: str  # "success", "warning", "failure"
    file_scores: list[FileScore]
    summary: str
    details_url: Optional[str] = None
