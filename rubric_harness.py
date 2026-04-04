#!/usr/bin/env python3
from __future__ import annotations
"""
Rubric Loop Harness - Generation/Verification Loop with Granular Scoring

Canonical implementation integrating:
1. Domain detection → template loading
2. Learned criteria from history
3. Pass/fail examples for guidance
4. Granular point-based scoring (not binary)
5. Sub-attribute measurement extraction
6. Targeted improvement hints in generation prompts

Usage:
    python rubric_harness.py "Write a research report on AI chip market"
    python rubric_harness.py --task "Analyze Q3 earnings" --context data.csv

As a library:
    from rubric_harness import RubricLoop, LoopResult, Rubric
    loop = RubricLoop()
    result = await loop.run("Write a research brief on AI chips")
"""

import asyncio
import json
import re
import sys
from pathlib import Path
from typing import List, Optional

from rubric_system.models import (
    ScoringMethod,
    SubAttribute,
    ScoringRubric,
    SubScore,
    CriterionScore,
    Criterion,
    Rubric,
    RubricDimension,
    Iteration,
    LoopResult,
    ScoredRubricRecord,
)
from rubric_system.scoring_engine import compute_dimension_scores

try:
    from anthropic import Anthropic, RateLimitError, APIError
    import httpx as _httpx
    _API_TIMEOUT = _httpx.Timeout(600.0, connect=30.0)
except ImportError:
    Anthropic = None
    RateLimitError = None
    APIError = None
    _API_TIMEOUT = None

import time as _time


class ScoringError(Exception):
    """Raised when the scorer fails to produce parseable results after retries."""
    pass


from rubric_system.rubric_learning import RubricStore, RubricLearner
from rubric_system.rubric_store import RubricStore as RubricRAGStore
from rubric_system.self_improve import OutcomeTracker, LearningIntegrator, SelfEditor, RegressionSuite

# Ensure API key is available
import os
from pathlib import Path
if not os.environ.get("ANTHROPIC_API_KEY"):
    for p in [Path(__file__).parent / ".env", Path.home() / ".anthropic" / "api_key"]:
        if p.exists():
            text = p.read_text().strip()
            if "=" in text:
                os.environ["ANTHROPIC_API_KEY"] = text.split("=", 1)[1].strip().strip('"')
            else:
                os.environ["ANTHROPIC_API_KEY"] = text
            break


# ============================================================================
# Pre-built Scoring Rubrics
# ============================================================================

def source_freshness_rubric(max_points: int = 10) -> ScoringRubric:
    return ScoringRubric(
        method=ScoringMethod.WEIGHTED_COMPONENTS,
        max_points=max_points,
        sub_attributes=[
            SubAttribute(
                sub_id="headline_citation_freshness",
                description="Freshness of sources for key/headline claims",
                weight=0.50,
                measurement="% of Tier 1 cited sources within currency threshold"
            ),
            SubAttribute(
                sub_id="supporting_citation_freshness",
                description="Freshness of sources for supporting claims",
                weight=0.30,
                measurement="% of Tier 2-3 cited sources within currency threshold"
            ),
            SubAttribute(
                sub_id="overall_source_freshness",
                description="Freshness of all sources in bibliography",
                weight=0.20,
                measurement="% of all sources within appropriate threshold"
            ),
        ]
    )


def source_authority_rubric(max_points: int = 10) -> ScoringRubric:
    return ScoringRubric(
        method=ScoringMethod.WEIGHTED_COMPONENTS,
        max_points=max_points,
        sub_attributes=[
            SubAttribute(
                sub_id="primary_source_authority",
                description="Authority of sources for key claims",
                weight=0.50,
                measurement="% of key claims backed by peer-reviewed/official sources"
            ),
            SubAttribute(
                sub_id="expert_credentials",
                description="Experts quoted have verifiable credentials",
                weight=0.25,
                measurement="% of expert quotes with stated credentials"
            ),
            SubAttribute(
                sub_id="institutional_reliability",
                description="Sources from accountable institutions",
                weight=0.25,
                measurement="% from established institutions vs blogs/forums"
            ),
        ]
    )


def source_triangulation_rubric(max_points: int = 10) -> ScoringRubric:
    return ScoringRubric(
        method=ScoringMethod.WEIGHTED_COMPONENTS,
        max_points=max_points,
        sub_attributes=[
            SubAttribute(
                sub_id="tier1_triangulation",
                description="Headline claims have 3+ independent sources",
                weight=0.50,
                measurement="% of Tier 1 claims with 3+ independent sources"
            ),
            SubAttribute(
                sub_id="tier2_triangulation",
                description="Supporting claims have 2+ sources",
                weight=0.30,
                measurement="% of Tier 2 claims with 2+ independent sources"
            ),
            SubAttribute(
                sub_id="source_independence",
                description="Sources are genuinely independent",
                weight=0.20,
                measurement="% of source pairs that don't cite each other"
            ),
        ]
    )


def evidence_alignment_rubric(max_points: int = 10) -> ScoringRubric:
    return ScoringRubric(
        method=ScoringMethod.PENALTY_BASED,
        max_points=max_points,
        penalties={
            "unsupported_headline_claim": -3.0,
            "unsupported_supporting_claim": -1.5,
            "weak_evidence_strong_claim": -2.0,
            "citation_drift": -1.0,
            "missing_quantitative_backing": -1.0,
        }
    )


def visualization_accuracy_rubric(max_points: int = 10) -> ScoringRubric:
    return ScoringRubric(
        method=ScoringMethod.PENALTY_BASED,
        max_points=max_points,
        penalties={
            "truncated_axis": -3.0,
            "misleading_scale": -3.0,
            "unlabeled_axis": -2.0,
            "missing_units": -1.5,
            "wrong_chart_type": -2.0,
            "3d_distortion": -1.5,
            "missing_legend": -1.0,
        }
    )


def visualization_clarity_rubric(max_points: int = 10) -> ScoringRubric:
    return ScoringRubric(
        method=ScoringMethod.WEIGHTED_COMPONENTS,
        max_points=max_points,
        sub_attributes=[
            SubAttribute(
                sub_id="declarative_titles",
                description="Chart titles state the takeaway",
                weight=0.30,
                measurement="% of charts with declarative (not descriptive) titles"
            ),
            SubAttribute(
                sub_id="labeling_completeness",
                description="All axes, legends properly labeled",
                weight=0.30,
                measurement="% of charts with complete labeling"
            ),
            SubAttribute(
                sub_id="accessibility",
                description="Color-blind safe, sufficient contrast",
                weight=0.20,
                measurement="% of charts meeting WCAG 2.0 AA"
            ),
            SubAttribute(
                sub_id="data_ink_ratio",
                description="Minimal chartjunk, high data-ink ratio",
                weight=0.20,
                measurement="% of charts without unnecessary decoration"
            ),
        ]
    )


def uncertainty_quantification_rubric(max_points: int = 10) -> ScoringRubric:
    return ScoringRubric(
        method=ScoringMethod.WEIGHTED_COMPONENTS,
        max_points=max_points,
        sub_attributes=[
            SubAttribute(
                sub_id="prediction_labeling",
                description="Predictions clearly labeled as such",
                weight=0.25,
                measurement="% of forward statements with prediction labels"
            ),
            SubAttribute(
                sub_id="confidence_levels",
                description="Confidence levels stated",
                weight=0.25,
                measurement="% of predictions with confidence indicators"
            ),
            SubAttribute(
                sub_id="uncertainty_ranges",
                description="Ranges/scenarios provided",
                weight=0.30,
                measurement="% of quantitative predictions with ranges/CIs"
            ),
            SubAttribute(
                sub_id="assumption_transparency",
                description="Key assumptions explicitly stated",
                weight=0.20,
                measurement="% of predictions with explicit assumptions"
            ),
        ]
    )


def document_structure_rubric(max_points: int = 10) -> ScoringRubric:
    return ScoringRubric(
        method=ScoringMethod.WEIGHTED_COMPONENTS,
        max_points=max_points,
        sub_attributes=[
            SubAttribute(
                sub_id="executive_summary_quality",
                description="BLUF with key findings in first paragraph",
                weight=0.35,
                measurement="Exec summary contains all major conclusions (0-1)"
            ),
            SubAttribute(
                sub_id="logical_flow",
                description="Sections build logically",
                weight=0.35,
                measurement="No circular reasoning, evidence before conclusions (0-1)"
            ),
            SubAttribute(
                sub_id="section_completeness",
                description="All required sections present",
                weight=0.30,
                measurement="% of required sections present and complete"
            ),
        ]
    )


# ============================================================================
# Frontend Design Scoring Rubrics
# ============================================================================

def color_palette_rubric(max_points: int = 10) -> ScoringRubric:
    """Color intentionality and modern palette usage."""
    return ScoringRubric(
        method=ScoringMethod.WEIGHTED_COMPONENTS,
        max_points=max_points,
        sub_attributes=[
            SubAttribute(
                sub_id="color_distinctiveness",
                description="Primary color is distinctive, avoids AI cliché purples",
                weight=0.35,
                measurement="1.0 if no default AI purple (#8B5CF6/#7C3AED/#6366F1) and color is purposeful, 0.0 if cliché"
            ),
            SubAttribute(
                sub_id="palette_harmony",
                description="Follows 60-30-10 rule with semantic meaning",
                weight=0.35,
                measurement="% adherence: dominant-secondary-accent ratios + semantic colors (success/error/warning)"
            ),
            SubAttribute(
                sub_id="palette_restraint",
                description="Maximum 5-6 active colors excluding grays",
                weight=0.30,
                measurement="1.0 if ≤6 active colors, degrade proportionally for excess"
            ),
        ]
    )


def color_contrast_rubric(max_points: int = 10) -> ScoringRubric:
    """WCAG 2.1 AA contrast compliance."""
    return ScoringRubric(
        method=ScoringMethod.WEIGHTED_COMPONENTS,
        max_points=max_points,
        sub_attributes=[
            SubAttribute(
                sub_id="body_text_contrast",
                description="Body text meets 4.5:1 minimum contrast ratio",
                weight=0.40,
                measurement="% of body text meeting 4.5:1 contrast"
            ),
            SubAttribute(
                sub_id="large_text_contrast",
                description="Large text (18px+/14px bold) meets 3:1 ratio",
                weight=0.25,
                measurement="% of large text meeting 3:1 contrast"
            ),
            SubAttribute(
                sub_id="interactive_distinguishability",
                description="Interactive elements clearly distinguishable, info not color-only",
                weight=0.35,
                measurement="% of interactive elements with non-color distinction"
            ),
        ]
    )


def color_modernness_rubric(max_points: int = 8) -> ScoringRubric:
    """Modern color trend application."""
    return ScoringRubric(
        method=ScoringMethod.PENALTY_BASED,
        max_points=max_points,
        penalties={
            "pure_black_on_white": -2.0,
            "saturated_rainbow_gradient": -2.0,
            "default_ai_purple_gradient": -3.0,
            "neon_accents_as_primary": -2.0,
            "saas_hero_gradient": -1.5,
            "cold_stark_white_bg": -1.0,
        }
    )


def typography_hierarchy_rubric(max_points: int = 10) -> ScoringRubric:
    """Clear and consistent typography hierarchy."""
    return ScoringRubric(
        method=ScoringMethod.WEIGHTED_COMPONENTS,
        max_points=max_points,
        sub_attributes=[
            SubAttribute(
                sub_id="heading_distinction",
                description="Clear distinction between H1-H3, body, caption with 1.2-1.5x ratio",
                weight=0.35,
                measurement="% of heading levels with clear size/weight distinction"
            ),
            SubAttribute(
                sub_id="weight_purpose",
                description="Font weight variation used purposefully, not randomly",
                weight=0.25,
                measurement="1.0 if weight choices are systematic, 0.0 if random"
            ),
            SubAttribute(
                sub_id="font_family_discipline",
                description="Maximum 2 font families (ideally 1 with multiple weights)",
                weight=0.20,
                measurement="1.0 if ≤2 families, 0.5 if 3, 0.0 if 4+"
            ),
            SubAttribute(
                sub_id="line_height_consistency",
                description="Line height 1.4-1.6x for body text",
                weight=0.20,
                measurement="% of body text with appropriate line height"
            ),
        ]
    )


def font_choice_rubric(max_points: int = 10) -> ScoringRubric:
    """Modern, readable font selection."""
    return ScoringRubric(
        method=ScoringMethod.WEIGHTED_COMPONENTS,
        max_points=max_points,
        sub_attributes=[
            SubAttribute(
                sub_id="font_modernity",
                description="Uses modern sans-serif (Inter, SF Pro, DM Sans, Satoshi, Geist) or intentional serif",
                weight=0.40,
                measurement="1.0 if intentional modern choice, 0.5 if system default, 0.0 if dated"
            ),
            SubAttribute(
                sub_id="size_readability",
                description="Font renders well at all sizes, 14px minimum for body",
                weight=0.35,
                measurement="% of body text at ≥14px with good rendering"
            ),
            SubAttribute(
                sub_id="character_support",
                description="Supports required character sets, variable fonts preferred",
                weight=0.25,
                measurement="1.0 if variable font with Latin extended, 0.5 if static with basic Latin"
            ),
        ]
    )


def typography_brand_rubric(max_points: int = 8) -> ScoringRubric:
    """Typography feels intentional and branded."""
    return ScoringRubric(
        method=ScoringMethod.WEIGHTED_COMPONENTS,
        max_points=max_points,
        sub_attributes=[
            SubAttribute(
                sub_id="headline_impact",
                description="Headlines make visual impact with bold weights, appropriate size",
                weight=0.35,
                measurement="% of headlines with intentional size/weight for impact"
            ),
            SubAttribute(
                sub_id="letter_spacing_consistency",
                description="Consistent letter-spacing (tighter for headlines, normal for body)",
                weight=0.30,
                measurement="1.0 if systematic tracking, 0.5 if partially consistent, 0.0 if random"
            ),
            SubAttribute(
                sub_id="text_alignment_intent",
                description="Text alignment is intentional (left for reading, center sparingly)",
                weight=0.35,
                measurement="% of text with appropriate alignment for context"
            ),
        ]
    )


def spacing_grid_rubric(max_points: int = 10) -> ScoringRubric:
    """8px grid system adherence."""
    return ScoringRubric(
        method=ScoringMethod.WEIGHTED_COMPONENTS,
        max_points=max_points,
        sub_attributes=[
            SubAttribute(
                sub_id="grid_adherence",
                description="All spacing values are multiples of 8 (4px only for micro)",
                weight=0.50,
                measurement="% of spacing values that are multiples of 8 (or 4 for icon-text gaps)"
            ),
            SubAttribute(
                sub_id="spacing_scale_consistency",
                description="Consistent spacing scale applied throughout",
                weight=0.30,
                measurement="% of components using values from a defined spacing scale"
            ),
            SubAttribute(
                sub_id="padding_margin_grouping",
                description="Internal padding ≤ external margins (Gestalt grouping)",
                weight=0.20,
                measurement="% of container groups where inner padding < outer margin"
            ),
        ]
    )


def spacing_hierarchy_rubric(max_points: int = 10) -> ScoringRubric:
    """Visual hierarchy through spacing."""
    return ScoringRubric(
        method=ScoringMethod.WEIGHTED_COMPONENTS,
        max_points=max_points,
        sub_attributes=[
            SubAttribute(
                sub_id="proximity_grouping",
                description="Related elements grouped closer (8-16px), unrelated separated (24-48px)",
                weight=0.40,
                measurement="% of element groups with appropriate proximity-based spacing"
            ),
            SubAttribute(
                sub_id="section_breathing_room",
                description="Sections have generous breathing room (48-96px)",
                weight=0.30,
                measurement="% of major sections with ≥48px separation"
            ),
            SubAttribute(
                sub_id="whitespace_intention",
                description="White space used intentionally, Gestalt principles applied",
                weight=0.30,
                measurement="1.0 if whitespace feels purposeful, 0.5 if adequate, 0.0 if cramped/lost"
            ),
        ]
    )


def layout_adaptability_rubric(max_points: int = 8) -> ScoringRubric:
    """Layout adapts to content and context."""
    return ScoringRubric(
        method=ScoringMethod.WEIGHTED_COMPONENTS,
        max_points=max_points,
        sub_attributes=[
            SubAttribute(
                sub_id="container_padding_consistency",
                description="Cards/containers have consistent padding (16-24px)",
                weight=0.35,
                measurement="% of containers with consistent internal padding"
            ),
            SubAttribute(
                sub_id="responsive_handling",
                description="Responsive breakpoints handle edge cases",
                weight=0.35,
                measurement="% of layouts that adapt well at standard breakpoints"
            ),
            SubAttribute(
                sub_id="gutter_consistency",
                description="Gutters consistent across similar components",
                weight=0.30,
                measurement="% of component groups with consistent gutters"
            ),
        ]
    )


def interactive_elements_rubric(max_points: int = 8) -> ScoringRubric:
    """Interactive elements are clearly tappable/clickable."""
    return ScoringRubric(
        method=ScoringMethod.PENALTY_BASED,
        max_points=max_points,
        penalties={
            "touch_target_below_44px": -2.5,
            "no_button_affordance": -2.0,
            "missing_hover_focus_active_states": -1.5,
            "invisible_disabled_state": -1.0,
            "links_indistinguishable_from_text": -1.5,
        }
    )


def navigation_rubric(max_points: int = 8) -> ScoringRubric:
    """Navigation is intuitive and consistent."""
    return ScoringRubric(
        method=ScoringMethod.WEIGHTED_COMPONENTS,
        max_points=max_points,
        sub_attributes=[
            SubAttribute(
                sub_id="location_indication",
                description="Current location clearly indicated in nav",
                weight=0.35,
                measurement="1.0 if current page/section always highlighted, 0.0 if ambiguous"
            ),
            SubAttribute(
                sub_id="action_accessibility",
                description="Back/close actions easily accessible, consistent patterns",
                weight=0.35,
                measurement="% of screens with accessible back/close actions"
            ),
            SubAttribute(
                sub_id="nav_consistency",
                description="Consistent navigation patterns across screens",
                weight=0.30,
                measurement="% of screens using the same navigation pattern"
            ),
        ]
    )


def forms_inputs_rubric(max_points: int = 8) -> ScoringRubric:
    """Forms and inputs are user-friendly."""
    return ScoringRubric(
        method=ScoringMethod.PENALTY_BASED,
        max_points=max_points,
        penalties={
            "invisible_input_boundaries": -2.0,
            "placeholder_only_labels": -2.0,
            "unclear_error_states": -1.5,
            "missing_focus_states": -1.5,
            "wrong_keyboard_type_mobile": -1.0,
        }
    )


def visual_consistency_rubric(max_points: int = 6) -> ScoringRubric:
    """Consistent visual language throughout."""
    return ScoringRubric(
        method=ScoringMethod.WEIGHTED_COMPONENTS,
        max_points=max_points,
        sub_attributes=[
            SubAttribute(
                sub_id="border_radius_consistency",
                description="Border radius consistent (system of sharp/rounded/mixed)",
                weight=0.30,
                measurement="% of components following the same border radius system"
            ),
            SubAttribute(
                sub_id="shadow_elevation_system",
                description="Shadow depth follows consistent elevation system",
                weight=0.25,
                measurement="% of elevated elements using consistent shadow scale"
            ),
            SubAttribute(
                sub_id="icon_style_unity",
                description="Icon style unified (outline vs filled, stroke weight)",
                weight=0.25,
                measurement="% of icons sharing same style (outline/filled) and stroke weight"
            ),
            SubAttribute(
                sub_id="no_mixed_metaphors",
                description="No mixed visual metaphors or illustration styles",
                weight=0.20,
                measurement="1.0 if cohesive, 0.5 if minor inconsistencies, 0.0 if mixed"
            ),
        ]
    )


def micro_interactions_rubric(max_points: int = 6) -> ScoringRubric:
    """Micro-interactions and feedback present."""
    return ScoringRubric(
        method=ScoringMethod.WEIGHTED_COMPONENTS,
        max_points=max_points,
        sub_attributes=[
            SubAttribute(
                sub_id="loading_states",
                description="Loading states for async operations",
                weight=0.35,
                measurement="% of async operations with loading indicators"
            ),
            SubAttribute(
                sub_id="action_feedback",
                description="Success/error feedback on user actions",
                weight=0.35,
                measurement="% of user actions with appropriate feedback"
            ),
            SubAttribute(
                sub_id="transition_smoothness",
                description="Transitions are smooth (200-300ms), no jarring state changes",
                weight=0.30,
                measurement="% of state transitions with smooth animation (200-300ms)"
            ),
        ]
    )


def dark_mode_rubric(max_points: int = 6) -> ScoringRubric:
    """Dark mode support quality (when applicable)."""
    return ScoringRubric(
        method=ScoringMethod.WEIGHTED_COMPONENTS,
        max_points=max_points,
        sub_attributes=[
            SubAttribute(
                sub_id="not_just_inverted",
                description="Dark mode is designed, not just inverted colors",
                weight=0.35,
                measurement="1.0 if purposeful dark palette, 0.0 if simple inversion"
            ),
            SubAttribute(
                sub_id="dark_backgrounds",
                description="Uses dark grays not pure black, reduced color saturation",
                weight=0.35,
                measurement="1.0 if off-black bg + desaturated colors, 0.5 if partial, 0.0 if pure black"
            ),
            SubAttribute(
                sub_id="shadow_adaptation",
                description="Shadows become glows or disappear, images remain readable",
                weight=0.30,
                measurement="% of dark mode elements with appropriate shadow/image adaptation"
            ),
        ]
    )


def screen_reader_rubric(max_points: int = 8) -> ScoringRubric:
    """Screen reader compatibility."""
    return ScoringRubric(
        method=ScoringMethod.WEIGHTED_COMPONENTS,
        max_points=max_points,
        sub_attributes=[
            SubAttribute(
                sub_id="semantic_html",
                description="Semantic HTML structure (headings, landmarks, lists)",
                weight=0.30,
                measurement="% of page using appropriate semantic elements"
            ),
            SubAttribute(
                sub_id="alt_text_coverage",
                description="Alt text for meaningful images, ARIA labels for interactive elements",
                weight=0.35,
                measurement="% of meaningful images with alt text + interactive elements with ARIA"
            ),
            SubAttribute(
                sub_id="focus_order_logic",
                description="Focus order is logical, skip links present for nav-heavy pages",
                weight=0.35,
                measurement="1.0 if logical focus order + skip links, 0.5 if order ok but no skip links"
            ),
        ]
    )


def keyboard_motor_rubric(max_points: int = 8) -> ScoringRubric:
    """Keyboard and motor accessibility."""
    return ScoringRubric(
        method=ScoringMethod.PENALTY_BASED,
        max_points=max_points,
        penalties={
            "non_keyboard_accessible_element": -2.0,
            "invisible_focus_indicators": -2.0,
            "keyboard_trap": -3.0,
            "inadequate_click_target_spacing": -1.5,
            "time_limited_without_override": -2.0,
        }
    )


# ============================================================================
# Task-Level Rubric Resolution
# ============================================================================

from dataclasses import dataclass as _dataclass, field as _field
from typing import Callable, Optional


@_dataclass
class RubricSignature:
    """Defines how to match a task string to a rubric builder.

    Each signature has:
    - name: unique key for this rubric type
    - builder: callable(task: str) -> Rubric
    - keywords: high-signal words that strongly indicate this task type
    - anti_keywords: words that indicate this is NOT this task type (negative signal)
    - task_patterns: regex patterns for structural matching
    - example_tasks: canonical examples (used for similarity scoring)
    - priority: tiebreaker — higher wins when scores are close (default 0)
    """
    name: str
    builder: Callable[[str], Rubric]
    keywords: list[str] = _field(default_factory=list)
    anti_keywords: list[str] = _field(default_factory=list)
    task_patterns: list[str] = _field(default_factory=list)
    example_tasks: list[str] = _field(default_factory=list)
    priority: int = 0


class RubricRegistry:
    """Registry of rubric builders with task-level matching.

    Resolution strategy (in order):
    1. Explicit rubric override (caller passes a Rubric directly)
    2. Explicit name lookup (caller passes rubric name string)
    3. Task-level scoring: keyword hits + anti-keyword penalties + pattern matches
    4. Fallback to knowledge_work if nothing scores above threshold

    The scoring is deterministic (no LLM) and transparent — you can inspect
    why a rubric was chosen via resolve_with_explanation().
    """

    def __init__(self):
        self._signatures: dict[str, RubricSignature] = {}
        self._fallback_name: str = "knowledge_work"

    def register(self, sig: RubricSignature) -> None:
        """Register a rubric signature."""
        self._signatures[sig.name] = sig

    def set_fallback(self, name: str) -> None:
        """Set which registered rubric to use as fallback."""
        self._fallback_name = name

    @property
    def registered_names(self) -> list[str]:
        return list(self._signatures.keys())

    def get(self, name: str) -> Optional[RubricSignature]:
        return self._signatures.get(name)

    def resolve(self, task: str, rubric_name: str = None) -> tuple[Rubric, str, float]:
        """Resolve a task string to a Rubric.

        Args:
            task: the task description
            rubric_name: optional explicit rubric name (skips matching)

        Returns:
            (rubric, matched_name, confidence)
        """
        # Path 1: explicit name lookup
        if rubric_name:
            sig = self._signatures.get(rubric_name)
            if sig:
                return sig.builder(task), rubric_name, 1.0
            raise ValueError(
                f"Unknown rubric '{rubric_name}'. Available: {self.registered_names}"
            )

        # Path 2: task-level scoring
        scores = self._score_all(task)

        if scores:
            best_name, best_score = scores[0]
            # Confidence threshold: need at least 2.0 to beat fallback
            if best_score >= 2.0:
                sig = self._signatures[best_name]
                confidence = min(best_score / 8.0, 1.0)  # normalize to 0-1
                return sig.builder(task), best_name, confidence

        # Path 3: fallback
        fallback = self._signatures.get(self._fallback_name)
        if fallback:
            return fallback.builder(task), self._fallback_name, 0.0
        raise ValueError(f"Fallback rubric '{self._fallback_name}' not registered")

    def resolve_with_explanation(self, task: str) -> dict:
        """Resolve and return full scoring breakdown for debugging."""
        scores = self._score_all(task)
        rubric, matched, confidence = self.resolve(task)

        return {
            "task": task,
            "matched": matched,
            "confidence": confidence,
            "rubric_criteria_count": len(rubric.criteria),
            "rubric_max_points": rubric.total_points,
            "all_scores": [
                {"name": name, "score": score, "breakdown": self._score_breakdown(task, name)}
                for name, score in scores
            ],
        }

    def _score_all(self, task: str) -> list[tuple[str, float]]:
        """Score task against all registered signatures. Returns sorted (name, score) pairs."""
        task_lower = task.lower()
        results = []

        for name, sig in self._signatures.items():
            score = self._score_task(task_lower, sig)
            if score > 0:
                results.append((name, score))

        results.sort(key=lambda x: (-x[1], -self._signatures[x[0]].priority))
        return results

    def _score_task(self, task_lower: str, sig: RubricSignature) -> float:
        """Score a task string against a single signature."""
        score = 0.0

        # Keyword hits: +1.0 each (these are high-signal)
        for kw in sig.keywords:
            if kw.lower() in task_lower:
                score += 1.0

        # Anti-keyword penalties: -2.0 each (strong negative signal)
        for akw in sig.anti_keywords:
            if akw.lower() in task_lower:
                score -= 2.0

        # Pattern matches: +1.5 each (structural signal)
        for pattern in sig.task_patterns:
            if re.search(pattern, task_lower, re.I):
                score += 1.5

        # Priority bonus (small tiebreaker)
        score += sig.priority * 0.1

        return max(0.0, score)

    def _score_breakdown(self, task: str, name: str) -> dict:
        """Detailed scoring breakdown for a single signature."""
        sig = self._signatures[name]
        task_lower = task.lower()

        keyword_hits = [kw for kw in sig.keywords if kw.lower() in task_lower]
        anti_hits = [akw for akw in sig.anti_keywords if akw.lower() in task_lower]
        pattern_hits = [p for p in sig.task_patterns if re.search(p, task_lower, re.I)]

        return {
            "keyword_hits": keyword_hits,
            "anti_keyword_hits": anti_hits,
            "pattern_hits": pattern_hits,
            "keyword_score": len(keyword_hits) * 1.0,
            "anti_score": len(anti_hits) * -2.0,
            "pattern_score": len(pattern_hits) * 1.5,
            "priority_bonus": sig.priority * 0.1,
        }


# ============================================================================
# Global Registry — all built-in rubrics registered here
# ============================================================================

REGISTRY = RubricRegistry()


def _register_builtin_rubrics():
    """Register all built-in rubric builders with their task signatures."""

    # --- Knowledge Work / Research (the original) ---
    REGISTRY.register(RubricSignature(
        name="knowledge_work",
        builder=build_knowledge_work_rubric,
        keywords=[
            "research", "report", "analysis", "whitepaper", "brief",
            "document", "study", "paper", "source", "citation",
            "evidence", "literature review", "findings",
        ],
        anti_keywords=["code", "function", "script", "sql", "bash", "api"],
        task_patterns=[
            r"write\s+a\s+(research|report|analysis|brief|memo|document)",
            r"(summarize|analyze|review)\s+.*(data|findings|research|paper)",
        ],
        example_tasks=[
            "Write a research brief on the AI chip market",
            "Analyze Q3 earnings and produce a report",
            "Draft a whitepaper on quantum computing applications",
        ],
        priority=0,  # default fallback, so low priority
    ))

    # --- Frontend Design ---
    REGISTRY.register(RubricSignature(
        name="frontend_design",
        builder=build_frontend_design_rubric,
        keywords=[
            "ui", "ux", "frontend", "landing page", "dashboard",
            "design", "component", "layout", "css", "tailwind",
            "figma", "wireframe", "mockup", "responsive",
        ],
        anti_keywords=["report", "research", "memo", "email"],
        task_patterns=[
            r"(design|build|create)\s+.*(ui|ux|frontend|dashboard|landing|page|app)",
            r"(component|layout|interface)\s+(for|that|with)",
        ],
        example_tasks=[
            "Design a modern dashboard UI for a SaaS app",
            "Create a responsive landing page component",
            "Build a mobile app interface for a finance product",
        ],
        priority=1,
    ))

    # --- Register sample rubrics from rubric_system.sample_rubrics ---
    try:
        from rubric_system.sample_rubrics import SAMPLE_TASKS
        _register_sample_rubrics(SAMPLE_TASKS)
    except ImportError:
        pass  # sample_rubrics not available, skip


def _register_sample_rubrics(sample_tasks: dict):
    """Register sample rubric builders with appropriate task signatures."""

    # Sample rubric builders take 0 args; registry expects builder(task) -> Rubric.
    # Wrap them so the task arg is accepted but unused (task is baked into the rubric).
    def _wrap(builder_fn):
        return lambda task: builder_fn()

    _SAMPLE_SIGNATURES = {
        "cold_outreach_email": RubricSignature(
            name="cold_outreach_email",
            builder=_wrap(sample_tasks["cold_outreach_email"]),
            keywords=[
                "cold email", "outreach", "pitch", "angel",
                "investor email", "fundraising email", "intro email",
            ],
            anti_keywords=["newsletter", "marketing email", "drip"],
            task_patterns=[
                r"(write|draft|compose)\s+.*(cold|outreach|pitch)\s*(email|message)",
                r"(email|message)\s+.*(founder|investor|ceo|vp|cto)",
                r"(angel|seed|series\s*[ab])\s+.*(pitch|investment|outreach)",
            ],
            example_tasks=[
                "Write a cold outreach email to a Series A founder pitching angel investment",
                "Draft a pitch email to a startup CEO for investment",
            ],
            priority=5,  # very specific, should win over generic
        ),

        "csv_parser": RubricSignature(
            name="csv_parser",
            builder=_wrap(sample_tasks["csv_parser"]),
            keywords=[
                "csv", "parser", "parse", "delimiter", "messy data",
                "data cleaning", "missing headers",
            ],
            anti_keywords=["sql", "database", "api"],
            task_patterns=[
                r"(parse|read|clean|handle)\s+.*(csv|tsv|delimited)",
                r"(function|script|code)\s+.*(csv|delimiter|header)",
                r"(messy|inconsistent|broken)\s+.*(data|csv|file)",
            ],
            example_tasks=[
                "Generate a Python function that parses messy CSV data with inconsistent delimiters",
                "Write a CSV parser that handles missing headers",
            ],
            priority=5,
        ),

        "exec_summary": RubricSignature(
            name="exec_summary",
            builder=_wrap(sample_tasks["exec_summary"]),
            keywords=[
                "summarize", "summary", "executive summary", "bullet",
                "tldr", "key takeaways", "condense",
            ],
            anti_keywords=["write", "create", "generate", "design"],
            task_patterns=[
                r"summarize\s+.*(post|article|document|paper|report)",
                r"(executive|exec)\s+summary",
                r"(\d+)[\s-]bullet\s+(summary|takeaway|point)",
                r"(condense|distill)\s+.*(into|to)\s+.*(bullet|point|summary)",
            ],
            example_tasks=[
                "Summarize a 2,000-word technical blog post into a 3-bullet executive summary",
                "Give me 5 key takeaways from this research paper",
            ],
            priority=5,
        ),

        "sql_ltv_query": RubricSignature(
            name="sql_ltv_query",
            builder=_wrap(sample_tasks["sql_ltv_query"]),
            keywords=[
                "sql", "query", "select", "join", "group by",
                "ltv", "lifetime value", "customer value",
                "schema", "database",
            ],
            anti_keywords=["api", "frontend", "email"],
            task_patterns=[
                r"(create|write|build)\s+.*(sql|query|select)",
                r"(find|get|calculate)\s+.*(customer|user|ltv|lifetime|revenue)",
                r"(top|best|highest)\s+\d+\s+.*(customer|user|account)",
            ],
            example_tasks=[
                "Create a SQL query to find the top 10 customers by lifetime value",
                "Write SQL to calculate customer LTV excluding refunds",
            ],
            priority=5,
        ),

        "agi_counterargument": RubricSignature(
            name="agi_counterargument",
            builder=_wrap(sample_tasks["agi_counterargument"]),
            keywords=[
                "counterargument", "counter argument", "argue against",
                "rebuttal", "refute", "push back", "devil's advocate",
                "steelman", "debate",
            ],
            anti_keywords=["code", "sql", "design", "email"],
            task_patterns=[
                r"(write|make|give)\s+.*(counterargument|counter.?argument|rebuttal)",
                r"(argue|push\s*back)\s+(against|that)",
                r"(counter|rebut|challenge)\s+.*(claim|argument|thesis|position)",
            ],
            example_tasks=[
                "Write a counterargument to the claim 'AGI will arrive before 2030'",
                "Argue against the position that remote work reduces productivity",
            ],
            priority=5,
        ),

        "billing_schema": RubricSignature(
            name="billing_schema",
            builder=_wrap(sample_tasks["billing_schema"]),
            keywords=[
                "json schema", "schema", "data model", "billing",
                "pricing", "subscription", "usage-based", "seat-based",
                "multi-tenant", "saas",
            ],
            anti_keywords=["query", "frontend", "email", "report"],
            task_patterns=[
                r"(design|create|define)\s+.*(schema|data\s*model|json)",
                r"(billing|pricing|subscription)\s+.*(system|model|schema)",
                r"(usage|seat|metered)\s*[\-]?\s*based",
            ],
            example_tasks=[
                "Design a JSON schema for a multi-tenant SaaS billing system",
                "Create a data model for subscription billing with usage-based pricing",
            ],
            priority=5,
        ),

        "attention_explanation": RubricSignature(
            name="attention_explanation",
            builder=_wrap(sample_tasks["attention_explanation"]),
            keywords=[
                "explain", "explanation", "teach", "tutorial",
                "how does", "what is", "eli5", "beginner",
                "year-old", "year old", "simple terms",
            ],
            anti_keywords=["code", "implement", "build", "write a function"],
            task_patterns=[
                r"explain\s+.*(to|for)\s+.*(beginner|\d+[\s-]year|non[\s-]?technical|someone)",
                r"(how|what)\s+(does|is|are)\s+.*(work|mean)",
                r"(teach|explain|describe)\s+.*(mechanism|concept|principle)",
            ],
            example_tasks=[
                "Explain transformer attention mechanisms to a smart 16-year-old",
                "How does gradient descent work? Explain for a beginner.",
            ],
            priority=3,  # slightly lower — "explain" is common in many tasks
        ),

        "startup_naming": RubricSignature(
            name="startup_naming",
            builder=_wrap(sample_tasks["startup_naming"]),
            keywords=[
                "name", "names", "naming", "startup name",
                "brand name", "product name", "company name",
            ],
            anti_keywords=["variable name", "function name", "file name", "rename"],
            task_patterns=[
                r"(generate|suggest|come\s+up\s+with|brainstorm)\s+.*(name|brand)",
                r"\d+\s+names?\s+(for|that)",
                r"name\s+.*(startup|company|product|app|brand)",
            ],
            example_tasks=[
                "Generate 5 names for a startup that does AI-powered contract review",
                "Come up with brand names for a fintech app",
            ],
            priority=5,
        ),

        "bash_backup": RubricSignature(
            name="bash_backup",
            builder=_wrap(sample_tasks["bash_backup"]),
            keywords=[
                "bash", "shell script", "backup", "pg_dump",
                "postgresql", "postgres", "s3", "cron",
                "rotation", "logging",
            ],
            anti_keywords=["python", "node", "frontend", "email"],
            task_patterns=[
                r"(write|create|build)\s+.*(bash|shell)\s*(script)",
                r"(backup|back\s*up)\s+.*(database|postgres|mysql|s3)",
                r"(script|cron)\s+.*(backup|rotate|log|notify)",
            ],
            example_tasks=[
                "Write a bash script that backs up a PostgreSQL database to S3",
                "Create a shell script for automated database backup with rotation",
            ],
            priority=5,
        ),

        "investment_memo": RubricSignature(
            name="investment_memo",
            builder=_wrap(sample_tasks["investment_memo"]),
            keywords=[
                "investment memo", "memo", "series a", "series b",
                "pitch", "due diligence", "deal memo",
                "thesis", "portfolio", "venture",
            ],
            anti_keywords=["code", "sql", "bash", "frontend", "email"],
            task_patterns=[
                r"(draft|write)\s+.*(investment|deal)\s*memo",
                r"(memo|brief)\s+.*(series\s*[abc]|seed|investment|company|startup)",
                r"(investment|vc|venture)\s+.*(thesis|memo|brief|analysis)",
            ],
            example_tasks=[
                "Draft a 1-page investment memo on a Series A defense drone company",
                "Write an investment memo for a seed-stage AI startup",
            ],
            priority=5,
        ),
    }

    for name, sig in _SAMPLE_SIGNATURES.items():
        REGISTRY.register(sig)


# Convenience: keep a top-level resolve function
def resolve_rubric(task: str, rubric: Rubric = None, rubric_name: str = None) -> tuple[Rubric, str, float]:
    """Resolve a task to the best-matching rubric.

    Args:
        task: task description string
        rubric: explicit Rubric object (bypasses all matching)
        rubric_name: explicit rubric name to look up in registry

    Returns:
        (rubric, matched_name, confidence)
    """
    if rubric is not None:
        return rubric, "explicit", 1.0
    return REGISTRY.resolve(task, rubric_name=rubric_name)


# Legacy compatibility
def detect_domain(task: str) -> tuple[str, float]:
    """DEPRECATED: Use resolve_rubric() instead. Kept for backwards compatibility."""
    _, name, confidence = resolve_rubric(task)
    return (name, confidence)


# ============================================================================
# Rubric Builder
# ============================================================================

def build_knowledge_work_rubric(task: str) -> Rubric:
    """Build full knowledge work rubric with granular scoring."""

    criteria = [
        Criterion(
            id="src_freshness",
            category="source_quality",
            description="Sources are appropriately recent for the domain",
            pass_condition="Fast-changing <2y, medium <5y; stale sources penalized by citation importance",
            scoring=source_freshness_rubric(10),
            pass_examples=[
                "All headline claims cite sources <12 months old",
                "95% of supporting sources within threshold"
            ],
            fail_examples=[
                "Key market size from 2021 report (3+ years stale)",
                "50% of headline citations are outdated"
            ]
        ),
        Criterion(
            id="src_authority",
            category="source_quality",
            description="Sources from credible, authoritative entities",
            pass_condition="Peer-reviewed, official data, experts with credentials stated",
            scoring=source_authority_rubric(10),
            pass_examples=[
                "Key claims backed by Nature/Science/Lancet",
                "Expert quotes include title and affiliation"
            ],
            fail_examples=[
                "Headline statistic from Medium blog",
                "Expert quoted without any credentials"
            ]
        ),
        Criterion(
            id="src_triangulation",
            category="source_quality",
            description="Key claims validated by multiple independent sources",
            pass_condition="Tier1: 3+ sources, Tier2: 2+ sources, genuinely independent",
            scoring=source_triangulation_rubric(10),
            pass_examples=[
                "TAM figure corroborated by 3 analyst firms",
                "Sources don't cite each other circularly"
            ],
            fail_examples=[
                "Headline claim from single source",
                "'3 sources' all citing same primary study"
            ]
        ),
        Criterion(
            id="evd_alignment",
            category="evidence",
            description="Every claim supported by appropriate evidence",
            pass_condition="No unsupported assertions; evidence strength matches claim strength",
            scoring=evidence_alignment_rubric(10),
            pass_examples=[
                "Each factual claim has inline citation",
                "Causal claims backed by experimental evidence"
            ],
            fail_examples=[
                "'X causes Y' supported only by correlation",
                "Statistics stated without any source"
            ]
        ),
        Criterion(
            id="viz_accuracy",
            category="visualization",
            description="Visualizations accurately represent underlying data",
            pass_condition="Proper baselines, scales, chart types; no visual distortion",
            scoring=visualization_accuracy_rubric(10),
            pass_examples=[
                "Bar chart Y-axis starts at zero",
                "Time series uses consistent intervals"
            ],
            fail_examples=[
                "Truncated axis exaggerates 5% difference",
                "Pie chart used for time trend"
            ]
        ),
        Criterion(
            id="viz_clarity",
            category="visualization",
            description="Visualizations are clear and accessible",
            pass_condition="Declarative titles, complete labels, WCAG compliant",
            scoring=visualization_clarity_rubric(10),
            pass_examples=[
                "Title: 'Revenue grew 40% in Q3' not 'Q3 Revenue'",
                "Color-blind safe palette with patterns"
            ],
            fail_examples=[
                "Chart titled 'Data' with no context",
                "Red/green only distinction"
            ]
        ),
        Criterion(
            id="fwd_uncertainty",
            category="predictions",
            description="Predictions include appropriate uncertainty quantification",
            pass_condition="Labeled as predictions, confidence levels, ranges, assumptions stated",
            scoring=uncertainty_quantification_rubric(10),
            pass_examples=[
                "Forecast: $50M (90% CI: $40-65M)",
                "Assuming 15% market growth (see Appendix A)"
            ],
            fail_examples=[
                "'Revenue will be $50M' with no range",
                "Prediction stated as fact without 'we expect'"
            ]
        ),
        Criterion(
            id="doc_structure",
            category="structure",
            description="Document has clear structure with BLUF",
            pass_condition="Exec summary with conclusions, logical flow, all sections complete",
            scoring=document_structure_rubric(10),
            pass_examples=[
                "First paragraph contains all 3 key findings",
                "Background -> Analysis -> Conclusions flow"
            ],
            fail_examples=[
                "Conclusions buried on page 15",
                "Circular reasoning between sections"
            ]
        ),
    ]

    total_points = sum(c.scoring.max_points for c in criteria)

    return Rubric(
        task=task,
        domain="knowledge_work_research",
        criteria=criteria,
        total_points=total_points,
        pass_threshold=0.85
    )


def build_frontend_design_rubric(task: str) -> Rubric:
    """Build frontend design rubric with 16 criteria from the design rubric spec.

    Categories: color system (3), typography (3), spacing/layout (3),
    components/patterns (3), visual polish (3), accessibility (2).
    Total: 132 max points.
    """

    criteria = [
        # === COLOR SYSTEM (Critical) ===
        Criterion(
            id="color_001",
            category="visual_design",
            description="Color palette is intentional, modern, and avoids AI clichés",
            pass_condition="NOT using default purple (#8B5CF6/#7C3AED/#6366F1). Primary is distinctive. "
                          "Follows 60-30-10 rule. Semantic colors present. Max 5-6 active colors.",
            scoring=color_palette_rubric(10),
            pass_examples=[
                "Deep teal primary (#0D6E6E) with coral accent, 60-30-10 ratio",
                "Brand orange (#EA580C) with semantic success/error/warning colors"
            ],
            fail_examples=[
                "Default AI purple gradient (#7C3AED → #6366F1)",
                "8+ active colors with no clear hierarchy"
            ],
            domain="frontend_design"
        ),
        Criterion(
            id="color_002",
            category="accessibility",
            description="Color contrast meets WCAG 2.1 AA standards",
            pass_condition="Body text: 4.5:1 minimum. Large text (18px+/14px bold): 3:1. "
                          "Interactive elements distinguishable. Info not conveyed by color alone.",
            scoring=color_contrast_rubric(10),
            pass_examples=[
                "#1C1917 on #FAFAF9 = 15.4:1 contrast ratio",
                "Links underlined + colored, not color-only"
            ],
            fail_examples=[
                "Light gray text (#A0A0A0) on white (#FFFFFF) = 2.1:1",
                "Error indicated only by red text, no icon or label"
            ],
            domain="frontend_design"
        ),
        Criterion(
            id="color_003",
            category="visual_design",
            description="Uses modern color trends appropriately",
            pass_condition="Warm neutrals over stark whites. Off-blacks instead of #000000. "
                          "Subtle gradients. No saturated rainbows or dated SaaS gradients.",
            scoring=color_modernness_rubric(8),
            pass_examples=[
                "Background #FAFAF8 (warm white), text #171717 (off-black)",
                "Subtle ambient gradient, not rainbow"
            ],
            fail_examples=[
                "Pure #FFFFFF background with #000000 text",
                "Blue-purple SaaS hero gradient as primary design element"
            ],
            domain="frontend_design"
        ),

        # === TYPOGRAPHY (Critical) ===
        Criterion(
            id="type_001",
            category="typography",
            description="Typography hierarchy is clear and consistent",
            pass_condition="Clear H1/H2/H3/body/caption distinction. Size ratio 1.2-1.5x between levels. "
                          "Max 2 font families. Line height 1.4-1.6x for body.",
            scoring=typography_hierarchy_rubric(10),
            pass_examples=[
                "H1 32px/bold, H2 24px/semibold, Body 16px/regular — clear scale",
                "Single font family (Inter) with 4 weight variations"
            ],
            fail_examples=[
                "H1 18px, H2 16px — nearly indistinguishable",
                "3 different font families creating visual chaos"
            ],
            domain="frontend_design"
        ),
        Criterion(
            id="type_002",
            category="typography",
            description="Font choices are modern and readable",
            pass_condition="Modern sans-serif (Inter, SF Pro, DM Sans, Satoshi, Geist) or intentional serif. "
                          "14px minimum body. Variable fonts preferred.",
            scoring=font_choice_rubric(10),
            pass_examples=[
                "Inter variable font, 16px body, renders crisp at all sizes",
                "Intentional serif (Fraunces) for brand personality"
            ],
            fail_examples=[
                "Comic Sans or Papyrus as UI font",
                "12px body text on mobile — too small to read"
            ],
            domain="frontend_design"
        ),
        Criterion(
            id="type_003",
            category="typography",
            description="Typography feels intentional and branded",
            pass_condition="Headlines make visual impact. Consistent letter-spacing. "
                          "Intentional alignment. Monospace for code/data.",
            scoring=typography_brand_rubric(8),
            pass_examples=[
                "Bold 48px headlines with tight tracking, left-aligned body",
                "Consistent -0.02em headline tracking, 0em body tracking"
            ],
            fail_examples=[
                "Everything center-aligned including body paragraphs",
                "Random mix of tracking values across similar elements"
            ],
            domain="frontend_design"
        ),

        # === SPACING & LAYOUT (Critical) ===
        Criterion(
            id="space_001",
            category="layout",
            description="Spacing follows 8px grid system consistently",
            pass_condition="All values multiples of 8 (4px only for micro). "
                          "No arbitrary values (13px, 17px). Consistent scale. Inner padding ≤ outer margins.",
            scoring=spacing_grid_rubric(10),
            pass_examples=[
                "All values 8/16/24/32/48 — clean grid",
                "4px only between icon and label text"
            ],
            fail_examples=[
                "Random 15px, 20px, 12px spacing throughout",
                "Inner card padding 24px but card gap only 16px"
            ],
            domain="frontend_design"
        ),
        Criterion(
            id="space_002",
            category="layout",
            description="Visual hierarchy through spacing",
            pass_condition="Related elements 8-16px. Unrelated 24-48px. Sections 48-96px. "
                          "Gestalt proximity/similarity applied.",
            scoring=spacing_hierarchy_rubric(10),
            pass_examples=[
                "Form labels 8px from inputs, field groups 24px apart, sections 48px",
                "Card content grouped at 8px, cards separated at 24px"
            ],
            fail_examples=[
                "Uniform 16px gap everywhere — no hierarchy",
                "Elements float with no clear grouping relationship"
            ],
            domain="frontend_design"
        ),
        Criterion(
            id="space_003",
            category="layout",
            description="Layout adapts to content and context",
            pass_condition="Consistent container padding (16-24px). Responsive breakpoints. "
                          "Content not cramped or lost. Consistent gutters.",
            scoring=layout_adaptability_rubric(8),
            pass_examples=[
                "16px card padding throughout, bento layout for dashboard",
                "Smooth transition from 3-col to 1-col at mobile breakpoint"
            ],
            fail_examples=[
                "Cards with 8px padding here, 32px there, 12px elsewhere",
                "Layout breaks at tablet width, content overlaps"
            ],
            domain="frontend_design"
        ),

        # === COMPONENTS & PATTERNS (High) ===
        Criterion(
            id="comp_001",
            category="components",
            description="Interactive elements are clearly tappable/clickable",
            pass_condition="Touch targets ≥44x44px (iOS)/48x48dp (Android). Clear button affordance. "
                          "Hover/focus/active states. Disabled states visible. Links distinguishable.",
            scoring=interactive_elements_rubric(8),
            pass_examples=[
                "Primary button 48px height, clear filled style, hover darkens 10%",
                "Disabled state at 40% opacity with not-allowed cursor"
            ],
            fail_examples=[
                "36px 'Add to Cart' button — below 44px minimum",
                "Links look identical to body text (no underline or color)"
            ],
            domain="frontend_design"
        ),
        Criterion(
            id="comp_002",
            category="components",
            description="Navigation is intuitive and consistent",
            pass_condition="Bottom nav for mobile (max 5). Current location indicated. "
                          "Back/close accessible. Consistent patterns across screens.",
            scoring=navigation_rubric(8),
            pass_examples=[
                "Bottom nav with active indicator, 5 items, current page highlighted",
                "Consistent back arrow in top-left across all detail screens"
            ],
            fail_examples=[
                "No indication of current page in navigation",
                "Back button missing on half the screens"
            ],
            domain="frontend_design"
        ),
        Criterion(
            id="comp_003",
            category="components",
            description="Forms and inputs are user-friendly",
            pass_condition="Visible input boundaries. Labels (not just placeholders). "
                          "Clear error states. Obvious focus. Appropriate mobile keyboards.",
            scoring=forms_inputs_rubric(8),
            pass_examples=[
                "Floating labels, 1px border inputs, red error with icon + message",
                "Email field triggers email keyboard on mobile"
            ],
            fail_examples=[
                "Placeholder-only labels that disappear on focus",
                "No visual change on input focus"
            ],
            domain="frontend_design"
        ),

        # === VISUAL POLISH (Standard) ===
        Criterion(
            id="polish_001",
            category="visual_design",
            description="Consistent visual language throughout",
            pass_condition="Consistent border radius, shadow depth, icon style, illustration style.",
            scoring=visual_consistency_rubric(6),
            pass_examples=[
                "16px radius throughout, 3-level shadow system, all outline icons",
                "Consistent illustration style — flat geometric across all pages"
            ],
            fail_examples=[
                "Mix of 4px, 8px, 16px, 24px border radius with no system",
                "Outline icons mixed with filled icons randomly"
            ],
            domain="frontend_design"
        ),
        Criterion(
            id="polish_002",
            category="visual_design",
            description="Micro-interactions and feedback present",
            pass_condition="Loading states for async. Success/error feedback. "
                          "Smooth transitions (200-300ms). No jarring changes.",
            scoring=micro_interactions_rubric(6),
            pass_examples=[
                "Skeleton loaders for content, toast notifications for actions",
                "Smooth 200ms ease-out transitions between states"
            ],
            fail_examples=[
                "Spinner-only loading with no layout skeleton",
                "Instant state jumps with no transition"
            ],
            domain="frontend_design"
        ),
        Criterion(
            id="polish_003",
            category="visual_design",
            description="Dark mode support (if applicable)",
            pass_condition="Not just inverted. Dark grays not pure black. Reduced saturation. "
                          "Shadows adapt. Images readable.",
            scoring=dark_mode_rubric(6),
            pass_examples=[
                "Dark mode #0F0F0F bg, desaturated teal primary, glow instead of shadow",
                "Images with dark overlay for readability"
            ],
            fail_examples=[
                "Simple CSS invert() — colors and images broken",
                "Pure #000000 background with full-saturation colors"
            ],
            domain="frontend_design"
        ),

        # === ACCESSIBILITY (High) ===
        Criterion(
            id="a11y_001",
            category="accessibility",
            description="Screen reader compatibility",
            pass_condition="Semantic HTML (headings, landmarks, lists). Alt text. ARIA labels. "
                          "Logical focus order. Skip links for nav-heavy pages.",
            scoring=screen_reader_rubric(8),
            pass_examples=[
                "Proper <nav>, <main>, <aside> landmarks, heading hierarchy matches visual",
                "All images have descriptive alt text, decorative images alt=''"
            ],
            fail_examples=[
                "All divs, no semantic structure — screen reader sees flat list",
                "Image-heavy page with zero alt text"
            ],
            domain="frontend_design"
        ),
        Criterion(
            id="a11y_002",
            category="accessibility",
            description="Keyboard and motor accessibility",
            pass_condition="All elements keyboard accessible. Visible focus indicators. "
                          "No keyboard traps. Adequate spacing. No time limits without override.",
            scoring=keyboard_motor_rubric(8),
            pass_examples=[
                "Tab through all interactive elements, 3px blue focus ring visible",
                "Modal has focus trap with Escape to close"
            ],
            fail_examples=[
                "Custom dropdown not keyboard accessible",
                "Focus indicator removed with outline: none, no replacement"
            ],
            domain="frontend_design"
        ),
    ]

    total_points = sum(c.scoring.max_points for c in criteria)

    return Rubric(
        task=task,
        domain="frontend_design",
        criteria=criteria,
        total_points=total_points,
        pass_threshold=0.85
    )


# ============================================================================
# Frontend Design Measurement Prompt
# ============================================================================

FRONTEND_MEASUREMENT_PROMPT = """Analyze this frontend design/UI output and extract precise measurements for scoring.

CONTENT:
```
{content}
```

CRITERIA TO MEASURE:
{criteria_specs}

For each criterion and sub-attribute, evaluate the design and calculate scores.

OUTPUT FORMAT (JSON):
{{
  "criterion_id": {{
    "sub_attribute_id": <float 0.0-1.0>,
    "sub_attribute_id_evidence": "specific observation",
    "violations": ["list", "of", "violations"]  // for penalty-based criteria
  }}
}}

MEASUREMENT RULES:
1. COLOR PALETTE (color_001):
   - color_distinctiveness: 0.0 if uses #8B5CF6/#7C3AED/#6366F1 or similar AI purple. 1.0 if distinctive.
   - palette_harmony: Check 60-30-10 adherence + semantic color presence
   - palette_restraint: Count distinct active (non-gray) colors

2. COLOR CONTRAST (color_002):
   - Calculate or estimate contrast ratios for text/background combinations
   - Check if interactive elements are distinguishable without color alone

3. COLOR MODERNNESS (color_003) — PENALTY-BASED:
   - List violations: pure_black_on_white, saturated_rainbow_gradient, default_ai_purple_gradient, etc.

4. TYPOGRAPHY (type_001-003):
   - Check heading size ratios, weight usage, font family count
   - Identify the font(s) used, assess modernity
   - Evaluate letter-spacing, alignment consistency

5. SPACING (space_001-003):
   - Check if values align to 8px grid (8,16,24,32,40,48...)
   - Evaluate proximity grouping vs section separation
   - Check container padding consistency

6. COMPONENTS (comp_001-003) — PENALTY-BASED for 001 and 003:
   - comp_001: List violations for touch targets, affordance, states
   - comp_002: Evaluate nav clarity, location indication, consistency
   - comp_003: List violations for input design, labels, error states

7. VISUAL POLISH (polish_001-003):
   - Evaluate consistency of border radius, shadows, icons
   - Check for loading states, feedback, transitions
   - Assess dark mode quality if present (N/A scores as 0.5 for each sub)

8. ACCESSIBILITY (a11y_001-002):
   - Check semantic HTML, ARIA, alt text, focus order
   - a11y_002: List violations for keyboard access, focus indicators, traps

Be thorough. Score each sub-attribute. Output ONLY valid JSON."""


# ============================================================================
# Scoring Engine
# ============================================================================


# ============================================================================
# Independent Generation Agent — isolated context window for content creation
# ============================================================================

class GenerationAgent:
    """Independent content generation agent with isolated context window.

    The generator operates in its own context — it never sees the scoring
    agent's system prompt, calibration rules, or measurement methodology.
    It only receives:
    1. The task description
    2. The rubric criteria (what to optimize for)
    3. Prior iteration feedback (scores and focus areas)
    4. Learned feedback from the FeedbackInjector

    This isolation prevents the generator from gaming the scorer by
    mimicking scoring patterns rather than producing genuinely good content.
    """

    GENERATOR_SYSTEM_PROMPT = """You are a domain expert content generator. Your job is to produce the highest-quality content possible for a given task, guided by a scoring rubric.

GENERATION PRINCIPLES:
1. SUBSTANCE OVER COMPLIANCE: Don't just address each rubric criterion superficially. Produce content that a domain expert would recognize as genuinely excellent. The rubric guides what to cover, but your expertise determines HOW to cover it.

2. INTERNAL CONSISTENCY: Every claim, number, and reference must be internally consistent. If you cite a figure in the executive summary, it must match the detailed analysis. Cross-reference your own work.

3. PRECISION OVER BREADTH: It's better to cover fewer points with genuine depth than to check every box with surface-level treatment. A scorer will penalize shallow compliance.

4. DOMAIN AUTHENTICITY: Use terminology, frameworks, and methodologies that a real practitioner in this field would use. Generic business language scores poorly.

5. ITERATION AWARENESS: When given feedback from a prior attempt, make TARGETED improvements to weak areas while PRESERVING everything that already scored well. Don't rewrite from scratch — surgically edit."""

    def __init__(self, model: str = "claude-sonnet-4-20250514", verbose: bool = True):
        if Anthropic is None:
            raise ImportError("anthropic package required: pip install anthropic")
        self.client = Anthropic(timeout=_API_TIMEOUT)  # Fresh client, separate from scorer and rubric agents
        self.model = model
        self.verbose = verbose

    def _log(self, msg: str):
        if self.verbose:
            print(f"[Generator] {msg}")

    def generate(
        self,
        prompt: str,
        max_tokens: int = 12000,
    ) -> str:
        """Generate content in an isolated context window.

        Args:
            prompt: the fully-formed generation prompt (task + rubric + feedback)
            max_tokens: max response length

        Returns:
            Generated content string
        """
        self._log("Generating content (isolated agent)...")

        response = self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            system=self.GENERATOR_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )

        return response.content[0].text


# ============================================================================
# Independent Scoring Agent — isolated context window for adversarial grading
# ============================================================================

class ScoringAgent:
    """Independent scoring agent with isolated context window.

    The scorer operates as a separate adversarial auditor — it never sees
    the generation prompt, task context, or prior attempts. It only sees:
    1. The rubric criteria and scoring rules
    2. The content to evaluate
    3. Calibration instructions to avoid leniency bias

    This is the core fix for the self-leniency problem: when Claude scores
    its own work in the same context, it grades generously. A fresh context
    with an adversarial system prompt produces honest scores.
    """

    SCORER_SYSTEM_PROMPT = """You are a structured two-stage evaluation system. Your role is to extract verifiable facts first, then derive scores mechanically from those facts — not to produce impressionistic holistic ratings.

TWO-STAGE PROTOCOL:

STAGE 1 — CHECKLIST EXTRACTION (facts only, no scoring yet):
For each sub-attribute, extract BINARY observations about what IS and IS NOT present in the content.
State each observation as: "[specific observable requirement]? YES / NO. Evidence: [direct quote or 'not found in content']"
Be literal and specific. Quote exact text when present. Do NOT assign numeric scores in this stage.

STAGE 2 — MECHANICAL SCORING (derived directly from Stage 1 facts):
Apply these deterministic mapping rules based on your Stage 1 checklist results:

For weighted_components sub-attributes (valid values: 0.0, 0.25, 0.50, 0.75, 1.0):
  - ALL checks pass AND content demonstrates exceptional independent domain expertise that SIGNIFICANTLY exceeds rubric guidance → 1.0 (rare — reserve for genuinely outstanding work)
  - ALL checks pass AND content demonstrates independent domain expertise that goes BEYOND rubric guidance → 0.75
  - ALL checks pass AND content follows rubric guidance correctly → 0.50 (DEFAULT for AI-generated content that meets requirements)
  - MAJORITY of checks pass (>50%) but important elements are missing → 0.25
  - FEW or ZERO checks pass (≤50%) → 0.00

For penalty_based criteria:
  Score = max_points − (accumulated deductions for each violation confirmed YES in Stage 1)

CRITICAL: Stage 2 scores are derived MECHANICALLY from Stage 1 facts. Do not override the mapping with subjective impressions. The Stage 1 checklist is the ground truth that produces the score.

CALIBRATION:
- AI-generated content that correctly follows rubric guidance earns 0.50 per sub-attribute (not 0.75 or 1.0)
- 0.75 requires independent domain expertise BEYOND what the rubric specified — this should appear on fewer than 35% of sub-attributes
- 1.0 requires exceptional quality that significantly exceeds rubric expectations — this should appear on no more than 15% of sub-attributes
- First-attempt overall scores typically land at 55-70% when applying this protocol honestly
- The goal is ACCURATE scoring, not harsh scoring. Let the Stage 1 facts determine the outcome."""

    def __init__(self, model: str = "claude-sonnet-4-20250514", verbose: bool = True):
        if Anthropic is None:
            raise ImportError("anthropic package required: pip install anthropic")
        self.client = Anthropic(timeout=_API_TIMEOUT)  # Fresh client, separate from generator
        self.model = model
        self.verbose = verbose
        # Mutable instance copy — updated by adaptive evaluator tuning
        self._scorer_system_prompt = self.SCORER_SYSTEM_PROMPT
        # Preserved from last scoring call for FeedbackAgent consumption
        self._last_raw_response = ""
        self._last_checklist = ""  # Deprecated — kept for backward compat
        self._last_critiques = {}  # criterion_id -> list of critique dicts (new primary source)

    def inject_plateau_prompt(self) -> None:
        """Adaptive evaluator tuning: inject meta-prompt when scores plateau.

        Called when consecutive iteration scores are within 2% of each other,
        indicating the evaluator may be applying criteria too leniently or
        using checklist items that don't discriminate between attempts.
        """
        plateau_injection = (
            "\n\nADAPTIVE EVALUATOR NOTE: Previous iterations have stalled — scores plateaued "
            "within 2% across the last two rounds. Before scoring this attempt, apply extra scrutiny:\n"
            "(1) Are any Stage 1 checklist items ambiguously worded so mediocre content satisfies them?\n"
            "(2) Is your checklist granular enough to distinguish this attempt from the prior one?\n"
            "(3) For each sub-attribute, quote specific evidence or state 'not found' — no inferences.\n"
            "(4) Identify what is specifically still missing, not just whether requirements are generally met.\n"
            "Do NOT change your scoring anchors — use the same 0.0/0.25/0.50/0.75/1.0 scale as always. "
            "Better evidence extraction, not score inflation, is the goal."
        )
        if plateau_injection not in self._scorer_system_prompt:
            self._scorer_system_prompt = self.SCORER_SYSTEM_PROMPT + plateau_injection

    def reset_system_prompt(self) -> None:
        """Reset scorer to base system prompt (call when plateau is resolved)."""
        self._scorer_system_prompt = self.SCORER_SYSTEM_PROMPT

    def _log(self, msg: str):
        if self.verbose:
            print(f"[Scorer] {msg}")

    def score(self, content: str, rubric, feedback_injector=None) -> dict:
        """Score content against rubric in an isolated context.

        Args:
            content: the generated content to evaluate
            rubric: the Rubric object with criteria
            feedback_injector: optional FeedbackInjector for scoring calibration

        Returns:
            dict of criterion_id -> measurements
        """
        criteria_specs = format_criteria_for_measurement(rubric.criteria)

        # Select domain-appropriate measurement prompt
        if rubric.domain == "frontend_design":
            prompt_template = FRONTEND_MEASUREMENT_PROMPT
        else:
            prompt_template = MEASUREMENT_PROMPT

        prompt = prompt_template.format(
            content=content[:20000],
            criteria_specs=criteria_specs
        )

        # Add scoring calibration feedback if available
        if feedback_injector:
            criteria_ids = [c.id for c in rubric.criteria]
            scoring_feedback = feedback_injector.format_for_scoring_prompt(
                domain=rubric.domain, criteria_ids=criteria_ids
            )
            if scoring_feedback:
                prompt += "\n" + scoring_feedback

        self._log("Scoring content (isolated agent)...")

        # Score with retry: if JSON parsing fails, retry the API call once.
        # This prevents catastrophic 0-score fallback from transient parse failures
        # (e.g., board_deck_narrative in Run 11: -61pp regression from parse bug).
        parsed = None
        for attempt in range(2):
            # FRESH context window: system prompt + single user message
            response = self.client.messages.create(
                model=self.model,
                max_tokens=16000,
                temperature=0,
                system=self._scorer_system_prompt,
                messages=[{"role": "user", "content": prompt}],
            )

            raw = response.content[0].text
            self._last_raw_response = raw

            parsed = self._parse_scorer_json(raw)
            if parsed:
                break
            if attempt == 0:
                self._log("Warning: scorer JSON parse failed — retrying with fresh call...")

        if not parsed:
            self._log("ERROR: scorer JSON parse failed after 2 attempts — raising ScoringError")
            raise ScoringError("Scorer returned unparseable JSON after 2 attempts")

        # Extract critiques from the structured JSON into a flat dict for the
        # FeedbackAgent. This is the single source of truth for all downstream
        # feedback — no more separate text checklist.
        self._last_critiques = self._extract_critiques(parsed)
        if self._last_critiques:
            critique_count = sum(len(v) for v in self._last_critiques.values())
            self._log(f"Captured {critique_count} embedded critiques across {len(self._last_critiques)} criteria")

        # Flatten the nested format back to what ScoringEngine expects:
        # {"criterion_id": {"sub_id": <float>, ...}}
        flat = self._flatten_scores(parsed)
        return flat

    def _parse_scorer_json(self, raw: str) -> dict:
        """Extract JSON from scorer response, handling code fences and preamble."""
        # Try code fence first
        match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', raw)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass
        # Try raw JSON
        raw_stripped = raw.strip()
        try:
            return json.loads(raw_stripped)
        except json.JSONDecodeError:
            pass
        # Try finding the outermost { ... }
        match = re.search(r'\{[\s\S]*\}', raw)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
        self._log("Warning: could not parse scorer response as JSON")
        return {}

    def _extract_critiques(self, parsed: dict) -> dict:
        """Extract structured critiques from the scorer's JSON response.

        Returns:
            dict of criterion_id -> list of critique dicts, each with:
                sub_id, score, critique, suggestion, checks, evidence
        """
        critiques = {}
        for crit_id, crit_data in parsed.items():
            if not isinstance(crit_data, dict):
                continue
            crit_critiques = []
            for key, val in crit_data.items():
                if key.startswith("_") or key == "violations" or key == "violation_details":
                    # Handle penalty-based violation critiques
                    if key == "violation_details" and isinstance(val, list):
                        for vd in val:
                            crit_critiques.append({
                                "sub_id": vd.get("violation", ""),
                                "score": None,
                                "critique": vd.get("critique", ""),
                                "suggestion": "",
                                "evidence": vd.get("evidence", ""),
                                "checks": [],
                                "is_violation": True,
                            })
                    continue
                if isinstance(val, dict) and "score" in val:
                    # New nested format: {"score": 0.25, "critique": "...", ...}
                    crit_critiques.append({
                        "sub_id": key,
                        "score": val.get("score", 0),
                        "critique": val.get("critique", ""),
                        "suggestion": val.get("suggestion", ""),
                        "evidence": self._extract_evidence_from_checks(val.get("checks", [])),
                        "checks": val.get("checks", []),
                        "is_violation": False,
                    })
                elif isinstance(val, (int, float)):
                    # Legacy flat format: {"sub_id": 0.25} — no critique available
                    crit_critiques.append({
                        "sub_id": key,
                        "score": val,
                        "critique": "",
                        "suggestion": "",
                        "evidence": "",
                        "checks": [],
                        "is_violation": False,
                    })
            if crit_critiques:
                critiques[crit_id] = crit_critiques
        return critiques

    def _extract_evidence_from_checks(self, checks: list) -> str:
        """Concatenate evidence from check results into a single string."""
        parts = []
        for c in checks:
            if isinstance(c, dict):
                result = c.get("result", "")
                evidence = c.get("evidence", "")
                check_desc = c.get("check", "")
                if result == "NO" and evidence:
                    parts.append(f"{check_desc}: {evidence}")
        return "; ".join(parts) if parts else ""

    def _flatten_scores(self, parsed: dict) -> dict:
        """Flatten nested critique format back to what ScoringEngine expects.

        Handles both new format: {"sub_id": {"score": 0.25, "critique": "..."}}
        and legacy format: {"sub_id": 0.25}
        """
        flat = {}
        for crit_id, crit_data in parsed.items():
            if not isinstance(crit_data, dict):
                continue
            flat_crit = {}
            for key, val in crit_data.items():
                if isinstance(val, dict) and "score" in val:
                    # New nested format — extract just the score
                    flat_crit[key] = val["score"]
                elif isinstance(val, (int, float)):
                    # Legacy flat format
                    flat_crit[key] = val
                elif key == "violations":
                    flat_crit["_raw_violations"] = val
                elif key == "violation_details":
                    flat_crit["_violation_details"] = val
                elif key.startswith("_"):
                    flat_crit[key] = val

            # Cross-reference violations against violation_details evidence
            raw_violations = flat_crit.pop("_raw_violations", None)
            viol_details = flat_crit.pop("_violation_details", None)

            if raw_violations is not None and viol_details is not None:
                # Both exist — filter raw_violations using evidence from details
                detail_map = {}
                for vd in viol_details:
                    if isinstance(vd, dict):
                        detail_map[vd.get("violation", "")] = vd
                filtered = []
                for v in raw_violations:
                    detail = detail_map.get(v)
                    if detail is None:
                        # No detail entry — assume present (conservative)
                        filtered.append(v)
                    elif "not found" not in detail.get("evidence", "").lower():
                        filtered.append(v)
                flat_crit["violations"] = filtered
            elif raw_violations is not None:
                # Only violations array, no details — pass through as-is
                flat_crit["violations"] = raw_violations
            elif viol_details is not None:
                # Only violation_details — extract present violations
                flat_crit["violations"] = [
                    vd.get("violation", "")
                    for vd in viol_details
                    if isinstance(vd, dict)
                    and "not found" not in vd.get("evidence", "").lower()
                ]

            flat[crit_id] = flat_crit
        return flat


class RubricNegotiationAgent:
    """Sprint contract: two-round negotiation between generator and scorer perspectives.

    Round 1 (Generator perspective — isolated context): Reviews the rubric as the
        content producer. Flags criteria that are ambiguous, untestable, unrealistic,
        or missing key quality dimensions. Proposes specific rewording, sub-attribute
        changes, or refined pass conditions.

    Round 2 (Scorer perspective — isolated context): Reviews the generator's flags as
        the evaluator. Accepts changes that improve testability, rejects changes that
        weaken rigor, or counter-proposes better refinements.

    Final rubric reflects consensus — accepted and counter-proposed changes are applied;
    rejected flags are ignored. The exchange is logged for debugging.
    """

    GENERATOR_REVIEW_SYSTEM_PROMPT = """You are a content generator in a generation-verification loop. You have been given a scoring rubric that will be used to grade your output.

Review each criterion from the perspective of someone who will produce the content:

1. AMBIGUOUS — the pass/fail condition has multiple valid interpretations that could produce different scores for identical content
2. UNTESTABLE — cannot be objectively verified from the content text alone (requires external data, human judgment, or post-hoc research)
3. MISSING — an important quality dimension a skilled practitioner would expect is absent from the rubric
4. UNREALISTIC — asks for something a single LLM generation pass cannot reasonably deliver

For each flagged criterion, propose a concrete change: reword the description, sharpen the pass condition, add or remove sub-attributes, or adjust weights. Be specific — vague objections will be rejected.

Leave criteria that are clear, measurable, and achievable alone.

Return only JSON — no prose outside the JSON block."""

    SCORER_REVIEW_SYSTEM_PROMPT = """You are the evaluator in a generation-verification loop. The content generator has reviewed the rubric and proposed changes to some criteria.

Your role is to protect rubric integrity while allowing valid improvements. For each generator flag, decide:

- "accept" — the objection is valid AND the proposed change makes the criterion more objectively testable
- "reject" — the criterion is sound as-is; the generator may be avoiding rigorous evaluation
- "counter" — the direction is right but the proposed wording needs improvement; provide your own refinement

Rules:
- Accept changes that add specificity and testability
- Reject changes that weaken or remove evaluation rigor without strong justification
- Counter when the objection has merit but the proposed change is imprecise
- Never accept a change that removes a criterion entirely (counter to narrow it instead)

Return only JSON — no prose outside the JSON block."""

    def __init__(self, model: str = "claude-sonnet-4-20250514", verbose: bool = True):
        if Anthropic is None:
            raise ImportError("anthropic package required: pip install anthropic")
        # Separate clients for isolated context windows per agent perspective
        self.generator_client = Anthropic(timeout=_API_TIMEOUT)
        self.scorer_client = Anthropic(timeout=_API_TIMEOUT)
        self.model = model
        self.verbose = verbose

    def _log(self, msg: str):
        if self.verbose:
            print(f"[Negotiator] {msg}")

    def _parse_json(self, raw: str) -> dict:
        """Parse JSON from LLM response, tolerating markdown code fences."""
        m = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', raw)
        text = m.group(1) if m else raw
        try:
            return json.loads(text.strip())
        except Exception:
            m2 = re.search(r'\{[\s\S]*\}', raw)
            if m2:
                try:
                    return json.loads(m2.group())
                except Exception:
                    pass
        return {}

    def negotiate(self, rubric: "Rubric", task: str) -> tuple["Rubric", list[str]]:
        """Two-round sprint contract negotiation.

        Round 1: Generator reviews rubric → proposes flags and changes.
        Round 2: Scorer reviews flags → accepts, rejects, or counter-proposes.
        Final:   Apply accepted/countered changes to produce negotiated rubric.

        Returns (negotiated_rubric, flag_messages_for_logging).
        """
        from dataclasses import replace as dc_replace

        criteria_json = [
            {
                "id": c.id,
                "description": c.description,
                "pass_condition": c.pass_condition,
                "scoring_method": c.scoring.method.value,
                "max_points": c.scoring.max_points,
                "sub_attributes": [
                    {"sub_id": s.sub_id, "description": s.description, "weight": s.weight}
                    for s in (c.scoring.sub_attributes or [])
                ],
            }
            for c in rubric.criteria
        ]

        # ── Round 1: Generator proposes flags ────────────────────────────────
        self._log(f"Round 1 — Generator reviewing {len(rubric.criteria)} criteria...")

        gen_prompt = f"""TASK: {task}

RUBRIC CRITERIA:
{json.dumps(criteria_json, indent=2)}

Review each criterion from the producer's perspective. Flag only criteria with real problems.

Return JSON in this exact format:
{{
  "flags": [
    {{
      "criterion_id": "...",
      "issue": "ambiguous|untestable|missing|unrealistic",
      "explanation": "...",
      "proposed_description": "...",
      "proposed_pass_condition": "..."
    }}
  ],
  "no_issues": ["criterion_id_1", ...]
}}"""

        gen_response = self.generator_client.messages.create(
            model=self.model,
            max_tokens=4000,
            system=self.GENERATOR_REVIEW_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": gen_prompt}],
        )
        gen_raw = gen_response.content[0].text
        self._log(f"  Generator response: {len(gen_raw)} chars")

        gen_result = self._parse_json(gen_raw)
        gen_flags = gen_result.get("flags", [])

        if not gen_flags:
            self._log("  Generator: no objections — rubric accepted as-is.")
            return rubric, []

        self._log(f"  Generator flagged {len(gen_flags)} criteria:")
        for f in gen_flags:
            self._log(
                f"    [{f.get('issue', '?')}] {f.get('criterion_id', '?')}: "
                f"{f.get('explanation', '')[:70]}"
            )

        # ── Round 2: Scorer reviews flags ────────────────────────────────────
        self._log("Round 2 — Scorer reviewing generator's flags...")

        scorer_prompt = f"""TASK: {task}

ORIGINAL RUBRIC:
{json.dumps(criteria_json, indent=2)}

GENERATOR FLAGS:
{json.dumps(gen_flags, indent=2)}

Evaluate each flag. For each flagged criterion_id decide: accept, reject, or counter.

Return JSON in this exact format:
{{
  "decisions": [
    {{
      "criterion_id": "...",
      "decision": "accept|reject|counter",
      "reason": "...",
      "final_description": "...",
      "final_pass_condition": "..."
    }}
  ]
}}"""

        scorer_response = self.scorer_client.messages.create(
            model=self.model,
            max_tokens=4000,
            system=self.SCORER_REVIEW_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": scorer_prompt}],
        )
        scorer_raw = scorer_response.content[0].text
        self._log(f"  Scorer response: {len(scorer_raw)} chars")

        scorer_result = self._parse_json(scorer_raw)
        decisions = scorer_result.get("decisions", [])

        # ── Apply decisions to produce negotiated rubric ──────────────────────
        decision_map = {d["criterion_id"]: d for d in decisions}
        flag_map = {f["criterion_id"]: f for f in gen_flags}
        flag_messages = []
        new_criteria = []
        accepted = rejected = countered = 0

        for c in rubric.criteria:
            d = decision_map.get(c.id)
            if d is None:
                new_criteria.append(c)
                continue

            verdict = d.get("decision", "reject")
            reason = d.get("reason", "")[:70]
            gen_flag = flag_map.get(c.id, {})

            if verdict == "accept":
                new_c = dc_replace(
                    c,
                    description=(
                        d.get("final_description")
                        or gen_flag.get("proposed_description", c.description)
                    ),
                    pass_condition=(
                        d.get("final_pass_condition")
                        or gen_flag.get("proposed_pass_condition", c.pass_condition)
                    ),
                )
                new_criteria.append(new_c)
                flag_messages.append(f"[accepted]  {c.id}: {reason}")
                self._log(f"    ✓ accepted  {c.id}: {reason}")
                accepted += 1
            elif verdict == "counter":
                new_c = dc_replace(
                    c,
                    description=d.get("final_description", c.description),
                    pass_condition=d.get("final_pass_condition", c.pass_condition),
                )
                new_criteria.append(new_c)
                flag_messages.append(f"[countered] {c.id}: {reason}")
                self._log(f"    ↔ countered {c.id}: {reason}")
                countered += 1
            else:  # reject
                new_criteria.append(c)
                flag_messages.append(f"[rejected]  {c.id}: {reason}")
                self._log(f"    ✗ rejected  {c.id}: {reason}")
                rejected += 1

        self._log(
            f"Sprint contract complete: {accepted} accepted, "
            f"{countered} countered, {rejected} rejected."
        )

        if accepted == 0 and countered == 0:
            return rubric, flag_messages

        return dc_replace(rubric, criteria=new_criteria), flag_messages


class TradeoffDetector:
    """Detects inversely correlated criteria pairs in a rubric and resolves them.

    Isolated context window — only sees the rubric criteria (no task history,
    no prior iterations).  Runs after rubric negotiation, before the main
    gen-verify loop starts.

    Resolution strategies:
      MERGE     — combine into a single balanced criterion
      PRIORITIZE — keep both, annotate the lower-priority one
      RELAX     — reduce max_points of the less-important criterion by 30 %
    """

    SYSTEM_PROMPT = """You are a rubric trade-off analyst. Your job is to identify \
pairs of scoring criteria that are inversely correlated — where genuinely optimizing \
for one criterion would necessarily hurt the other.

Common trade-off patterns (non-exhaustive):
- Concision vs completeness/depth/nuance
- Simplicity vs thoroughness
- Brevity vs evidence richness
- Accessibility vs technical precision
- Speed vs accuracy
- Specificity vs generalizability
- Formality vs approachability

Important constraints:
- Only flag pairs that are GENUINELY in tension based on their descriptions and pass conditions.
- Do NOT flag pairs that merely cover different aspects of quality.
- Be conservative — it is better to miss a subtle trade-off than to incorrectly merge independent criteria.
- You must be GENERAL PURPOSE: do not assume any particular domain or subject matter.

For each trade-off pair found, recommend exactly one resolution:
  MERGE       — combine both into a single criterion that explicitly balances them
  PRIORITIZE  — keep both, but state which takes precedence when they conflict
  RELAX       — lower the weight of the less important criterion in the pair

Return only JSON — no prose outside the JSON block."""

    def __init__(self, model: str = "claude-sonnet-4-20250514", verbose: bool = True):
        if Anthropic is None:
            raise ImportError("anthropic package required: pip install anthropic")
        self.client = Anthropic(timeout=_API_TIMEOUT)
        self.model = model
        self.verbose = verbose

    def _log(self, msg: str) -> None:
        if self.verbose:
            print(f"[TradeoffDetector] {msg}")

    def detect_and_resolve(self, rubric: "Rubric") -> tuple["Rubric", List[str]]:
        """Analyse rubric criteria for inverse correlations and return a resolved rubric.

        Returns:
            (refined_rubric, resolution_messages) — resolution_messages is empty
            when no trade-offs were detected.
        """
        from dataclasses import replace as dc_replace

        if len(rubric.criteria) < 2:
            return rubric, [], []

        criteria_json = [
            {
                "id": c.id,
                "description": c.description,
                "pass_condition": c.pass_condition,
                "max_points": c.scoring.max_points,
            }
            for c in rubric.criteria
        ]

        prompt = f"""RUBRIC CRITERIA:
{json.dumps(criteria_json, indent=2)}

Analyze these criteria pairwise for inverse correlation — cases where genuinely \
optimizing for one would necessarily hurt the other.

For each detected trade-off pair, choose a resolution:
- MERGE: combine into one balanced criterion (provide merged_description + merged_pass_condition)
- PRIORITIZE: keep both, note which takes precedence (provide primary_criterion + priority_note)
- RELAX: reduce max_points of the less important one by 30% (provide relax_criterion)

Return JSON in this exact format:
{{
  "tradeoffs": [
    {{
      "criterion_a": "criterion_id_1",
      "criterion_b": "criterion_id_2",
      "explanation": "Why these are in tension (1-2 sentences)",
      "resolution": "merge|prioritize|relax",
      "merged_description": "...",
      "merged_pass_condition": "...",
      "primary_criterion": "criterion_id",
      "priority_note": "...",
      "relax_criterion": "criterion_id"
    }}
  ]
}}

Only include the keys relevant to the chosen resolution.
If no genuine trade-offs exist, return: {{"tradeoffs": []}}"""

        self._log(f"Analysing {len(rubric.criteria)} criteria for inverse correlations...")

        response = self.client.messages.create(
            model=self.model,
            max_tokens=4000,
            system=self.SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = response.content[0].text

        result: dict = {}
        m = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', raw)
        raw_json = m.group(1) if m else raw
        try:
            result = json.loads(raw_json.strip())
        except Exception:
            m2 = re.search(r'\{[\s\S]*\}', raw)
            if m2:
                try:
                    result = json.loads(m2.group())
                except Exception:
                    pass

        tradeoffs = result.get("tradeoffs", [])
        if not tradeoffs:
            self._log("No trade-offs detected.")
            return rubric, [], []

        # Build a mutable lookup; track criteria absorbed by a MERGE.
        criteria_map = {c.id: c for c in rubric.criteria}
        merged_ids: set = set()
        resolution_messages: List[str] = []
        tradeoff_context_blocks: List[str] = []

        for t in tradeoffs:
            cid_a = t.get("criterion_a", "")
            cid_b = t.get("criterion_b", "")
            resolution = t.get("resolution", "")
            explanation = t.get("explanation", "")

            if cid_a not in criteria_map or cid_b not in criteria_map:
                self._log(f"  Skipping unknown criterion pair: {cid_a!r}, {cid_b!r}")
                continue
            if cid_a in merged_ids or cid_b in merged_ids:
                continue  # one side already consumed by a prior merge

            if resolution == "merge":
                merged_desc = t.get("merged_description", "")
                merged_pass = t.get("merged_pass_condition", "")
                if not merged_desc:
                    self._log(f"  Skipping merge for ({cid_a}, {cid_b}): no merged_description")
                    continue
                base = criteria_map[cid_a]
                criteria_map[cid_a] = dc_replace(
                    base,
                    description=merged_desc,
                    pass_condition=merged_pass or base.pass_condition,
                )
                merged_ids.add(cid_b)
                msg = f"[merge] {cid_a} + {cid_b} → {cid_a} (balanced): {explanation[:80]}"
                resolution_messages.append(msg)
                self._log(f"  {msg}")

            elif resolution == "prioritize":
                primary = t.get("primary_criterion", cid_a)
                note = t.get("priority_note", f"{primary} takes precedence")
                secondary = cid_b if primary == cid_a else cid_a
                if secondary not in criteria_map:
                    secondary = cid_b
                # Do NOT mutate the criterion description — emit a generation context
                # note instead so the rubric criteria remain clean.  The note is
                # injected into the generation agent's prompt as a separate block.
                tradeoff_context_blocks.append(
                    f"DO NOT sacrifice '{primary}' for '{secondary}'. "
                    f"When these conflict, '{primary}' wins unconditionally. {note}"
                )
                msg = f"[prioritize] {primary} > {secondary}: {explanation[:80]}"
                resolution_messages.append(msg)
                self._log(f"  {msg}")

            elif resolution == "relax":
                relax_id = t.get("relax_criterion", cid_b)
                if relax_id not in criteria_map:
                    relax_id = cid_b
                relax_c = criteria_map[relax_id]
                old_pts = relax_c.scoring.max_points
                new_pts = max(1, int(old_pts * 0.7))
                new_scoring = dc_replace(relax_c.scoring, max_points=new_pts)
                criteria_map[relax_id] = dc_replace(relax_c, scoring=new_scoring)
                msg = f"[relax] {relax_id} max_points {old_pts} → {new_pts}: {explanation[:80]}"
                resolution_messages.append(msg)
                self._log(f"  {msg}")

            else:
                self._log(f"  Unknown resolution {resolution!r} for ({cid_a}, {cid_b}), skipping")

        # Reconstruct criteria in original order, dropping merged-away criteria.
        new_criteria = [
            criteria_map[c.id]
            for c in rubric.criteria
            if c.id not in merged_ids
        ]
        new_total = sum(c.scoring.max_points for c in new_criteria)
        refined_rubric = dc_replace(rubric, criteria=new_criteria, total_points=new_total)

        self._log(
            f"Resolved {len(tradeoffs)} trade-off(s): "
            f"{len(new_criteria)} criteria remain (was {len(rubric.criteria)}), "
            f"{new_total}pts total (was {rubric.total_points}pts)."
        )
        return refined_rubric, resolution_messages, tradeoff_context_blocks


class GenerationAgent:
    """Isolated content generation agent.

    Each call is a fresh, independent context window. The agent receives only:
    1. The task description
    2. Rubric criteria (what to optimize for)
    3. The best prior artifact + score breakdown (from file-based handoff)
    4. Focus areas for this iteration

    It never sees scorer reasoning, prior scoring history, or the negotiation
    transcript. This is the GAN-inspired separation: generator and evaluator
    operate in isolated contexts, preventing self-leniency bias.
    """

    SYSTEM_PROMPT = """You are a content generation specialist. Your role is to produce
high-quality content that satisfies specific rubric criteria. You receive:
- A task description
- Rubric criteria with pass/fail examples
- (On iterations 2+) The current best attempt and its score breakdown

You have access to a web search tool. Use it proactively whenever the task or
rubric requires specific facts, statistics, expert citations, recent research,
named individuals/institutions, or empirical evidence. Search BEFORE writing
so your content is grounded in real, verifiable information rather than
generic claims. Criteria that require specific evidence cannot be satisfied
without looking things up.

The harness uses observation masking: bulk content from older iterations is
offloaded to disk and resolved for you before being placed in this prompt.
You always receive the actual content of the best prior attempt — never a
file pointer. Focus entirely on improving the content to score higher.

Output the complete content only — no meta-commentary, no scoring rationale.
Produce content that earns high scores on every rubric criterion."""

    def __init__(self, model: str = "claude-sonnet-4-20250514", verbose: bool = True):
        if Anthropic is None:
            raise ImportError("anthropic package required: pip install anthropic")
        self.client = Anthropic(timeout=_API_TIMEOUT)
        self.model = model
        self.verbose = verbose

    def _log(self, msg: str):
        if self.verbose:
            print(f"[Generator] {msg}")

    def generate(self, prompt: str, max_tokens: int = 12000) -> str:
        """Generate content in an isolated context window with web search."""
        response = self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            system=self.SYSTEM_PROMPT,
            tools=[{
                "type": "web_search_20250305",
                "name": "web_search",
            }],
            messages=[{"role": "user", "content": prompt}],
        )
        # Response may include web_search_tool_result blocks; extract only text
        text_parts = [block.text for block in response.content if hasattr(block, "text")]
        raw = "\n".join(text_parts)
        return self._strip_preamble(raw)

    @staticmethod
    def _strip_preamble(text: str) -> str:
        """Remove meta-commentary preamble that the model sometimes emits.

        The system prompt instructs "no meta-commentary", but the model
        occasionally prefixes content with reasoning like "Based on the
        feedback, I'll..." or "Now I'll apply the specific fixes...".
        This pollutes the output and causes re-scoring failures.

        Strategy: detect paragraphs that start with meta-commentary signals
        and strip them.  A paragraph boundary is a blank line (``\\n\\n``).
        """
        import re

        preamble_starters = re.compile(
            r"^(?:"
            r"(?:Now\s+)?(?:I'?\u2019?ll|Let\s+me|I\s+will)\s+"
            r"|Based\s+on\s+"
            r"|Looking\s+at\s+"
            r"|However,?\s+since\s+"
            r"|I\s+need\s+to\s+"
            r"|Here\s+is\s+the\s+improved"
            r"|The\s+key\s+improvements"
            r"|Now\s+I\s+have\s+the\s+information"
            r")",
            re.IGNORECASE,
        )

        stripped = text.lstrip()
        for _ in range(5):  # strip up to 5 preamble paragraphs
            if not preamble_starters.match(stripped):
                break
            # Consume everything up to the next blank line (paragraph boundary)
            para_end = re.search(r"\n\s*\n", stripped)
            if para_end:
                stripped = stripped[para_end.end():].lstrip()
            else:
                break  # no paragraph boundary — don't strip everything

        # Postamble stripping: detect meta-commentary appended at the end
        postamble_signals = re.compile(
            r"(?:"
            r"\b(?:criterion|rubric|scoring|FIX\b|improvement)\b"
            r"|\bkey\s+(?:changes|improvements|updates)\b"
            r"|\bhere\s+is\s+the\s+improved\b"
            r"|\bthe\s+key\s+improvements\b"
            r")",
            re.IGNORECASE,
        )

        paragraphs = re.split(r"\n\s*\n", stripped)
        if len(paragraphs) > 2:
            strip_from = len(paragraphs)
            for i in range(len(paragraphs) - 1, max(len(paragraphs) - 4, 0), -1):
                para = paragraphs[i].strip()
                if not para:
                    strip_from = i
                    continue
                if postamble_signals.search(para):
                    strip_from = i
                else:
                    break
            if strip_from < len(paragraphs):
                stripped = "\n\n".join(paragraphs[:strip_from]).rstrip()

        # Safety: if stripping removed almost everything, return original.
        # Use 10-char absolute minimum so short-but-real content is kept.
        if len(stripped) < 10:
            return text.lstrip()
        return stripped


class ScoringEngine:
    """Calculates granular scores from measurements."""

    def score_criterion(
        self,
        criterion: Criterion,
        measurements: dict,
        violations: list[str] = None
    ) -> CriterionScore:

        method = criterion.scoring.method

        if method == ScoringMethod.WEIGHTED_COMPONENTS:
            return self._score_weighted(criterion, measurements)
        elif method == ScoringMethod.PENALTY_BASED:
            return self._score_penalties(criterion, violations or [])
        elif method == ScoringMethod.BINARY:
            passed = measurements.get("passed", False)
            points = criterion.scoring.max_points if passed else 0
            return CriterionScore(
                criterion_id=criterion.id,
                points_earned=points,
                max_points=criterion.scoring.max_points,
                percentage=1.0 if passed else 0.0,
                methodology="Binary: full points if pass, zero if fail"
            )
        elif method == ScoringMethod.THRESHOLD_TIERS:
            return self._score_threshold_tiers(criterion, measurements)
        else:
            pct = measurements.get("percentage", 0.0)
            points = criterion.scoring.max_points * pct
            return CriterionScore(
                criterion_id=criterion.id,
                points_earned=points,
                max_points=criterion.scoring.max_points,
                percentage=pct,
                methodology="Percentage-based"
            )

    def _score_weighted(self, criterion: Criterion, measurements: dict) -> CriterionScore:
        sub_scores = []
        total_weighted = 0.0
        method_parts = []

        for sub in criterion.scoring.sub_attributes:
            raw = measurements.get(sub.sub_id, 0.0)
            raw = max(0.0, min(1.0, raw))
            weighted = raw * sub.weight
            total_weighted += weighted

            sub_scores.append(SubScore(
                sub_id=sub.sub_id,
                raw_value=raw,
                weighted_value=weighted,
                evidence=measurements.get(f"{sub.sub_id}_evidence", ""),
                target=0.8
            ))
            method_parts.append(f"{sub.sub_id}: {raw:.0%}x{sub.weight:.0%}")

        points = criterion.scoring.max_points * total_weighted

        hints = []
        for ss in sorted(sub_scores, key=lambda x: x.raw_value):
            if ss.raw_value < 0.8:
                gap = 0.8 - ss.raw_value
                point_gain = gap * criterion.scoring.max_points * next(
                    (s.weight for s in criterion.scoring.sub_attributes if s.sub_id == ss.sub_id), 0
                )
                hints.append(f"{ss.sub_id}: {ss.raw_value:.0%} -> 80% (+{point_gain:.1f} pts)")

        return CriterionScore(
            criterion_id=criterion.id,
            points_earned=round(points, 2),
            max_points=criterion.scoring.max_points,
            percentage=total_weighted,
            sub_scores=sub_scores,
            methodology=f"Weighted: {' + '.join(method_parts)}",
            improvement_hints=hints[:3]
        )

    def _score_penalties(self, criterion: Criterion, violations: list[str]) -> CriterionScore:
        points = float(criterion.scoring.max_points)
        penalties_applied = []

        for v in violations:
            penalty = criterion.scoring.penalties.get(v, 0)
            if penalty:
                points += penalty
                penalties_applied.append({"violation": v, "penalty": penalty})

        # Log when applied penalties exceed max_points (scoring granularity loss)
        if penalties_applied:
            total_penalty_magnitude = sum(abs(p["penalty"]) for p in penalties_applied)
            if total_penalty_magnitude > criterion.scoring.max_points:
                self._log(
                    f"[Penalty] {criterion.id}: applied penalties "
                    f"{total_penalty_magnitude:.1f} exceed max_points "
                    f"{criterion.scoring.max_points}"
                )

        points = max(0, points)

        hints = [f"Fix {p['violation']} (+{abs(p['penalty']):.1f} pts)"
                 for p in sorted(penalties_applied, key=lambda x: x['penalty'])]

        return CriterionScore(
            criterion_id=criterion.id,
            points_earned=round(points, 2),
            max_points=criterion.scoring.max_points,
            percentage=points / criterion.scoring.max_points,
            penalties_applied=penalties_applied,
            methodology=f"Penalty: {criterion.scoring.max_points} - {sum(p['penalty'] for p in penalties_applied):.1f}",
            improvement_hints=hints[:3]
        )

    def _score_threshold_tiers(self, criterion: Criterion, measurements: dict) -> CriterionScore:
        value = measurements.get("value", 0.0)
        tiers = sorted(criterion.scoring.tiers.items(), reverse=True)
        matched_tier = 0.0
        tier_name = "none"
        for threshold, name in tiers:
            if value >= threshold:
                matched_tier = threshold
                tier_name = name
                break
        points = criterion.scoring.max_points * matched_tier
        return CriterionScore(
            criterion_id=criterion.id,
            points_earned=round(points, 2),
            max_points=criterion.scoring.max_points,
            percentage=matched_tier,
            evidence=f"Value {value:.1%} falls in tier: {tier_name}",
            methodology=f"Threshold tiers: {value:.1%} -> {tier_name} ({matched_tier:.0%})"
        )


# ============================================================================
# Measurement Extraction Prompt
# ============================================================================

MEASUREMENT_PROMPT = """You are a structured evaluation system implementing a two-stage scoring protocol: extract verifiable facts first (Stage 1), then derive scores mechanically from those facts (Stage 2).

CONTENT TO EVALUATE:
```
{content}
```

CRITERIA TO MEASURE:
{criteria_specs}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
STAGE 1 — CHECKLIST EXTRACTION (facts only, no scores yet)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

For EACH criterion and sub-attribute, extract binary observations. Be literal and specific.

For each sub-attribute, produce 3-4 specific binary checks:
### [criterion_id]
Sub-attribute [sub_id]:
  - [Specific observable requirement from the rubric]? YES / NO. Evidence: [exact quote or "not found"]
  - [Another specific observable requirement]? YES / NO. Evidence: [exact quote or "not found"]
  - Does the content go BEYOND rubric guidance with independent domain expertise on this sub-attribute? YES / NO. Evidence: [specific detail or "no evidence of independent insight"]

For penalty-based criteria:
  - Violation "[violation_name]": PRESENT / ABSENT. Evidence: [quote or "not found"]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
STAGE 2 — MECHANICAL SCORE DERIVATION (derived from Stage 1 facts)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

For each sub-attribute, count Stage 1 YES answers and apply these deterministic rules:

FOR weighted_components SUB-ATTRIBUTES (valid anchor values: 0.0, 0.25, 0.50, 0.75, 1.0):
  1.00 — ALL requirement checks YES + beyond-rubric check YES + content demonstrates exceptional, significantly-above-expectations expertise (rare — ≤15% of sub-attributes)
  0.75 — ALL requirement checks YES + beyond-rubric check YES (independent domain expertise)
  0.50 — ALL requirement checks YES + beyond-rubric check NO (rubric-directed, adequate) ← DEFAULT for correct AI output
  0.25 — MOST requirement checks YES (>50%) but key elements missing
  0.00 — FEW or NONE requirement checks YES (≤50%)

FOR penalty_based CRITERIA:
  Score = max_points − sum of deductions for each PRESENT violation from Stage 1

Do NOT override the mechanical mapping with subjective impressions. Stage 1 facts determine the scores.

CALIBRATION CHECK before writing JSON:
  - How many sub-attributes scored 1.0? Should be ≤15% of total sub-attributes.
  - How many sub-attributes scored 0.75 or above? Should be ≤35% of total sub-attributes.
  - For each 0.75 or 1.0, verify you can cite specific evidence of independent expertise beyond the rubric.
  - First-attempt AI output landing at 55-65% overall is expected and correct.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
OUTPUT FORMAT — SINGLE JSON with embedded critiques
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

IMPORTANT: Output ONLY a JSON block. Do NOT write a separate Stage 1 text section — embed all critiques INSIDE the JSON.

First complete your Stage 1 checklist analysis internally, then produce a single JSON block where every sub-attribute includes its score, its critique (the specific failed/passed checks with evidence), and what's missing:

```json
{{
  "criterion_id": {{
    "sub_attribute_id": {{
      "score": <float — must be one of: 0.0, 0.25, 0.5, 0.75, 1.0>,
      "checks": [
        {{"check": "description of what was checked", "result": "YES or NO", "evidence": "exact quote from content or 'not found'"}}
      ],
      "critique": "1-2 sentence summary of what specifically is wrong or right. Quote the content. If failing, state exactly what is missing.",
      "suggestion": "If score < 1.0, a specific instruction for what to add/change to improve this sub-attribute. Include example text where possible."
    }},
    "violations": ["violation_name_if_found"],
    "_meta": {{"checks_passed": <int>, "total_checks": <int>, "beyond_rubric": <bool>}}
  }}
}}
```

For penalty_based criteria, use a flat structure:
```json
{{
  "criterion_id": {{
    "violations": ["violation_name"],
    "violation_details": [
      {{"violation": "name", "evidence": "exact quote", "critique": "why this is a violation"}}
    ]
  }}
}}
```

CRITICAL RULES:
- Sub-attribute scores must use only anchor values (0.0, 0.25, 0.5, 0.75, 1.0).
- Every sub-attribute MUST have a non-empty "critique" field. Never return a score without explaining why.
- Every sub-attribute with score < 1.0 MUST have a non-empty "suggestion" field.
- The "evidence" in checks must be exact quotes from the content, or "not found in content" — never paraphrased.
- Scores must be mechanically derived from the checks — not independently estimated."""


CALIBRATION_ANCHORS = """
CALIBRATION ANCHORS — use these to ground your scoring:

ANCHOR A (Score: 45% overall): An AI-generated memo that mentions Benford's Law by name, lists journal entry
review as a methodology, and references ASC 606 — but the Benford's analysis uses fabricated numbers with no
statistical test, the journal entry methodology is described in one paragraph without sample size or threshold
discussion, and the financial impact is stated as a single unsourced dollar figure. This is RUBRIC COMPLIANCE
without ANALYTICAL DEPTH. Each criterion gets 0.25-0.50.

ANCHOR B (Score: 68% overall): An AI-generated memo with a plausible Benford's analysis (first-digit frequencies,
MAD calculation) but the data is hypothetical, the timeline reconstruction identifies suspicious patterns but
doesn't triangulate against independent sources, and the professional documentation section uses correct
terminology but doesn't address chain of custody or evidence admissibility. Some criteria at 0.75, most at 0.50.

ANCHOR C (Score: 88% overall): A memo where the Benford's analysis specifies the exact dataset used, calculates
MAD with proper interpretation, the journal entry methodology describes stratified sampling with threshold
rationale, the timeline cross-references financial data with communications evidence, and professional standards
are cited with specific section numbers. Multiple criteria at 0.75, one or two at 1.0, but still has gaps in
internal consistency or completeness.

Use these anchors to calibrate. If the content you're scoring resembles Anchor A more than B, score accordingly.
Most first-attempt AI output lands between A and B.
"""

def format_criteria_for_measurement(criteria: list[Criterion]) -> str:
    lines = [CALIBRATION_ANCHORS]
    for c in criteria:
        lines.append(f"\n=== {c.id} ({c.scoring.method.value}) ===")
        lines.append(f"Description: {c.description}")
        if c.pass_condition:
            lines.append(f"Pass condition: {c.pass_condition}")

        if c.pass_examples:
            lines.append(f"PASSING EXAMPLE (what 1.0 looks like): {c.pass_examples[0]}")
        if c.fail_examples:
            lines.append(f"NEAR-MISS FAILURE EXAMPLE (what 0.5 looks like): {c.fail_examples[0]}")

        if c.scoring.sub_attributes:
            lines.append("Sub-attributes to score (use anchor values: 0.0, 0.25, 0.5, 0.75, 1.0):")
            for sub in c.scoring.sub_attributes:
                lines.append(f"  - {sub.sub_id} (weight {sub.weight:.0%}): {sub.description}")
                lines.append(f"    Measurement scale: {sub.measurement}")

        if c.scoring.penalties:
            lines.append("Hunt for these violations (list each one found in the 'violations' array):")
            for v, p in c.scoring.penalties.items():
                lines.append(f"  - {v} (penalty: {p} pts)")

    return "\n".join(lines)


# ============================================================================
# Generation Prompt with Granular Feedback
# ============================================================================

GENERATION_PROMPT = """Complete the following task to the best of your ability.

TASK: {task}

{history_section}

{focus_section}

Output complete, high-quality content."""


EDIT_PROMPT = """You are improving an existing document. Your job is to SURGICALLY EDIT the weak sections while PRESERVING everything that already scores well.

TASK: {task}

CRITICAL CONSTRAINT: You MUST preserve quality on criteria that are already scoring well.
The following criteria scored >= 90% and must NOT regress:
{protected_criteria_list}

Focus improvements ONLY on these weak criteria:
{improvement_targets_list}

Make surgical, targeted improvements. Do NOT rewrite from scratch.

CURRENT DRAFT (score: {current_score}):
--- BEGIN CONTENT ---
{current_content}
--- END CONTENT ---

{regression_section}

{iteration_guidance}

CRITICAL RULES:
1. DO NOT rewrite sections that already score >= 90%. Copy them VERBATIM.
2. ONLY rewrite or expand sections corresponding to criteria marked IMPROVE.
3. Keep the same overall structure, headings, and section ordering.
4. The STRUCTURED FEEDBACK FROM EVALUATOR below is your SOLE instruction set. Follow its ACTION items precisely — each one tells you exactly what to add or change, quoting the scorer's own checks and evidence.
5. Do NOT reconcile multiple signals. The structured feedback already incorporates scores, regressions, and failed checks into a single prioritized list. Just execute it.
6. Output the COMPLETE improved document — not just the changed parts.
7. When improving a section, add specificity, quantitative detail, and technical depth — don't just rephrase.
8. For each fix instruction, make the MINIMUM change needed. Don't rewrite surrounding paragraphs.
"""


def format_rubric_for_generation(rubric: Rubric) -> str:
    lines = []
    for c in rubric.criteria:
        lines.append(f"\n{'─'*50}")
        lines.append(f"  {c.id} ({c.scoring.max_points} points)")
        lines.append(f"   {c.description}")

        if c.scoring.sub_attributes:
            lines.append("   Sub-scores (weighted):")
            for sub in c.scoring.sub_attributes:
                lines.append(f"     - {sub.sub_id} ({sub.weight:.0%}): {sub.description}")

        if c.pass_examples:
            lines.append("   PASS: " + c.pass_examples[0])
        if c.fail_examples:
            lines.append("   FAIL: " + c.fail_examples[0])

        if c.research_basis:
            basis = c.research_basis[:120]
            if c.research_basis.startswith("[HALLUCINATED"):
                lines.append(f"   ⚠ RESEARCH: {basis}")
            elif c.research_basis.startswith("[Partial"):
                lines.append(f"   ◐ RESEARCH: {basis}")
            else:
                lines.append(f"   ✓ RESEARCH: {basis}")

    return "\n".join(lines)


def format_history_for_generation(history: list[Iteration]) -> str:
    if not history:
        return ""

    last = history[-1]
    lines = [f"\nPREVIOUS ATTEMPT: {last.percentage:.0%} ({last.total_score:.1f}/{last.max_score} points)"]
    lines.append("\nSub-scores needing improvement:")

    all_subs = []
    for cs in last.criterion_scores:
        for ss in cs.sub_scores:
            if ss.raw_value < 0.8:
                all_subs.append((cs.criterion_id, ss))

    all_subs.sort(key=lambda x: x[1].raw_value)

    for crit_id, ss in all_subs[:5]:
        lines.append(f"  {crit_id}.{ss.sub_id}: {ss.raw_value:.0%} (target: 80%)")
        if ss.evidence:
            lines.append(f"     Evidence: {ss.evidence}")

    for cs in last.criterion_scores:
        for p in cs.penalties_applied[:2]:
            lines.append(f"  {cs.criterion_id}: {p['violation']} ({p['penalty']} pts)")

    return "\n".join(lines)


def format_focus_for_generation(focus_areas: list[tuple[str, str, float]]) -> str:
    if not focus_areas:
        return ""

    lines = ["\nPRIORITY IMPROVEMENTS (biggest point gains):"]
    for crit_id, sub_id, current in focus_areas[:3]:
        gap = 0.8 - current
        lines.append(f"  1. {crit_id}.{sub_id}: {current:.0%} -> 80% (gap: {gap:.0%})")

    return "\n".join(lines)


def parse_stage1_per_criterion(stage1_text: str, criterion_ids: list[str]) -> dict[str, str]:
    """Parse Stage 1 checklist text into per-criterion critique blocks.

    The scorer outputs Stage 1 in this format:
        ### criterion_id
        Sub-attribute sub_id:
          - [check]? YES / NO. Evidence: ...
        ### next_criterion_id
        ...

    Returns:
        dict mapping criterion_id -> critique text block
    """
    if not stage1_text:
        return {}

    critiques = {}
    # Split on ### headers that match known criterion IDs
    parts = re.split(r'###\s+(\S+)', stage1_text)

    # parts[0] is text before first ###, then alternating: id, text, id, text...
    for i in range(1, len(parts) - 1, 2):
        crit_id = parts[i].strip()
        crit_text = parts[i + 1].strip() if i + 1 < len(parts) else ""
        if crit_id in criterion_ids:
            critiques[crit_id] = crit_text

    return critiques


# ============================================================================
# Rubric Generator — builds bespoke rubrics for any task via LLM
# ============================================================================

RUBRIC_GENERATION_PROMPT = """You are a rubric architect and domain expert calibration system. Your job is to produce a RIGOROUS, FINE-GRAINED scoring rubric that discriminates between expert (75-85%), competent (65-75%), and weak (below 65%) responses.

TASK:
{task}

{context_section}

CORE PHILOSOPHY:
Test JUDGMENT, not KNOWLEDGE. Focus on areas where domain experts would disagree on quality - nuanced trade-offs, contextual appropriateness, and subjective professional judgment calls. Avoid criteria that test factual correctness or comprehensive coverage (LLMs excel at these). Instead, test: "Given multiple technically correct approaches, did they choose the most appropriate one for this context?" The rubric should evaluate decisions where reasonable people disagree, but experts can distinguish quality levels.

INSTRUCTIONS:

1. DECOMPOSE DEEPLY before writing criteria. For any broad quality dimension, break it into 2-4 atomic sub-criteria. Do NOT write a single criterion called "evidence quality" — instead write separate criteria for: primary source citation, chain of custody, cross-referencing between independent sources, quantitative vs qualitative evidence ratio, statistical significance of findings. Each becomes its own measurable criterion.

2. Generate criteria proportional to task complexity. Simple tasks may need 8-12; complex multi-dimensional tasks should have 15-30+. Focus on DEPTH — each criterion should test expert-level judgment that requires deep domain knowledge. A first attempt that "covers everything at a surface level" should score 40-50%. Each criterion should require genuine expertise to score well, not just comprehensive coverage.

3. Assign max_points reflecting granularity: most criteria should be 3-5 points. Reserve 6-8 points ONLY for the most critical expert-level criteria. Do NOT use 10-12 point criteria — that makes the rubric too coarse.

4. MANDATORY: At least 3 criteria MUST use penalty_based scoring. These should catch specific technical errors, omissions, or professional anti-patterns that a domain expert would immediately flag. Each penalty criterion needs 5+ named violations with specific penalty values.

5. For each criterion, choose scoring method:
   - "weighted_components": Quality is a composite of measurable sub-dimensions. Each sub-attribute must measure something DISTINCT and SPECIFIC. Weights must sum to 1.0.
   - "penalty_based": Start at max and deduct for named violations. Use for anti-patterns, professional errors, missing required elements.
   - "binary": Only for structural requirements with no gradient (use very sparingly, max 2 per rubric).

6. ANTI-GAMING: Criteria must test CONTEXTUAL JUDGMENT that requires weighing trade-offs:
   - Appropriateness of approach for the specific context (not just technical correctness)
   - Quality of reasoning about edge cases and limitations (not just acknowledging they exist)
   - Sophistication of trade-off analysis between competing valid options
   - Professional judgment calls where multiple approaches are defensible but some are more suitable
   - Nuanced understanding of when standard approaches should be modified

7. Set pass_threshold between 0.65-0.75:
   - Technical/analytical tasks: 0.68-0.75
   - Creative/writing tasks: 0.65-0.70

8. EXPERT vs JUNIOR DELTA: For every criterion, ask: "Would a junior analyst satisfy this?" If yes, make it harder. Add a sub-attribute that tests for something juniors routinely miss. The rubric should have at least 5 criteria that a confident-but-shallow LLM response will fail. Each criterion must have a pass_condition with clear performance gradients: define what constitutes 40%, 60%, and 80% performance levels. Ensure that competent responses can achieve 60-70% while expert responses reach 80%+.

{examples_section}

OUTPUT FORMAT — valid JSON only, no markdown fences:
{{
  "domain": "<short domain label for this task type>",
  "pass_threshold": <float>,
  "criteria": [
    {{
      "id": "<short_snake_case>",
      "category": "<category>",
      "description": "<what this criterion evaluates — be specific about what expert-level looks like>",
      "pass_condition": "<concrete threshold with NUMBERS: minimum counts (e.g. '3+ sources'), specific percentages (e.g. '80% accuracy'), named techniques (e.g. 'uses Monte Carlo simulation'), measurable standards — NO vague adjectives>",
      "scoring_method": "weighted_components|penalty_based|binary",
      "max_points": <int 3-8>,
      "sub_attributes": [
        {{
          "sub_id": "<snake_case>",
          "description": "<what this measures — one specific thing>",
          "weight": <float 0.0-1.0>,
          "measurement": "<graduated scale: 1.0 if [specific expert condition], 0.7 if [competent but incomplete], 0.4 if [surface-level only], 0.0 if [absent or wrong]>"
        }}
      ],
      "penalties": {{
        "<specific_violation_name>": <negative_float>,
        ...
      }},
      "pass_examples": ["<specific example showing exactly what passing looks like — quote format, terminology, or structure>"],
      "fail_examples": ["<plausible near-miss failure — what 'almost good enough but not quite' looks like, not an obviously terrible example>"],
      "research_basis": "<REQUIRED: cite the specific research finding, professional standard, or expert practice that grounds this criterion. Format: '[Source/Standard] requires/recommends [specific requirement]'. Example: 'AICPA SSFS No. 1 §4.02 requires forensic accountants to document chain of custody for all evidence.' If no research was provided, state 'No research basis — criterion based on domain knowledge.' Criteria without research grounding will be flagged for review.>"
    }}
  ]
}}

HARDENING RULES — these are NOT optional:
- No cap on criteria count. Generate as many as the task demands for comprehensive verification. A complex task should have 15-30+ criteria. If you have fewer than 12, you are being too coarse — decompose further.
- At least 3 penalty_based criteria with 5+ violations each. Penalty criteria catch professional errors a surface response would miss.
- Every weighted_components criterion must have at least one sub-attribute testing CORRECTNESS and PRECISION, not just PRESENCE. "1.0 if present, 0.0 if absent" is banned — it produces binary scores that don't discriminate quality.
- At least 2 "expert stretch" criteria testing domain-specific precision that a junior or LLM would fail on (e.g., correct statistical test selection, proper regulatory citation format, methodology limitation acknowledgment).
- All pass_conditions must include CONCRETE thresholds with specific counts or named techniques. "Well-analyzed" is banned. "Identifies ≥3 specific journal entry anomalies with account codes and dollar amounts" is correct.
- fail_examples must show PLAUSIBLE near-misses — something that looks good but falls short on precision or depth.
- The rubric must be calibrated so a first-attempt output scores 55-65%, not 80-90%. If all criteria seem easy to satisfy, you haven't decomposed enough or made the bar high enough.

RUBRIC HARDENING RULES (critical for quality):
- At least 2 criteria must use penalty_based scoring with 4+ violations each
- Every weighted_components criterion must have at least one sub-attribute that tests for SPECIFIC
  technical accuracy, not just "is it present" but "is it correct and precise"
- Include at least one "stretch" criterion that tests for expert-level quality (something a junior
  would miss but a senior expert would catch). This should be worth 6-8 points.
- Pass conditions must include CONCRETE thresholds: "at least 3 specific examples", "under 200 words",
  "cites 2+ authoritative sources", not vague standards like "thorough" or "well-written"
- Measurements must produce a RANGE of scores, not binary. A measurement like "1.0 if present, 0.0 if
  absent" is too coarse. Instead: "1.0 if specific + sourced, 0.7 if specific but unsourced, 0.4 if
  vague, 0.0 if absent"
- fail_examples should include PLAUSIBLE failures, not obviously terrible ones. Show what "almost good
  enough but not quite" looks like.
- The rubric should be calibrated so that Claude's FIRST attempt scores 60-75%, not 90%+. If the task
  is easy enough that a first attempt could score 90%+, add harder criteria.

- Output ONLY the JSON object, nothing else"""


RUBRIC_GEN_EXAMPLES = """EXAMPLE — for the task "Write a cold outreach email to a Series A founder":

{
  "domain": "cold_outreach_email",
  "pass_threshold": 0.80,
  "criteria": [
    {
      "id": "email_subject",
      "category": "engagement",
      "description": "Subject line is compelling and specific — not generic or spammy",
      "pass_condition": "Subject is <60 chars, references something specific to the recipient, creates curiosity without clickbait.",
      "scoring_method": "weighted_components",
      "max_points": 10,
      "sub_attributes": [
        {"sub_id": "specificity", "description": "References recipient's company/round/domain", "weight": 0.40, "measurement": "1.0 if names company or specific context, 0.0 if generic"},
        {"sub_id": "brevity", "description": "Under 60 chars, scannable on mobile", "weight": 0.25, "measurement": "1.0 if ≤60 chars, 0.5 if ≤80, 0.0 if >80"},
        {"sub_id": "curiosity_hook", "description": "Creates reason to open without being clickbait", "weight": 0.35, "measurement": "1.0 if compelling + honest, 0.5 if generic, 0.0 if spammy"}
      ],
      "penalties": {},
      "pass_examples": ["'$2M angel check for Acme's Series A — operator background in logistics'"],
      "fail_examples": ["'Quick question'", "'Exciting investment opportunity!'"]
    },
    {
      "id": "email_tone",
      "category": "voice",
      "description": "Tone is peer-to-peer, confident but not presumptuous",
      "pass_condition": "Reads like one founder talking to another. Not sycophantic, not salesy, not formal.",
      "scoring_method": "penalty_based",
      "max_points": 6,
      "sub_attributes": [],
      "penalties": {
        "sycophantic_language": -2.0,
        "salesy_pressure": -2.0,
        "overly_formal": -1.5,
        "presumptuous_familiarity": -1.5
      },
      "pass_examples": ["Direct, warm, brief — reads like a text from a smart friend"],
      "fail_examples": ["'I'd be truly honored to be part of your incredible journey'"]
    }
  ]
}

EXAMPLE — for the task "Write a bash script that backs up PostgreSQL to S3":

{
  "domain": "bash_scripting",
  "pass_threshold": 0.85,
  "criteria": [
    {
      "id": "bash_safety",
      "category": "reliability",
      "description": "Script is safe — set -euo pipefail, no secrets in code, cleanup on failure",
      "pass_condition": "set -euo pipefail. Trap for cleanup. No hardcoded passwords.",
      "scoring_method": "penalty_based",
      "max_points": 10,
      "sub_attributes": [],
      "penalties": {
        "no_set_e": -2.0,
        "no_pipefail": -1.5,
        "hardcoded_password": -3.0,
        "no_trap_cleanup": -1.5,
        "unquoted_variables": -1.0
      },
      "pass_examples": ["set -euo pipefail, trap cleanup EXIT, reads creds from env"],
      "fail_examples": ["No error handling, password in script"]
    }
  ]
}"""


RESEARCH_PROMPT = """You are a domain research specialist. Your job is to research what industry experts, practitioners, and authoritative sources consider "excellent" for a specific type of task.

TASK TO RESEARCH:
{task}

RESEARCH GOALS:
1. Find what domain experts consider best practices for this type of work
2. Identify specific quality standards, frameworks, or checklists used by professionals
3. Discover common failure modes that experts watch for
4. Find measurable dimensions of quality that separate good from great

RESEARCH APPROACH:
- Search for professional standards, style guides, industry benchmarks
- Look for expert blogs, authoritative publications, professional associations
- Find real evaluation criteria used in the field (not generic advice)
- Prioritize sources that are specific and measurable over vague guidance

OUTPUT FORMAT:
Provide a structured research brief with these sections:

DOMAIN CONTEXT: What field/discipline does this task fall under? What role typically does this?

EXPERT QUALITY STANDARDS: What do professionals in this field consider the key dimensions of quality? Be specific — cite frameworks, standards, or expert consensus where possible.

MEASURABLE CRITERIA: List 5-10 specific, measurable things an expert would check. For each, explain:
- What to measure
- What "great" looks like vs. "acceptable" vs. "poor"
- Why it matters (the consequence of getting it wrong)

COMMON FAILURE MODES: What are the most frequent ways this type of task goes wrong? What do experts specifically watch for?

NON-OBVIOUS QUALITY SIGNALS: What separates truly excellent work from merely competent work in this domain? What would an expert notice that a generalist would miss?

Be concrete and specific. Cite real standards, frameworks, or practices where possible. Avoid generic advice like "be clear" or "be thorough" — instead say exactly what clarity or thoroughness means in this context."""


EXPERT_PERSONA_PROMPT = """You are an expert profiler. Given a task description, identify the ideal human expert who would evaluate the output of that task at the highest professional level.

TASK:
{task}

Write a 3-5 sentence expert persona profile that answers:
1. What credentials and experience would this evaluator have? (degrees, certifications, years of practice, industry background)
2. What domain-specific quality signals would they focus on that a generalist would overlook?
3. What common mistakes or anti-patterns would they immediately catch that a generalist would miss?
4. What professional standards, frameworks, or benchmarks would they hold the output to?

Write the persona in second person ("You are..."). Be specific and concrete — name real credentials, real frameworks, real standards. Avoid generic descriptions like "experienced professional" — say exactly what kind of expert, from what background, with what specific knowledge.

Output only the persona description. No preamble, no headers, no explanation."""


EXPERT_PANEL_PROMPT = """You are an expert panel designer. For evaluating the output of a specific task, identify 3 complementary expert roles whose perspectives would collectively ensure comprehensive evaluation. Each expert must have a DIFFERENT vantage point — they should catch different types of quality issues that the others might miss.

TASK:
{task}

For each expert provide:
- role: their specific professional title (not generic)
- expertise: their domain background and credentials (2-3 sentences)
- unique_focus: what they uniquely care about that the other two would likely overlook
- dimensions: list of 2-3 specific quality dimensions they would focus on

Output ONLY valid JSON in this exact format:
{{
  "panel": [
    {{
      "role": "Senior Investment Analyst",
      "expertise": "10+ years in equity research at a top-tier investment bank. CFA charterholder with deep experience in DCF modeling, comparable company analysis, and sector-specific valuation. Has evaluated hundreds of investment memos across growth and value contexts.",
      "unique_focus": "Financial modeling rigor and valuation methodology — checks whether assumptions are grounded in data, whether the comp set is defensible, whether the bull/bear cases are mathematically consistent.",
      "dimensions": ["Valuation methodology", "Financial model integrity", "Comparable analysis quality"]
    }},
    {{
      "role": "Portfolio Risk Manager",
      "expertise": "...",
      "unique_focus": "...",
      "dimensions": ["..."]
    }},
    {{
      "role": "Operating Partner / Former Founder",
      "expertise": "...",
      "unique_focus": "...",
      "dimensions": ["..."]
    }}
  ]
}}

The three experts must cover genuinely different angles. No role should duplicate another's focus area. Tailor all three roles specifically to the task domain."""


EXPERT_PANEL_RECONCILE_PROMPT = """You are a rubric architect performing expert panel reconciliation. Three domain experts have each generated evaluation criteria for the same task. Your job is to produce a single unified, non-redundant criteria list that captures the best insights from all three perspectives.

TASK:
{task}

EXPERT PANEL:
{panel_summary}

CRITERIA FROM EACH EXPERT:
{all_criteria_json}

RECONCILIATION RULES:
1. MERGE DUPLICATES: If two or more experts covered the same dimension, keep only the most rigorous version (the one with more specific, measurable sub-attributes). Do not keep both.
2. RESOLVE CONFLICTS: If experts assign different weights to similar criteria, use the higher weight for criteria that are truly critical to quality.
3. IDENTIFY GAPS: Are there important quality dimensions that NO expert covered? Add 1-2 criteria for genuine gaps only (not padding).
4. PRESERVE DIVERSITY: Keep unique criteria from each expert — the whole point is multi-perspective coverage.
5. NORMALIZE IDs: Assign clean sequential IDs (C01, C02, ...). Do not preserve original expert-specific IDs.
6. BALANCE POINTS: Total points should be in the 60-120 range. No single criterion should exceed 20% of total points.

Output ONLY valid JSON:
{{
  "domain": "<domain string>",
  "pass_threshold": 0.85,
  "criteria": [
    {{
      "id": "C01",
      "category": "<category>",
      "description": "<criterion description>",
      "pass_condition": "<measurable pass condition>",
      "scoring_method": "<weighted_components|penalty_based|binary|percentage|threshold_tiers|count_based>",
      "max_points": 10,
      "sub_attributes": [],
      "penalties": {{}},
      "tiers": {{}},
      "pass_examples": [],
      "fail_examples": [],
      "research_basis": "<source expert role or rationale>"
    }}
  ]
}}"""


EXEMPLAR_SEARCH_PROMPT = """You are an exemplar research specialist. Your job is to find real, high-quality example outputs for a specific type of task — the kind produced by top practitioners in the field.

TASK TYPE TO FIND EXAMPLES FOR:
{task}

SEARCH GOALS:
1. Find 2-4 actual expert-quality example outputs or templates for this task type
2. Focus on what makes them distinctively better than average — not just "well-written" but specifically expert
3. Extract the most discriminating features: what would a naive LLM miss that an expert gets right?

SEARCH APPROACH:
- Search for "example [task type] by expert", "award-winning [task type]", "professional [task type] sample", "model [task type] template"
- Look for examples cited by practitioners as exemplary, not just any available example
- Target industry publications, professional portfolios, award winners, canonical references

OUTPUT FORMAT:
Provide an EXEMPLAR BRIEF with these sections:

EXEMPLAR SOURCES: What sources/examples did you find? (2-4 examples, with their notable qualities)

DISTINCTIVE EXPERT FEATURES: For each exemplar, extract 3-5 specific features that distinguish expert work from default output. Be concrete — not "high quality" but "uses specific technique X" or "avoids common error Y".

EXPERT-VS-DEFAULT GAP: What are the top 3-5 dimensions where expert output is most clearly superior to what a default LLM would produce? What would the LLM get approximately right but subtly wrong?

Be specific and concrete. The goal is to identify criteria that require real domain knowledge to evaluate — not just "is it clear?" but "does it use technique X?" or "does it avoid failure mode Y that beginners commonly hit?" """


CONTRASTIVE_CRITERIA_PROMPT = """You are a rubric calibration specialist. Your job is to derive DISCRIMINATIVE scoring criteria by analyzing the gap between expert-quality outputs and what a default LLM produces.

TASK:
{task}

EXPERT EXEMPLAR BRIEF:
{exemplar_brief}

BASELINE OUTPUT (what Claude produces without guidance):
{baseline}

YOUR JOB:
Analyze where the baseline output falls short of the expert exemplars. For each dimension where expert output is clearly superior, generate ONE criterion that:
1. Would score the expert output at 90-100%
2. Would score the baseline output at 40-60%
3. Requires domain knowledge to evaluate — not just "is it clear?" but something that a generalist reviewer would likely miss
4. Is specific and measurable — has concrete pass/fail indicators

CRITICAL: These criteria must be discriminating. If the baseline and expert output would score similarly, the criterion is not discriminating enough. Only include criteria where you can clearly see the gap.

OUTPUT FORMAT:
Generate 3-6 contrastive criteria as a JSON array:

```json
[
  {{
    "id": "contrastive_[descriptive_name]",
    "category": "[category]",
    "description": "[what this criterion measures — be specific]",
    "pass_condition": "[concrete, specific condition for passing — cite the expert technique/standard]",
    "expert_score_rationale": "[why expert output scores high — what specifically they do]",
    "baseline_gap": "[what the baseline gets wrong or misses — be concrete]",
    "domain_signal": "[why this requires domain knowledge to evaluate]"
  }}
]
```

RULES:
- Generate ONLY criteria where you can see a clear, specific gap between expert and baseline
- Each criterion must be grounded in the expert exemplar brief — not invented
- If you cannot find 3 genuinely discriminating criteria, generate fewer — quality over quantity
- Do NOT generate criteria the baseline already satisfies well
- Do NOT generate generic quality criteria (e.g., "is clear", "is organized") — these are not discriminating"""


# ============================================================================
# Multi-Pass Rubric Generation Prompts
# ============================================================================

DIMENSION_DECOMPOSITION_PROMPT = """You are a domain expert assembling a panel of evaluators for a task. Your job is to identify the major evaluation DIMENSIONS — the distinct axes of quality that a panel of experts would assess.

TASK:
{task}

{persona_section}

{research_section}

YOUR JOB:
Think like a panel of domain experts assembled to evaluate work on this task. What are ALL the major dimensions they would assess? Miss nothing. Each dimension should be a distinct axis of quality with minimal overlap with others.

Generate 6-12 evaluation dimensions. Each dimension represents a major area of expertise required to do this task well.

EXAMPLE — for an investment memo task:
[
  {{"id": "financial_analysis", "name": "Financial Analysis", "scope": "Quantitative modeling, valuation methodology, projection quality, and financial assumptions.", "weight": 0.18}},
  {{"id": "market_assessment", "name": "Market Assessment", "scope": "TAM/SAM/SOM analysis, market dynamics, growth drivers, and addressable opportunity sizing.", "weight": 0.14}},
  {{"id": "risk_framework", "name": "Risk Framework", "scope": "Risk identification, quantification, mitigation strategies, and scenario analysis.", "weight": 0.12}},
  {{"id": "investment_thesis", "name": "Investment Thesis", "scope": "Core value proposition, differentiation, and investment rationale clarity.", "weight": 0.14}},
  {{"id": "competitive_positioning", "name": "Competitive Positioning", "scope": "Competitive landscape, moats, defensibility, and differentiation sustainability.", "weight": 0.12}},
  {{"id": "management_assessment", "name": "Management Assessment", "scope": "Team quality, track record, execution capability, and key-person risk.", "weight": 0.10}},
  {{"id": "deal_structure", "name": "Deal Structure", "scope": "Terms, governance, cap table, and alignment of incentives.", "weight": 0.10}},
  {{"id": "exit_analysis", "name": "Exit Analysis", "scope": "Liquidity paths, comparable transactions, return potential, and hold period.", "weight": 0.10}}
]

OUTPUT FORMAT — valid JSON array only, no markdown fences:
[
  {{
    "id": "<short_snake_case_id>",
    "name": "<Dimension Name>",
    "scope": "<2-3 sentence description of what this dimension covers and what expert-level looks like>",
    "weight": <float 0.0-1.0, all weights must sum to 1.0>
  }}
]

RULES:
- Generate 6-12 dimensions
- Weights must sum to exactly 1.0 (within 0.01 tolerance)
- Each dimension must be distinct — no significant overlap with others
- Every dimension must be genuinely important for expert evaluation of this specific task
- Output ONLY the JSON array, nothing else"""


DIMENSION_CRITERIA_PROMPT = """You are a rubric architect generating scoring criteria for ONE specific evaluation dimension.

TASK:
{task}

DIMENSION TO EVALUATE:
Name: {dimension_name}
Scope: {dimension_scope}

{persona_section}

{research_section}

YOUR JOB:
Generate 2-5 criteria that evaluate this dimension deeply and specifically. Each criterion must:
1. Be specific to this dimension — not generic quality signals
2. Test expert-level judgment that requires domain knowledge to evaluate
3. Discriminate between junior-level and expert-level work on this dimension
4. Have concrete, measurable pass conditions with numbers or named techniques

INSTRUCTIONS:
- DECOMPOSE DEEPLY: break broad quality into atomic sub-criteria
- Test JUDGMENT, not just KNOWLEDGE: focus on decisions where reasonable experts could disagree
- Each criterion should fail for a "competent but generic" response
- Pass conditions must use NUMBERS: counts, percentages, named techniques — never vague adjectives

OUTPUT FORMAT — valid JSON array of criteria only, no markdown fences:
[
  {{
    "id": "<short_snake_case — prefix with dimension id if helpful for uniqueness>",
    "category": "<category matching the dimension>",
    "description": "<what this criterion evaluates — specific about what expert-level looks like>",
    "pass_condition": "<concrete threshold with NUMBERS: minimum counts, specific percentages, named techniques>",
    "scoring_method": "weighted_components|penalty_based|binary",
    "max_points": <int 3-8>,
    "sub_attributes": [
      {{
        "sub_id": "<snake_case>",
        "description": "<what this measures — one specific thing>",
        "weight": <float 0.0-1.0, sub-attribute weights must sum to 1.0>,
        "measurement": "<graduated scale: 1.0 if [specific expert condition], 0.7 if [competent but incomplete], 0.4 if [surface-level only], 0.0 if [absent or wrong]>"
      }}
    ],
    "penalties": {{
      "<specific_violation_name>": <negative_float>
    }},
    "pass_examples": ["<specific example showing exactly what passing looks like>"],
    "fail_examples": ["<plausible near-miss failure — almost good enough but not quite>"],
    "research_basis": "<cite the specific research finding, professional standard, or expert practice that grounds this criterion>"
  }}
]

RULES:
- Generate 2-5 criteria — quality over quantity
- For penalty_based: use when violations subtract from a perfect baseline; include 4+ named violations with specific negative float values
- For weighted_components: sub-attribute weights must sum to 1.0; measurements must produce a RANGE of scores (never "1.0 if present, 0.0 if absent")
- Output ONLY the JSON array, nothing else"""


CALIBRATION_PROMPT = """You are a rubric calibration expert. You have received criteria generated by multiple domain experts, each covering a different evaluation dimension. Your job is to produce a final, unified, well-calibrated rubric.

TASK:
{task}

EVALUATION DIMENSIONS (with target weight allocations):
{dimensions_section}

ALL CRITERIA FROM ALL DIMENSIONS ({total_criteria} total):
{criteria_section}

YOUR TASKS — perform ALL of these:

1. REMOVE REDUNDANCY: Identify criteria that overlap significantly. Merge overlapping criteria into the most specific version, keeping the stronger measurement standard.

2. REBALANCE POINTS: Calculate the current point share per dimension. If any dimension exceeds 30% of total points, scale down its criteria max_points. No single dimension should dominate.

3. ADD CROSS-CUTTING CRITERIA (add exactly 2-3): Add criteria that evaluate COHERENCE between dimensions — e.g.:
   - "Do the financial projections align with the market sizing?"
   - "Are the identified risks reflected in the proposed deal structure?"
   - "Does the investment thesis follow logically from the competitive and market analysis?"
   These cross-cutting criteria should test internal consistency of the whole, not any one section.

4. VERIFY FINAL COUNT: Final rubric should have 15-35 criteria. If under 15, you removed too many. If over 35, trim the weakest/most redundant further.

5. SET METADATA: Provide domain label and pass_threshold (0.65-0.75 based on task complexity).

OUTPUT FORMAT — valid JSON only, no markdown fences:
{{
  "domain": "<short domain label>",
  "pass_threshold": <float 0.65-0.75>,
  "criteria": [
    {{
      "id": "<short_snake_case>",
      "category": "<category>",
      "description": "<description>",
      "pass_condition": "<concrete threshold with numbers>",
      "scoring_method": "weighted_components|penalty_based|binary",
      "max_points": <int 3-8>,
      "sub_attributes": [
        {{
          "sub_id": "<snake_case>",
          "description": "<what this measures>",
          "weight": <float, sub-attribute weights must sum to 1.0>,
          "measurement": "<graduated measurement scale>"
        }}
      ],
      "penalties": {{
        "<violation_name>": <negative_float>
      }},
      "pass_examples": ["<example>"],
      "fail_examples": ["<example>"],
      "research_basis": "<research basis>"
    }}
  ]
}}

CALIBRATION RULES:
- No dimension should represent more than 30% of total points
- Total criteria count: 15-35 (hard limits)
- Cross-cutting criteria must test coherence between 2+ dimensions, not individual section quality
- Prefer retaining criteria that are specific, measurable, and test expert judgment; trim vague ones
- Preserve penalty_based criteria — they catch professional errors generic responses miss
- Output ONLY the JSON object, nothing else"""


class RubricAgent:
    """Independent rubric creation agent with isolated context window.

    The rubric agent operates in its own context — it never sees the generation
    agent's output, the scoring agent's measurements, or the evaluation agent's
    pass/fail decisions. It only receives:
    1. The task description
    2. Domain research from web search
    3. Few-shot seed rubrics from the registry
    4. Learning context from prior evaluations

    This isolation ensures rubric creation is grounded in domain expertise and
    research, not influenced by generation patterns or scoring heuristics.
    """

    RUBRIC_AGENT_SYSTEM_PROMPT = """You are a rubric architect — a domain expert who designs precise, measurable scoring rubrics for evaluating task outputs.

RUBRIC DESIGN PRINCIPLES:

1. GROUNDED IN RESEARCH: Every criterion must trace back to real-world professional standards, industry best practices, or domain-specific quality frameworks discovered through research. Never invent criteria from generic intuition.

2. MEASURABLE OVER ASPIRATIONAL: Each criterion must have concrete, binary-checkable sub-attributes. "Is thorough" is bad. "Contains at least 3 specific examples with citations" is good. A scorer should be able to evaluate each sub-attribute as YES/NO.

3. DISCRIMINATING POWER: Criteria should separate excellent work from merely adequate work. Avoid criteria that any competent attempt would trivially satisfy (e.g., "has an introduction"). Focus on what distinguishes expert-level output.

4. SCORING METHOD FIT: Choose the scoring method that best matches what you're measuring:
   - weighted_components: for multi-faceted criteria with independent sub-attributes
   - penalty_based: for compliance/correctness where violations subtract from a perfect score
   - binary: for pass/fail requirements with no partial credit
   - percentage: for coverage/completeness metrics
   - threshold_tiers: for quality levels (excellent/good/adequate/poor)
   - count_based: for countable elements (e.g., number of examples, citations)

5. ANTI-GAMING: Write criteria that reward genuine quality, not surface compliance. If a criterion can be satisfied by a formulaic template without real expertise, it needs to be harder.

6. BALANCED WEIGHTING: Allocate points proportional to importance. The most critical quality signals should carry the most weight. No single criterion should dominate unless it genuinely is the primary quality signal."""

    def __init__(self, model: str = "claude-sonnet-4-20250514", verbose: bool = True,
                 learning_integrator: LearningIntegrator = None,
                 enable_research: bool = True,
                 research_model: str = "claude-sonnet-4-20250514",
                 enable_tracing: bool = True,
                 enable_expert_persona: bool = True,
                 enable_expert_panel: bool = False,
                 enable_exemplar: bool = True,
                 enable_rubric_store: bool = True,
                 rag_store: Optional[RubricRAGStore] = None,
                 enable_multipass: bool = True,
                 enable_adversarial_audit: bool = True):
        if Anthropic is None:
            raise ImportError("anthropic package required: pip install anthropic")
        self.client = Anthropic(timeout=_API_TIMEOUT)  # Fresh client, separate from generation/scoring/evaluation agents
        self.model = model
        self.verbose = verbose
        self.learning_integrator = learning_integrator
        self.enable_research = enable_research
        self.enable_tracing = enable_tracing
        self.research_model = research_model
        self.enable_expert_persona = enable_expert_persona
        self.enable_expert_panel = enable_expert_panel
        self.enable_exemplar = enable_exemplar
        self.enable_rubric_store = enable_rubric_store
        self.rag_store = rag_store
        self.enable_multipass = enable_multipass
        self.enable_adversarial_audit = enable_adversarial_audit
        # Research tracer (verifies rubric grounding) — has its own isolated client
        self.tracer = ResearchTracer(model=model, verbose=verbose) if enable_tracing else None
        # Adversarial auditor (red-teams the rubric for coverage gaps) — shares client
        self.auditor = AdversarialAuditor(client=self.client, model=model, verbose=verbose) if enable_adversarial_audit else None

    def _log(self, msg: str):
        if self.verbose:
            print(f"[RubricAgent] {msg}" if not msg.startswith("[Rubric") else msg)

    def _elicit_expert_persona(self, task: str) -> str:
        """Generate a domain expert persona for the given task.

        Makes one short LLM call to produce a 3-5 sentence expert persona that
        describes what credentials/experience the ideal evaluator would have, what
        domain-specific things they would focus on, and what professional standards
        they would apply. This persona is injected into rubric generation and research
        prompts to ground criteria in genuine expert perspective.

        Returns:
            Expert persona description as a string, or "" on failure.
        """
        self._log("Eliciting expert persona for task domain...")
        prompt = EXPERT_PERSONA_PROMPT.format(task=task)
        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=500,
                messages=[{"role": "user", "content": prompt}],
            )
            persona = response.content[0].text.strip()
            if persona:
                self._log(f"Expert persona elicited ({len(persona)} chars)")
            return persona
        except Exception as e:
            self._log(f"Expert persona elicitation failed (non-fatal): {e}")
            return ""

    def _elicit_expert_panel(self, task: str) -> list:
        """Generate 3 complementary expert personas for the given task.

        Makes one LLM call to produce a panel of 3 experts with different
        vantage points that collectively ensure comprehensive evaluation.
        Each expert covers a different quality dimension so their criteria sets
        are additive, not redundant.

        Returns:
            List of expert dicts (role, expertise, unique_focus, dimensions),
            or [] on failure (caller should fall back to single persona).
        """
        self._log("Eliciting expert panel (3 complementary perspectives)...")
        prompt = EXPERT_PANEL_PROMPT.format(task=task)
        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=1500,
                messages=[{"role": "user", "content": prompt}],
            )
            raw = response.content[0].text.strip()
            parsed = self._parse_json(raw)
            panel = parsed.get("panel", [])
            if isinstance(panel, list) and len(panel) >= 2:
                roles = [e.get("role", "?") for e in panel]
                self._log(f"Expert panel: {roles}")
                return panel[:3]
            else:
                self._log("Expert panel parse returned insufficient experts (non-fatal)")
                return []
        except Exception as e:
            self._log(f"Expert panel elicitation failed (non-fatal): {e}")
            return []

    def _generate_expert_criteria(self, task: str, expert: dict,
                                   context_sections: str) -> list:
        """Generate 4-8 evaluation criteria from a single expert's perspective.

        Each expert generates criteria focused exclusively on their unique quality
        dimensions — the things only they would catch. This ensures diversity across
        the panel's outputs.

        Args:
            task: the task description
            expert: expert dict with role, expertise, unique_focus, dimensions
            context_sections: pre-built string combining research + contrastive +
                              retrieval + learning sections for grounding

        Returns:
            List of raw criteria dicts, or [] on failure (graceful degradation).
        """
        role = expert.get("role", "Domain Expert")
        expertise = expert.get("expertise", "")
        unique_focus = expert.get("unique_focus", "")
        dimensions = expert.get("dimensions", [])
        dimensions_str = ", ".join(dimensions) if dimensions else "quality and correctness"

        self._log(f"Generating criteria from {role}'s perspective...")

        system_prompt = (
            self.RUBRIC_AGENT_SYSTEM_PROMPT
            + f"\n\nEXPERT EVALUATOR PERSONA:\nYou are a {role}. {expertise}"
            + f"\n\nYOUR UNIQUE FOCUS: {unique_focus}"
            + f"\n\nYOUR KEY DIMENSIONS: {dimensions_str}"
            + "\n\nGenerate evaluation criteria exclusively from YOUR expert perspective. "
            "Focus on what YOU uniquely care about — the dimensions listed above. "
            "Generate 4-8 highly specific criteria that only someone with your background "
            "would know to check. Do NOT generate generic criteria that any evaluator "
            "would produce — those will be contributed by the other panel members."
        )

        user_prompt = (
            f"Generate evaluation criteria for this task from your expert perspective:\n\n"
            f"TASK: {task}\n\n"
            f"Focus ONLY on your unique dimensions: {dimensions_str}\n"
            f"Generate 4-8 highly specific criteria grounded in your domain expertise.\n"
        )
        if context_sections:
            user_prompt += context_sections
        user_prompt += (
            "\n\nOutput ONLY valid JSON:\n"
            '{\n  "criteria": [\n    {\n'
            '      "id": "PLACEHOLDER",\n'
            '      "category": "<your dimension>",\n'
            '      "description": "<specific criterion>",\n'
            '      "pass_condition": "<measurable pass condition>",\n'
            '      "scoring_method": "<weighted_components|penalty_based|binary|percentage|threshold_tiers|count_based>",\n'
            '      "max_points": 10,\n'
            '      "sub_attributes": [],\n'
            '      "penalties": {},\n'
            '      "tiers": {},\n'
            '      "pass_examples": [],\n'
            '      "fail_examples": [],\n'
            '      "research_basis": ""\n'
            "    }\n  ]\n}"
        )

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=6000,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
            )
            raw = response.content[0].text.strip()
            parsed = self._parse_json(raw)
            criteria = parsed.get("criteria", [])
            if criteria:
                self._log(f"{role}: generated {len(criteria)} criteria")
                return criteria
            else:
                self._log(f"{role}: no criteria parsed (non-fatal)")
                return []
        except Exception as e:
            self._log(f"{role} criteria generation failed (non-fatal): {e}")
            return []

    def _reconcile_panel_criteria(self, task: str, all_criteria: list,
                                   panel: list) -> dict:
        """Merge criteria from all panel experts into a unified, non-redundant spec.

        Runs an LLM reconciliation pass that:
        - Merges duplicates (keeps the more rigorous version)
        - Resolves scoring conflicts
        - Identifies and fills coverage gaps
        - Normalizes IDs and balances point allocation

        Args:
            task: the task description
            all_criteria: list of criteria lists, one per expert (parallel with panel)
            panel: expert dicts for context

        Returns:
            Full rubric spec dict {"domain": ..., "pass_threshold": ..., "criteria": [...]}.
            Falls back to a flat merge if the LLM call fails.
        """
        self._log(f"Reconciling panel criteria ({sum(len(c) for c in all_criteria)} total across {len(panel)} experts)...")

        panel_summary = "\n".join(
            f"- {e.get('role', '?')}: {e.get('unique_focus', '')}"
            for e in panel
        )

        all_criteria_parts = []
        for expert, criteria_list in zip(panel, all_criteria):
            role = expert.get("role", "Expert")
            all_criteria_parts.append(
                f"=== {role} ({len(criteria_list)} criteria) ===\n"
                + json.dumps({"criteria": criteria_list}, indent=2)
            )
        all_criteria_str = "\n\n".join(all_criteria_parts)

        prompt = EXPERT_PANEL_RECONCILE_PROMPT.format(
            task=task,
            panel_summary=panel_summary,
            all_criteria_json=all_criteria_str,
        )

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=16000,
                system=self.RUBRIC_AGENT_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": prompt}],
            )
            raw = response.content[0].text.strip()
            parsed = self._parse_json(raw)
            criteria = parsed.get("criteria", [])
            if criteria:
                self._log(f"Panel reconciled: {len(criteria)} criteria after merging/deduplication")
                return parsed
            else:
                self._log("Reconciliation returned empty criteria — falling back to flat merge")
                return self._flat_merge_criteria(all_criteria)
        except Exception as e:
            self._log(f"Panel reconciliation failed (non-fatal): {e} — falling back to flat merge")
            return self._flat_merge_criteria(all_criteria)

    def _flat_merge_criteria(self, all_criteria: list) -> dict:
        """Fallback: concatenate all expert criteria with renumbered sequential IDs."""
        merged = []
        idx = 1
        for criteria_list in all_criteria:
            for c in criteria_list:
                c = dict(c)
                c["id"] = f"C{idx:02d}"
                merged.append(c)
                idx += 1
        return {"criteria": merged, "domain": "generated", "pass_threshold": 0.85}

    def _research_best_practices(self, task: str, persona: str = "") -> str:
        """Deep research step: use web search to find what domain experts consider
        best practices and quality standards for this task type.

        Uses Claude with the web_search tool to ground rubric generation in
        real-world expert standards rather than LLM intuitions.

        Returns:
            Formatted research brief to inject into the generation prompt.
        """
        self._log("Researching best practices for task domain...")

        prompt = RESEARCH_PROMPT.format(task=task)

        # If a persona is available, append a note to steer search queries toward
        # domain-specific professional standards rather than generic best practices.
        if persona:
            prompt += (
                "\n\nEXPERT EVALUATOR CONTEXT:\n"
                + persona
                + "\n\nBased on this expert profile, prioritize searches for domain-specific "
                "professional standards, certification bodies, practitioner frameworks, "
                "and field-specific failure modes that this expert would reference. "
                "Go beyond generic 'best practices' — search for what this particular "
                "type of expert uses as their professional evaluation criteria."
            )

        try:
            response = self.client.messages.create(
                model=self.research_model,
                max_tokens=4000,
                tools=[{
                    "type": "web_search_20250305",
                    "name": "web_search",
                }],
                messages=[{"role": "user", "content": prompt}],
            )

            # Extract text blocks from response (may include tool_use + text blocks)
            text_parts = []
            for block in response.content:
                if hasattr(block, "text"):
                    text_parts.append(block.text)

            research = "\n".join(text_parts)

            if research.strip():
                self._log(f"Research complete ({len(research)} chars, "
                          f"{sum(1 for b in response.content if b.type == 'web_search_tool_result')} searches)")
                return (
                    "\nDOMAIN RESEARCH — the following is based on web research into what "
                    "industry experts and practitioners consider best practices for this task type. "
                    "Use this to ensure your rubric criteria reflect real-world professional standards, "
                    "not generic quality platitudes.\n\n"
                    + research
                )
            else:
                self._log("Research returned no results — proceeding without")
                return ""

        except Exception as e:
            self._log(f"Research step failed (non-fatal): {e}")
            return ""

    def _extract_criteria_from_research(self, task: str, research: str, persona: str = "") -> list:
        """Extract criterion specifications directly from research findings.

        For each research finding (professional standard, best practice, common failure mode,
        regulatory requirement), generate a criterion that would verify compliance.

        Returns list of criterion specs (dicts matching the rubric JSON format).
        """
        if not research or not research.strip():
            return []

        self._log("Step 1.1: Extracting criteria directly from research findings...")

        prompt = RESEARCH_CRITERIA_EXTRACTION_PROMPT.format(
            research=research[:10000],  # cap to avoid oversized prompts
            task=task,
        )

        if persona:
            prompt += (
                "\n\nEXPERT EVALUATOR CONTEXT:\n"
                + persona
                + "\n\nExtract criteria that this specific expert would require based on the research."
            )

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=8000,
                messages=[{"role": "user", "content": prompt}],
            )
            raw = response.content[0].text if response.content else ""

            # Try to extract JSON array from the response
            match = re.search(r'```(?:json)?\s*(\[[\s\S]*?\])\s*```', raw)
            if not match:
                match = re.search(r'(\[[\s\S]*\])', raw)

            if not match:
                self._log("Research criteria extraction returned no parseable array — skipping")
                return []

            try:
                criteria_specs = json.loads(match.group(1))
            except (json.JSONDecodeError, ValueError):
                self._log("Research criteria JSON parse failed — skipping")
                return []

            if not isinstance(criteria_specs, list):
                self._log("Research criteria extraction returned non-list — skipping")
                return []

            self._log(f"Extracted {len(criteria_specs)} criteria from research findings")
            return criteria_specs

        except Exception as e:
            self._log(f"Research criteria extraction failed (non-fatal): {e}")
            return []

    def _retrieve_exemplars(self, task: str) -> str:
        """Phase C — web search for expert-quality example outputs for similar tasks.

        Dynamically generates search queries from the task description and searches
        for exemplary outputs produced by top practitioners. Works for any task type.

        Returns:
            Formatted exemplar brief with distinctive excerpts, or empty string
            if no relevant exemplars are found.
        """
        self._log("Phase C: Searching for expert exemplars...")

        prompt = EXEMPLAR_SEARCH_PROMPT.format(task=task)

        try:
            response = self.client.messages.create(
                model=self.research_model,
                max_tokens=4000,
                tools=[{
                    "type": "web_search_20250305",
                    "name": "web_search",
                }],
                messages=[{"role": "user", "content": prompt}],
            )

            # Extract text blocks from response (may include tool_use + text blocks)
            text_parts = []
            for block in response.content:
                if hasattr(block, "text"):
                    text_parts.append(block.text)

            exemplar_brief = "\n".join(text_parts)

            if exemplar_brief.strip():
                n_searches = sum(
                    1 for b in response.content
                    if hasattr(b, "type") and b.type == "web_search_tool_result"
                )
                self._log(f"Exemplar search complete ({len(exemplar_brief)} chars, "
                          f"{n_searches} searches)")
                return exemplar_brief
            else:
                self._log("Exemplar search returned no results — skipping")
                return ""

        except Exception as e:
            self._log(f"Exemplar search failed (non-fatal): {e}")
            return ""

    def _generate_baseline(self, task: str) -> str:
        """Generate a cheap single-shot baseline representing what Claude produces
        without guidance. Max 2000 tokens, no system prompt engineering.

        Returns:
            Baseline text, or empty string if generation fails.
        """
        self._log("Phase C: Generating quick baseline...")

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=2000,
                messages=[{"role": "user", "content": f"Please complete the following task:\n\n{task}"}],
            )
            baseline = response.content[0].text if response.content else ""
            if baseline.strip():
                self._log(f"Baseline generated ({len(baseline)} chars)")
            return baseline
        except Exception as e:
            self._log(f"Baseline generation failed (non-fatal): {e}")
            return ""

    def _extract_contrastive_criteria(self, task: str, exemplar_brief: str, baseline: str) -> str:
        """Extract discriminative criteria from the gap between expert exemplars and baseline.

        Feeds both the expert exemplar brief and the quick baseline to the model and
        asks it to identify criteria that score experts high and baseline medium — i.e.,
        criteria that only domain knowledge reveals.

        Returns:
            Formatted criteria seeds to inject into rubric generation prompt, or empty
            string if extraction fails or produces no discriminating criteria.
        """
        self._log("Phase C: Extracting contrastive criteria...")

        prompt = CONTRASTIVE_CRITERIA_PROMPT.format(
            task=task,
            exemplar_brief=exemplar_brief[:3000],  # cap to avoid oversized prompts
            baseline=baseline[:2000],
        )

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=3000,
                messages=[{"role": "user", "content": prompt}],
            )
            raw = response.content[0].text if response.content else ""

            # Try to extract JSON array of criteria
            match = re.search(r'```(?:json)?\s*(\[[\s\S]*?\])\s*```', raw)
            if not match:
                match = re.search(r'(\[[\s\S]*\])', raw)

            if not match:
                self._log("Contrastive extraction returned no parseable criteria — skipping")
                return ""

            try:
                criteria_specs = json.loads(match.group(1))
            except (json.JSONDecodeError, ValueError):
                self._log("Contrastive criteria JSON parse failed — skipping")
                return ""

            if not criteria_specs:
                self._log("Contrastive extraction found 0 discriminating criteria — skipping")
                return ""

            self._log(f"Extracted {len(criteria_specs)} contrastive criteria")

            # Format as a prompt injection block
            lines = [
                "\nCONTRASTIVE CRITERIA SEEDS — derived by comparing expert exemplars against a "
                "default LLM baseline. These represent dimensions where expert output is clearly "
                "superior to what Claude produces without guidance. Prioritize these as high-signal "
                "criteria in the rubric. De-duplicate against criteria already derived from domain "
                "research.\n"
            ]
            for c in criteria_specs:
                lines.append(f"  [{c.get('id', 'contrastive')}] {c.get('description', '')}")
                if c.get("pass_condition"):
                    lines.append(f"    Pass condition: {c['pass_condition']}")
                if c.get("baseline_gap"):
                    lines.append(f"    Baseline gap: {c['baseline_gap']}")
                if c.get("domain_signal"):
                    lines.append(f"    Domain signal: {c['domain_signal']}")
                lines.append("")

            return "\n".join(lines)

        except Exception as e:
            self._log(f"Contrastive extraction failed (non-fatal): {e}")
            return ""

    def _run_exemplar_pipeline(self, task: str) -> str:
        """Orchestrate the full exemplar retrieval + contrastive criterion extraction pipeline.

        Phase C of rubric generation — runs after best-practice web research (Phase A)
        and before the main rubric generation call:
          C1. Search the web for expert-quality exemplar outputs (web search)
          C2. Generate a cheap single-shot baseline (what Claude produces without guidance)
          C3. Extract discriminative criteria from the expert-vs-baseline gap

        Returns:
            Formatted contrastive criteria section for injection into the rubric
            generation prompt, or empty string if the pipeline finds nothing useful.
        """
        # C1: Search for expert exemplars
        exemplar_brief = self._retrieve_exemplars(task)
        if not exemplar_brief:
            self._log("No exemplars found — skipping contrastive extraction")
            return ""

        # C2: Generate a quick baseline
        baseline = self._generate_baseline(task)
        if not baseline:
            self._log("Baseline generation failed — skipping contrastive extraction")
            return ""

        # C3: Extract contrastive criteria from the gap
        return self._extract_contrastive_criteria(task, exemplar_brief, baseline)

    # -------------------------------------------------------------------------
    # Multi-Pass Pipeline (Pass 1, 2, 3)
    # -------------------------------------------------------------------------

    def _decompose_dimensions(self, task: str, research_section: str, expert_persona: str) -> list[dict]:
        """Pass 1: Ask an LLM to decompose the task into 6-12 evaluation dimensions.

        Returns:
            List of dimension dicts with keys: id, name, scope, weight.
            Weights are normalized to sum to 1.0.
        Raises:
            ValueError if the response cannot be parsed.
        """
        self._log("[MultiPass] Pass 1: Decomposing task into evaluation dimensions...")

        persona_section = (f"EXPERT EVALUATOR PERSONA:\n{expert_persona}" if expert_persona else "")
        research_snippet = research_section[:3000] if research_section else ""

        prompt = DIMENSION_DECOMPOSITION_PROMPT.format(
            task=task,
            persona_section=persona_section,
            research_section=research_snippet,
        )

        response = self.client.messages.create(
            model=self.model,
            max_tokens=4000,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = response.content[0].text.strip()

        match = re.search(r'```(?:json)?\s*(\[[\s\S]*?\])\s*```', raw)
        if not match:
            match = re.search(r'(\[[\s\S]*\])', raw)
        if not match:
            raise ValueError(f"Pass 1 returned no parseable JSON array: {raw[:200]}")

        dims = json.loads(match.group(1))
        if not dims:
            raise ValueError("Pass 1 returned empty dimensions list")

        # Normalize weights to sum to 1.0
        total_w = sum(float(d.get("weight", 0.1)) for d in dims)
        if total_w > 0 and abs(total_w - 1.0) > 0.01:
            for d in dims:
                d["weight"] = float(d.get("weight", 0.1)) / total_w

        self._log(f"[MultiPass] Pass 1 complete: {len(dims)} dimensions")
        return dims

    def _generate_dimension_criteria(
        self,
        task: str,
        dimension: dict,
        research_section: str,
        expert_persona: str,
    ) -> list[dict]:
        """Pass 2 (per-dimension): Generate 2-5 criteria specific to one dimension.

        Returns:
            List of criterion dicts (same schema as RUBRIC_GENERATION_PROMPT criteria).
            Returns empty list on any parse/API failure (non-fatal).
        """
        dim_name = dimension.get("name", "Unknown")
        persona_section = (f"EXPERT EVALUATOR PERSONA:\n{expert_persona}" if expert_persona else "")
        research_snippet = research_section[:2000] if research_section else ""

        prompt = DIMENSION_CRITERIA_PROMPT.format(
            task=task,
            dimension_name=dim_name,
            dimension_scope=dimension.get("scope", ""),
            persona_section=persona_section,
            research_section=research_snippet,
        )

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=4000,
                messages=[{"role": "user", "content": prompt}],
            )
            raw = response.content[0].text.strip()

            match = re.search(r'```(?:json)?\s*(\[[\s\S]*?\])\s*```', raw)
            if not match:
                match = re.search(r'(\[[\s\S]*\])', raw)
            if not match:
                self._log(f"[MultiPass]   '{dim_name}': no JSON array found — skipping dimension")
                return []

            criteria = json.loads(match.group(1))
            self._log(f"[MultiPass]   '{dim_name}': {len(criteria)} criteria")
            return criteria

        except Exception as e:
            self._log(f"[MultiPass]   '{dim_name}': failed ({e}) — skipping dimension")
            return []

    def _calibrate_criteria(
        self,
        task: str,
        all_criteria: list[dict],
        dimensions: list[dict],
    ) -> dict:
        """Pass 3: Calibrate all per-dimension criteria into a unified rubric.

        Removes redundancy, rebalances point allocations, adds cross-cutting
        criteria, and ensures the final count is 15-35.

        Returns:
            Rubric spec dict with keys: domain, pass_threshold, criteria.
        Raises:
            ValueError if the response cannot be parsed.
        """
        self._log(f"[MultiPass] Pass 3: Calibrating {len(all_criteria)} criteria "
                  f"across {len(dimensions)} dimensions...")

        dims_lines = [
            f"  [{d['id']}] {d['name']} (weight: {d.get('weight', 0):.0%}): {d.get('scope', '')}"
            for d in dimensions
        ]
        dimensions_section = "\n".join(dims_lines)

        # Cap criteria JSON to avoid oversized prompts
        criteria_json = json.dumps(all_criteria, indent=2)
        if len(criteria_json) > 10000:
            # Truncate to first ~10k chars to stay within token budget;
            # calibration LLM still sees full count in the header
            criteria_json = criteria_json[:10000] + "\n  ... (truncated for length)"

        prompt = CALIBRATION_PROMPT.format(
            task=task,
            dimensions_section=dimensions_section,
            total_criteria=len(all_criteria),
            criteria_section=criteria_json,
        )

        response = self.client.messages.create(
            model=self.model,
            max_tokens=16000,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = response.content[0].text.strip()

        spec = self._parse_json(raw)
        if not spec or "criteria" not in spec:
            raise ValueError(f"Pass 3 returned no parseable rubric JSON: {raw[:200]}")

        self._log(f"[MultiPass] Pass 3 complete: {len(spec['criteria'])} final criteria")
        return spec

    def _run_multipass_pipeline(
        self,
        task: str,
        research_section: str,
        expert_persona: str,
    ) -> Rubric:
        """Orchestrate the full 3-pass rubric generation pipeline.

        Pass 1 — Dimension Decomposition: identifies 6-12 evaluation dimensions.
        Pass 2 — Per-Dimension Criteria: generates 2-5 criteria per dimension.
        Pass 3 — Calibration: deduplicates, rebalances, adds cross-cutting criteria.

        Raises:
            ValueError or any exception if the pipeline fails at any pass.
            The caller (generate()) catches this and falls back to single-pass.
        """
        # Pass 1: Decompose dimensions
        dimensions = self._decompose_dimensions(task, research_section, expert_persona)

        # Pass 2: Generate criteria per dimension (sequential calls)
        all_criteria: list[dict] = []
        for dim in dimensions:
            dim_criteria = self._generate_dimension_criteria(
                task, dim, research_section, expert_persona
            )
            all_criteria.extend(dim_criteria)

        if not all_criteria:
            raise ValueError("Pass 2 produced no criteria across all dimensions")

        self._log(f"[MultiPass] Pass 2 complete: {len(all_criteria)} total criteria "
                  f"across {len(dimensions)} dimensions")

        # Pass 3: Calibrate into final rubric
        spec = self._calibrate_criteria(task, all_criteria, dimensions)

        # Hydrate into canonical Rubric object
        rubric = self._hydrate(task, spec)

        # Attach dimension metadata for downstream use
        rubric.dimensions = [
            RubricDimension(
                id=d["id"],
                name=d["name"],
                weight=float(d.get("weight", 0.0)),
                criteria_ids=[],
            )
            for d in dimensions
        ]

        return rubric

    def generate(self, task: str, context: str = "", seed_rubrics: list[Rubric] = None) -> Rubric:
        """Generate a bespoke rubric for the given task.

        Args:
            task: the task description
            context: optional additional context
            seed_rubrics: optional list of existing Rubrics to use as few-shot seeds.
                          If not provided, pulls the closest matches from the registry.

        Returns:
            A fully hydrated Rubric with Criterion objects and ScoringRubrics
        """
        self._log(f"Generating rubric for: {task[:60]}...")

        context_section = ""
        if context:
            context_section = f"ADDITIONAL CONTEXT:\n{context[:2000]}"

        # Build examples section: static examples + dynamic seeds from registry
        examples_section = RUBRIC_GEN_EXAMPLES
        seed_section = self._build_seed_section(task, seed_rubrics)
        if seed_section:
            examples_section += "\n\n" + seed_section

        # Step 0: Expert persona / panel elicitation — who are the ideal evaluators?
        expert_persona = ""
        expert_panel = []
        if self.enable_expert_panel:
            # Panel mode: elicit 3 complementary experts; fall back to single persona
            expert_panel = self._elicit_expert_panel(task)
            if not expert_panel:
                self._log("Panel elicitation failed — falling back to single persona")
                if self.enable_expert_persona:
                    expert_persona = self._elicit_expert_persona(task)
        elif self.enable_expert_persona:
            expert_persona = self._elicit_expert_persona(task)

        # Build research persona: use panel summary when panel is active
        research_persona = expert_persona
        if expert_panel:
            research_persona = "Panel of domain experts:\n" + "\n".join(
                f"- {e.get('role', '?')}: {e.get('unique_focus', '')}"
                for e in expert_panel
            )

        # Step 1: Deep research — what do domain experts consider best practices?
        research_section = ""
        if self.enable_research:
            research_section = self._research_best_practices(task, persona=research_persona)

        # Step 1.1: Extract research-derived criteria — make research LOAD-BEARING.
        # Each finding becomes a mandatory criterion seed so research is never dropped.
        research_derived_criteria = []
        if research_section:
            research_derived_criteria = self._extract_criteria_from_research(
                task, research_section, persona=expert_persona
            )

        # Phase C: Exemplar retrieval + contrastive criterion extraction
        contrastive_section = ""
        if self.enable_exemplar:
            contrastive_section = self._run_exemplar_pipeline(task)

        # Step 1.5: RubricRAG — retrieve seed criteria from similar prior rubrics
        retrieval_section = ""
        if self.enable_rubric_store and self.rag_store is not None:
            try:
                retrieval_section = self.rag_store.format_retrieval_section(task)
                if retrieval_section:
                    self._log(f"[RubricRAG] Injected retrieval context ({len(retrieval_section)} chars)")
            except Exception as e:
                self._log(f"[RubricRAG] Retrieval unavailable (non-fatal): {e}")

        # Step 2: Inject learning context from prior evaluations
        learning_section = ""
        if self.learning_integrator:
            try:
                learning_section = self.learning_integrator.build_learning_context(task)
                if learning_section:
                    self._log(f"Injected learning context ({len(learning_section)} chars)")
            except Exception as e:
                self._log(f"Learning context unavailable: {e}")

        # ---- Multi-pass pipeline (default path) ----
        if self.enable_multipass:
            try:
                rubric = self._run_multipass_pipeline(task, research_section, expert_persona)
                self._log(f"[MultiPass] Generated: {len(rubric.criteria)} criteria, "
                          f"{rubric.total_points} max points, threshold: {rubric.pass_threshold:.0%}")
                rubric = self._apply_tracing(rubric, research_section, task)
                return rubric
            except Exception as e:
                self._log(f"[MultiPass] Pipeline failed ({e}) — falling back to single-pass")

        # ---- Single-pass fallback ----
        # ------------------------------------------------------------------ #
        # Panel path: per-expert criteria generation + reconciliation          #
        # ------------------------------------------------------------------ #
        if expert_panel:
            # Build a shared context string for all experts (research + contrastive + RAG + learning)
            context_sections = ""
            if research_section:
                context_sections += "\n" + research_section
            if contrastive_section:
                context_sections += "\n" + contrastive_section
            if retrieval_section:
                context_sections += "\n" + retrieval_section
            if learning_section:
                context_sections += "\n" + learning_section

            # Per-expert criteria generation — skip experts that fail (graceful degradation)
            successful_experts = []
            all_expert_criteria = []
            for expert in expert_panel:
                criteria = self._generate_expert_criteria(task, expert, context_sections)
                if criteria:
                    successful_experts.append(expert)
                    all_expert_criteria.append(criteria)
                else:
                    self._log(f"Skipping {expert.get('role', '?')} — no criteria generated")

            if all_expert_criteria:
                # Reconcile all experts' criteria into a unified spec
                spec = self._reconcile_panel_criteria(task, all_expert_criteria, successful_experts)

                if spec and spec.get("criteria"):
                    rubric = self._hydrate(task, spec)
                    self._log(
                        f"[Panel] Generated: {len(rubric.criteria)} criteria "
                        f"(from {len(successful_experts)} experts), "
                        f"{rubric.total_points} max points, "
                        f"threshold: {rubric.pass_threshold:.0%}"
                    )

                    # Research traceability audit
                    if self.enable_tracing and self.tracer and research_section:
                        self._log("Running research traceability audit...")
                        trace_result = self.tracer.trace(rubric, research_section)
                        if trace_result.grounding_score < 0.70 or trace_result.ungrounded_criteria:
                            self._log(f"Grounding: {trace_result.grounding_score:.0%} — patching rubric")
                            rubric = self.tracer.patch_rubric(rubric, trace_result, research_section)
                            self._log(f"Patched: {len(rubric.criteria)} criteria, {rubric.total_points} max points")
                        else:
                            audit_map = {a.criterion_id: a for a in trace_result.criterion_audits}
                            for criterion in rubric.criteria:
                                audit = audit_map.get(criterion.id)
                                if audit and audit.research_quote and not criterion.research_basis:
                                    criterion.research_basis = audit.research_quote
                        rubric._trace_result = trace_result

                    return rubric
                else:
                    self._log("Panel reconciliation produced no criteria — falling through to standard path")
            else:
                self._log("All panel experts failed — falling through to standard path")

        # ------------------------------------------------------------------ #
        # Standard single-persona path (default, or panel fallback)           #
        # ------------------------------------------------------------------ #
        prompt = RUBRIC_GENERATION_PROMPT.format(
            task=task,
            context_section=context_section,
            examples_section=examples_section,
        )
        # Append research + learnings after the base prompt so the rubric architect
        # has full domain context before generating criteria
        if research_section:
            prompt += "\n" + research_section

        # Inject research-derived criteria as mandatory seeds — these ensure every
        # research finding maps to at least one criterion in the final rubric.
        if research_derived_criteria:
            lines = [
                "\nRESEARCH-DERIVED CRITERIA (incorporate these and add additional criteria based on your "
                "expert judgment) — The following criteria were extracted directly from domain research "
                "findings. Incorporate ALL of them into the rubric. You may refine wording, scoring "
                "method, or max_points, but do NOT drop any. Add more criteria as your expertise demands.\n"
            ]
            for c in research_derived_criteria:
                cid = c.get("id", "unknown")
                desc = c.get("description", "")
                pass_cond = c.get("pass_condition", "")
                basis = c.get("research_basis", "")
                lines.append(f"  [{cid}] {desc}")
                if pass_cond:
                    lines.append(f"    Pass condition: {pass_cond}")
                if basis:
                    lines.append(f"    Research basis: {basis}")
                lines.append("")
            prompt += "\n".join(lines)

        if contrastive_section:
            prompt += "\n" + contrastive_section
        if retrieval_section:
            prompt += "\n" + retrieval_section
        if learning_section:
            prompt += "\n" + learning_section

        # Build system prompt — inject expert persona if available so the rubric
        # architect adopts the perspective of the domain's ideal evaluator
        system_prompt = self.RUBRIC_AGENT_SYSTEM_PROMPT
        if expert_persona:
            system_prompt = (
                system_prompt
                + "\n\nEXPERT EVALUATOR PERSONA:\n"
                + expert_persona
                + "\n\nYou are generating evaluation criteria from this expert's perspective. "
                "Focus on what separates truly expert-level output from competent-but-generic "
                "work in this domain. Include criteria that only someone with this specific "
                "background would know to check — the kind of thing a generalist would miss "
                "but this expert would flag immediately."
            )

        self._log("[RubricAgent] Generating rubric (single-pass)...")
        response = self.client.messages.create(
            model=self.model,
            max_tokens=16000,
            system=system_prompt,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = response.content[0].text

        # Parse JSON from response
        spec = self._parse_json(raw)
        if not spec or "criteria" not in spec:
            raise ValueError(f"Failed to parse rubric spec from LLM response: {raw[:200]}")

        # Hydrate into canonical objects
        rubric = self._hydrate(task, spec)
        self._log(f"Generated: {len(rubric.criteria)} criteria, {rubric.total_points} max points, "
                  f"threshold: {rubric.pass_threshold:.0%}")

        # Coverage check: verify research-derived criteria survived into the final rubric.
        # Log warnings for any that were dropped so we can diagnose generation failures.
        if research_derived_criteria:
            rubric_ids = {c.id for c in rubric.criteria}
            missing = []
            for c in research_derived_criteria:
                cid = c.get("id", "")
                if cid and cid not in rubric_ids:
                    missing.append((cid, c.get("description", "")[:80]))
            if missing:
                self._log(f"[Coverage] WARNING: {len(missing)}/{len(research_derived_criteria)} "
                          f"research-derived criteria were not retained in the final rubric:")
                for cid, desc in missing:
                    self._log(f"[Coverage]   DROPPED: '{cid}' — {desc}")
            else:
                self._log(f"[Coverage] All {len(research_derived_criteria)} research-derived criteria "
                          f"retained in final rubric")

        # Step 3: Research traceability audit — verify criteria are grounded
        rubric = self._apply_tracing(rubric, research_section, task)
        return rubric

    def _apply_tracing(self, rubric: Rubric, research_section: str, task: str = "") -> Rubric:
        """Run the research traceability audit and patch rubric if grounding is low.

        Shared post-processing step used by both multi-pass and single-pass paths.
        """
        if not (self.enable_tracing and self.tracer and research_section):
            return rubric

        self._log("Running research traceability audit...")
        trace_result = self.tracer.trace(rubric, research_section)

        if trace_result.grounding_score < 0.70 or trace_result.ungrounded_criteria:
            self._log(f"Grounding: {trace_result.grounding_score:.0%} — patching rubric")
            rubric = self.tracer.patch_rubric(rubric, trace_result, research_section)
            self._log(f"Patched: {len(rubric.criteria)} criteria, {rubric.total_points} max points")
        else:
            # Still update research_basis on well-grounded criteria
            audit_map = {a.criterion_id: a for a in trace_result.criterion_audits}
            for criterion in rubric.criteria:
                audit = audit_map.get(criterion.id)
                if audit and audit.research_quote and not criterion.research_basis:
                    criterion.research_basis = audit.research_quote

        # Store trace result on rubric for downstream use
        rubric._trace_result = trace_result
        # Step 4: Adversarial coverage audit — red-team the rubric for blind spots
        if self.enable_adversarial_audit and self.auditor:
            self._log("Running adversarial coverage audit...")
            rubric, audit_report = self.auditor.audit(task, rubric, max_rounds=2)
            self._log(
                f"Adversarial audit: added {audit_report['criteria_added']} criteria "
                f"in {audit_report['rounds']} round(s) "
                f"({'converged' if audit_report['converged'] else 'max rounds reached'})"
            )

        return rubric

    def _build_seed_section(self, task: str, seed_rubrics: list[Rubric] = None) -> str:
        """Build a seed examples section from existing rubrics.

        If seed_rubrics is provided, uses those. Otherwise, queries the registry
        for the top 2 closest matches to use as structural seeds.
        """
        seeds = seed_rubrics or []

        if not seeds:
            # Pull closest matches from registry as seeds
            try:
                scores = REGISTRY._score_all(task)
                for name, score in scores[:2]:  # top 2 matches
                    sig = REGISTRY.get(name)
                    if sig:
                        seed = sig.builder(task)
                        seeds.append(seed)
            except Exception:
                pass

        if not seeds:
            return ""

        parts = ["SEED RUBRICS — these are similar rubrics for related task types. "
                  "Use their structure and scoring patterns as inspiration, "
                  "but generate criteria SPECIFIC to the task above.\n"]

        for seed in seeds[:2]:
            parts.append(f"--- Seed: {seed.domain} ({len(seed.criteria)} criteria, {seed.total_points}pts) ---")
            for c in seed.criteria[:3]:  # show first 3 criteria as seeds
                method = c.scoring.method.value
                pts = c.scoring.max_points
                parts.append(f"  {c.id} ({method}, {pts}pts): {c.description}")
                if c.scoring.sub_attributes:
                    for sub in c.scoring.sub_attributes[:2]:
                        parts.append(f"    - {sub.sub_id} ({sub.weight:.0%}): {sub.measurement[:80]}")
                if c.scoring.penalties:
                    for v, p in list(c.scoring.penalties.items())[:3]:
                        parts.append(f"    - violation: {v} ({p})")
            parts.append("")

        return "\n".join(parts)

    def _parse_json(self, text: str) -> dict:
        """Extract JSON from LLM response."""
        text = text.strip()

        # Try direct parse
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # Try extracting from markdown fences
        match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', text)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass

        # Try finding the first { ... } block
        match = re.search(r'\{[\s\S]*\}', text)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass

        return {}

    def _hydrate(self, task: str, spec: dict) -> Rubric:
        """Convert a JSON spec into canonical Rubric/Criterion objects."""
        criteria = []

        for c_spec in spec["criteria"]:
            scoring = self._build_scoring(c_spec)

            criterion = Criterion(
                id=c_spec["id"],
                category=c_spec.get("category", "general"),
                description=c_spec["description"],
                pass_condition=c_spec.get("pass_condition", ""),
                scoring=scoring,
                source="generated",
                pass_examples=c_spec.get("pass_examples", []),
                fail_examples=c_spec.get("fail_examples", []),
                domain=spec.get("domain", "generated"),
                research_basis=c_spec.get("research_basis", ""),
            )
            criteria.append(criterion)

        total_points = sum(c.scoring.max_points for c in criteria)

        return Rubric(
            task=task,
            domain=spec.get("domain", "generated"),
            criteria=criteria,
            total_points=total_points,
            pass_threshold=spec.get("pass_threshold", 0.85),
        )

    def _build_scoring(self, c_spec: dict) -> ScoringRubric:
        """Build a ScoringRubric from a criterion spec."""
        method_str = c_spec.get("scoring_method", "binary")
        max_points = c_spec.get("max_points", 5)

        method_map = {
            "weighted_components": ScoringMethod.WEIGHTED_COMPONENTS,
            "penalty_based": ScoringMethod.PENALTY_BASED,
            "binary": ScoringMethod.BINARY,
            "percentage": ScoringMethod.PERCENTAGE,
            "threshold_tiers": ScoringMethod.THRESHOLD_TIERS,
            "count_based": ScoringMethod.COUNT_BASED,
        }
        method = method_map.get(method_str, ScoringMethod.BINARY)

        sub_attributes = []
        if method == ScoringMethod.WEIGHTED_COMPONENTS:
            for sub_spec in c_spec.get("sub_attributes", []):
                sub_attributes.append(SubAttribute(
                    sub_id=sub_spec["sub_id"],
                    description=sub_spec.get("description", ""),
                    weight=sub_spec.get("weight", 0.5),
                    measurement=sub_spec.get("measurement", ""),
                ))
            # Normalize weights if they don't sum to 1.0
            total_weight = sum(s.weight for s in sub_attributes)
            if sub_attributes and abs(total_weight - 1.0) > 0.01:
                for s in sub_attributes:
                    s.weight = s.weight / total_weight

        penalties = {}
        if method == ScoringMethod.PENALTY_BASED:
            penalties = c_spec.get("penalties", {})
            # Ensure penalties are negative
            penalties = {k: -abs(v) for k, v in penalties.items()}

        return ScoringRubric(
            method=method,
            max_points=max_points,
            sub_attributes=sub_attributes,
            penalties=penalties,
        )


# ============================================================================
# Research Tracer — verifies rubric criteria are grounded in research
# ============================================================================

RESEARCH_CRITERIA_EXTRACTION_PROMPT = """You are converting domain research into measurable evaluation criteria. For each distinct professional standard, best practice, or domain-specific quality requirement found in the research below, generate ONE criterion that would verify an output meets that standard.

RESEARCH FINDINGS:
{research}

TASK BEING EVALUATED:
{task}

For each research finding, ask: 'What specific, measurable criterion would verify that an output complies with or demonstrates this standard?'

Rules:
- Each criterion must trace to a SPECIFIC finding in the research (cite it in research_basis)
- If a finding is too broad, decompose it into 2-3 specific criteria
- Skip findings that are generic advice (e.g., 'be clear') — only extract criteria for domain-specific standards
- Each criterion needs concrete pass_condition with numbers/named techniques
- Use weighted_components or penalty_based scoring (not binary)
- Generate as many criteria as the research supports — do NOT artificially cap

Output: JSON array of criterion objects matching the standard rubric format:
[
  {{
    "id": "<short_snake_case>",
    "category": "<category>",
    "description": "<what this criterion evaluates>",
    "pass_condition": "<concrete threshold with numbers/named techniques>",
    "scoring_method": "weighted_components|penalty_based",
    "max_points": <int 3-8>,
    "sub_attributes": [
      {{
        "sub_id": "<snake_case>",
        "description": "<what this measures>",
        "weight": <float>,
        "measurement": "<graduated scale: 1.0 if [expert], 0.7 if [competent], 0.4 if [surface], 0.0 if [absent]>"
      }}
    ],
    "penalties": {{"<violation>": <negative_float>}},
    "pass_examples": ["<example>"],
    "fail_examples": ["<example>"],
    "research_basis": "<exact quote or citation from the research finding this criterion traces to>"
  }}
]

Output ONLY the JSON array. No preamble, no explanation."""


TRACER_PROMPT = """You are a rubric auditor. Your job is to verify that each criterion in a generated rubric is properly grounded in the domain research that was conducted.

DOMAIN RESEARCH (this is what was found via web search):
{research}

GENERATED RUBRIC CRITERIA:
{criteria_summary}

For EACH criterion, evaluate:

1. GROUNDING STATUS — one of:
   - GROUNDED: The criterion directly corresponds to a specific finding, standard, or practice mentioned in the research. Quote the relevant research passage.
   - PARTIALLY_GROUNDED: The criterion relates to the research domain but isn't directly supported by a specific finding. The connection is inferential.
   - UNGROUNDED: The criterion has no clear basis in the research. It may be generic quality padding or an LLM assumption.
   - HALLUCINATED: The criterion cites a specific standard/source that does NOT appear in the research and may be fabricated.

2. RESEARCH GAPS — identify specific findings in the research that are NOT covered by any criterion. These are missed opportunities.

3. PATCH RECOMMENDATIONS — for each UNGROUNDED or HALLUCINATED criterion, suggest either:
   - REPLACE: with a specific criterion grounded in an unused research finding
   - STRENGTHEN: add a research_basis citation and adjust the criterion to align with research
   - REMOVE: if the criterion is pure padding with no value

Output as JSON:
{{
  "criterion_audits": [
    {{
      "criterion_id": "<id>",
      "status": "GROUNDED|PARTIALLY_GROUNDED|UNGROUNDED|HALLUCINATED",
      "research_quote": "<exact quote from research that grounds this, or empty>",
      "issue": "<what's wrong if not GROUNDED>",
      "recommendation": "<REPLACE|STRENGTHEN|REMOVE and specific action>"
    }}
  ],
  "uncovered_research_findings": [
    {{
      "finding": "<specific research finding not covered by any criterion>",
      "importance": "high|medium|low",
      "suggested_criterion_id": "<snake_case_id>",
      "suggested_description": "<what the criterion should test>"
    }}
  ],
  "overall_grounding_score": <float 0.0-1.0 — fraction of criteria that are GROUNDED or PARTIALLY_GROUNDED>,
  "summary": "<1-2 sentence assessment>"
}}"""


@_dataclass
class CriterionAudit:
    """Result of auditing a single criterion against research."""
    criterion_id: str
    status: str  # GROUNDED, PARTIALLY_GROUNDED, UNGROUNDED, HALLUCINATED
    research_quote: str = ""
    issue: str = ""
    recommendation: str = ""


@_dataclass
class ResearchGap:
    """A research finding not covered by any criterion."""
    finding: str
    importance: str  # high, medium, low
    suggested_criterion_id: str = ""
    suggested_description: str = ""


@_dataclass
class TraceResult:
    """Full result of research-to-rubric traceability audit."""
    criterion_audits: list[CriterionAudit]
    uncovered_findings: list[ResearchGap]
    grounding_score: float
    summary: str

    @property
    def ungrounded_criteria(self) -> list[CriterionAudit]:
        return [a for a in self.criterion_audits if a.status in ("UNGROUNDED", "HALLUCINATED")]

    @property
    def high_priority_gaps(self) -> list[ResearchGap]:
        return [g for g in self.uncovered_findings if g.importance == "high"]


class ResearchTracer:
    """Verifies that generated rubric criteria are grounded in domain research.

    After the RubricAgent produces a rubric from research, the tracer:
    1. Audits each criterion for research provenance (GROUNDED → HALLUCINATED)
    2. Identifies research findings not covered by any criterion
    3. Patches the rubric: replaces ungrounded criteria with research-backed ones,
       adds high-priority missing criteria, and records provenance

    This closes the gap where the generator might ignore research or hallucinate
    standards that weren't in the research.
    """

    def __init__(self, model: str = "claude-sonnet-4-20250514", verbose: bool = True):
        if Anthropic is None:
            raise ImportError("anthropic package required")
        self.client = Anthropic(timeout=_API_TIMEOUT)
        self.model = model
        self.verbose = verbose

    def _log(self, msg: str):
        if self.verbose:
            print(f"[Tracer] {msg}")

    def trace(self, rubric: Rubric, research: str) -> TraceResult:
        """Audit rubric criteria against the research that generated them.

        Args:
            rubric: the generated Rubric to audit
            research: the raw research text from _research_best_practices()

        Returns:
            TraceResult with per-criterion audits and gap analysis
        """
        if not research or not research.strip():
            self._log("No research to trace against — skipping")
            return TraceResult(
                criterion_audits=[],
                uncovered_findings=[],
                grounding_score=0.0,
                summary="No research available for traceability audit"
            )

        # Build criteria summary for the auditor
        criteria_lines = []
        for c in rubric.criteria:
            line = f"  {c.id}: {c.description}"
            if c.research_basis:
                line += f"\n    Research basis (claimed): {c.research_basis}"
            if c.pass_condition:
                line += f"\n    Pass condition: {c.pass_condition}"
            criteria_lines.append(line)

        criteria_summary = "\n".join(criteria_lines)

        prompt = TRACER_PROMPT.format(
            research=research[:12000],
            criteria_summary=criteria_summary,
        )

        self._log(f"Auditing {len(rubric.criteria)} criteria against {len(research)} chars of research...")

        response = self.client.messages.create(
            model=self.model,
            max_tokens=8000,
            temperature=0,
            messages=[{"role": "user", "content": prompt}],
        )

        raw = response.content[0].text

        # Parse JSON
        result_data = self._parse_json(raw)
        if not result_data:
            self._log("Warning: could not parse tracer response")
            return TraceResult(
                criterion_audits=[],
                uncovered_findings=[],
                grounding_score=0.0,
                summary="Failed to parse tracer audit"
            )

        # Hydrate into dataclasses
        audits = []
        for a in result_data.get("criterion_audits", []):
            audits.append(CriterionAudit(
                criterion_id=a.get("criterion_id", ""),
                status=a.get("status", "UNGROUNDED"),
                research_quote=a.get("research_quote", ""),
                issue=a.get("issue", ""),
                recommendation=a.get("recommendation", ""),
            ))

        gaps = []
        for g in result_data.get("uncovered_research_findings", []):
            gaps.append(ResearchGap(
                finding=g.get("finding", ""),
                importance=g.get("importance", "medium"),
                suggested_criterion_id=g.get("suggested_criterion_id", ""),
                suggested_description=g.get("suggested_description", ""),
            ))

        trace_result = TraceResult(
            criterion_audits=audits,
            uncovered_findings=gaps,
            grounding_score=result_data.get("overall_grounding_score", 0.0),
            summary=result_data.get("summary", ""),
        )

        # Log results
        grounded = sum(1 for a in audits if a.status == "GROUNDED")
        partial = sum(1 for a in audits if a.status == "PARTIALLY_GROUNDED")
        ungrounded = sum(1 for a in audits if a.status in ("UNGROUNDED", "HALLUCINATED"))
        self._log(f"Audit: {grounded} grounded, {partial} partial, {ungrounded} ungrounded/hallucinated")
        self._log(f"Grounding score: {trace_result.grounding_score:.0%}")
        if trace_result.high_priority_gaps:
            self._log(f"High-priority research gaps: {len(trace_result.high_priority_gaps)}")
        self._log(f"Summary: {trace_result.summary}")

        return trace_result

    def patch_rubric(self, rubric: Rubric, trace_result: TraceResult, research: str) -> Rubric:
        """Patch rubric based on traceability audit results.

        Three actions:
        1. Update research_basis on grounded criteria (add the actual quote)
        2. Flag ungrounded criteria by prepending [UNGROUNDED] to their description
        3. If there are high-priority gaps AND ungrounded criteria, replace the worst
           ungrounded criteria with new research-backed ones

        Args:
            rubric: the original rubric
            trace_result: the audit results
            research: raw research text for generating replacement criteria

        Returns:
            Patched rubric (new object, original unchanged)
        """
        import copy
        patched = copy.deepcopy(rubric)

        # Build lookup
        audit_map = {a.criterion_id: a for a in trace_result.criterion_audits}

        # Step 1: Update research_basis on grounded/partial criteria
        for criterion in patched.criteria:
            audit = audit_map.get(criterion.id)
            if not audit:
                continue

            if audit.status == "GROUNDED" and audit.research_quote:
                criterion.research_basis = audit.research_quote

            elif audit.status == "PARTIALLY_GROUNDED" and audit.research_quote:
                criterion.research_basis = f"[Partial] {audit.research_quote}"

            elif audit.status == "HALLUCINATED":
                criterion.research_basis = f"[HALLUCINATED — claimed basis not found in research] {criterion.research_basis}"
                self._log(f"  Flagged hallucinated: {criterion.id}")

        # Step 2: Replace ungrounded criteria with high-priority research gaps
        ungrounded = [a for a in trace_result.criterion_audits if a.status in ("UNGROUNDED", "HALLUCINATED")]
        high_gaps = trace_result.high_priority_gaps

        replacements_made = 0
        max_replacements = min(len(ungrounded), len(high_gaps), 3)  # cap at 3 swaps

        if max_replacements > 0 and high_gaps:
            self._log(f"  Replacing up to {max_replacements} ungrounded criteria with research-backed ones")

            # Generate replacement criteria via LLM
            replacement_specs = self._generate_replacements(
                rubric, ungrounded[:max_replacements], high_gaps[:max_replacements], research
            )

            if replacement_specs:
                # Map old criterion IDs to remove
                ids_to_remove = set()
                for i, spec in enumerate(replacement_specs):
                    if i < len(ungrounded):
                        ids_to_remove.add(ungrounded[i].criterion_id)

                # Remove ungrounded, add replacements
                patched.criteria = [c for c in patched.criteria if c.id not in ids_to_remove]

                for spec in replacement_specs:
                    scoring = self._build_basic_scoring(spec)
                    new_criterion = Criterion(
                        id=spec.get("id", f"research_gap_{replacements_made}"),
                        category=spec.get("category", "research_grounded"),
                        description=spec.get("description", ""),
                        pass_condition=spec.get("pass_condition", ""),
                        scoring=scoring,
                        source="research_tracer",
                        pass_examples=spec.get("pass_examples", []),
                        fail_examples=spec.get("fail_examples", []),
                        domain=rubric.domain,
                        research_basis=spec.get("research_basis", ""),
                    )
                    patched.criteria.append(new_criterion)
                    replacements_made += 1
                    self._log(f"  Replaced with: {new_criterion.id} (grounded: {new_criterion.research_basis[:80]}...)")

        # Recalculate total points
        patched.total_points = sum(c.scoring.max_points for c in patched.criteria)

        # Step 3: Log provenance summary
        grounded_count = sum(1 for c in patched.criteria if c.research_basis and not c.research_basis.startswith("["))
        self._log(f"  Final: {grounded_count}/{len(patched.criteria)} criteria have research provenance")
        self._log(f"  Replacements made: {replacements_made}")

        return patched

    def _generate_replacements(self, rubric, ungrounded_audits, gaps, research) -> list[dict]:
        """Generate replacement criterion specs for ungrounded criteria."""
        gap_descriptions = "\n".join(
            f"  - {g.finding} (importance: {g.importance})"
            f"\n    Suggested: {g.suggested_description}"
            for g in gaps
        )

        prompt = f"""Generate {len(gaps)} replacement rubric criteria to fill these research-backed gaps.
These criteria replace ungrounded ones that had no basis in domain research.

DOMAIN: {rubric.domain}
TASK: {rubric.task}

RESEARCH GAPS TO FILL:
{gap_descriptions}

RESEARCH CONTEXT:
{research[:6000]}

For each replacement, output a criterion spec matching this format:
{{
  "id": "<snake_case>",
  "category": "<category>",
  "description": "<what this evaluates>",
  "pass_condition": "<concrete threshold>",
  "scoring_method": "weighted_components",
  "max_points": 4,
  "sub_attributes": [
    {{"sub_id": "<id>", "description": "<desc>", "weight": 0.5, "measurement": "<scale>"}}
  ],
  "pass_examples": ["<example>"],
  "fail_examples": ["<example>"],
  "research_basis": "<exact quote or citation from research>"
}}

Output a JSON array of criterion specs. Output ONLY the JSON array."""

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=4000,
                temperature=0,
                messages=[{"role": "user", "content": prompt}],
            )
            raw = response.content[0].text
            parsed = self._parse_json(raw)
            if isinstance(parsed, list):
                return parsed
            elif isinstance(parsed, dict) and "criteria" in parsed:
                return parsed["criteria"]
            return []
        except Exception as e:
            self._log(f"  Replacement generation failed: {e}")
            return []

    def _build_basic_scoring(self, spec: dict) -> ScoringRubric:
        """Build a ScoringRubric from a replacement spec."""
        method_str = spec.get("scoring_method", "weighted_components")
        method_map = {
            "weighted_components": ScoringMethod.WEIGHTED_COMPONENTS,
            "penalty_based": ScoringMethod.PENALTY_BASED,
            "binary": ScoringMethod.BINARY,
        }
        method = method_map.get(method_str, ScoringMethod.WEIGHTED_COMPONENTS)
        max_points = spec.get("max_points", 4)

        sub_attributes = []
        if method == ScoringMethod.WEIGHTED_COMPONENTS:
            for sub in spec.get("sub_attributes", []):
                sub_attributes.append(SubAttribute(
                    sub_id=sub["sub_id"],
                    description=sub.get("description", ""),
                    weight=sub.get("weight", 0.5),
                    measurement=sub.get("measurement", ""),
                ))
            total_w = sum(s.weight for s in sub_attributes)
            if sub_attributes and abs(total_w - 1.0) > 0.01:
                for s in sub_attributes:
                    s.weight = s.weight / total_w

        penalties = {}
        if method == ScoringMethod.PENALTY_BASED:
            penalties = {k: -abs(v) for k, v in spec.get("penalties", {}).items()}

        return ScoringRubric(method=method, max_points=max_points,
                             sub_attributes=sub_attributes, penalties=penalties)

    def _parse_json(self, text: str):
        text = text.strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
        match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', text)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass
        # Try array
        match = re.search(r'\[[\s\S]*\]', text)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
        # Try object
        match = re.search(r'\{[\s\S]*\}', text)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
        return None


# Backward compatibility alias
RubricGenerator = RubricAgent


# ============================================================================
# Adversarial Coverage Auditor — red-teams the rubric to find coverage gaps
# ============================================================================

class AdversarialAuditor:
    """Red-teams a rubric by generating outputs that score high but miss expert expectations.

    Runs in up to 2 rounds:
    1. Generates adversarial outputs that would score 90%+ but lack genuine quality
    2. Identifies what quality dimensions the adversarial outputs exploit
    3. Generates new criteria to close the gaps found
    4. Stops when the red team can no longer find exploitable gaps
    """

    def __init__(self, client, model: str, verbose: bool = True):
        self.client = client
        self.model = model
        self.verbose = verbose

    def _log(self, msg: str):
        if self.verbose:
            print(f"[AdversarialAuditor] {msg}")

    def audit(self, task: str, rubric: Rubric, max_rounds: int = 2) -> tuple[Rubric, dict]:
        """Red-team the rubric and patch coverage gaps.

        Args:
            task: the task description
            rubric: the rubric to audit
            max_rounds: maximum red-team rounds (default 2)

        Returns:
            (patched_rubric, audit_report) where audit_report tracks rounds run,
            adversarial outputs generated, gaps found, criteria added, and convergence.
        """
        import copy

        audit_report: dict = {
            "rounds": 0,
            "adversarial_outputs_generated": 0,
            "gaps_found": 0,
            "criteria_added": 0,
            "converged": False,
        }

        patched = copy.deepcopy(rubric)

        for round_num in range(1, max_rounds + 1):
            self._log(f"Round {round_num}: generating adversarial outputs...")

            adversarial_outputs = self._generate_adversarial_outputs(task, patched)
            if not adversarial_outputs:
                self._log(f"Round {round_num}: no adversarial outputs generated — stopping")
                audit_report["converged"] = True
                break

            audit_report["adversarial_outputs_generated"] += len(adversarial_outputs)
            audit_report["rounds"] = round_num

            all_new_criteria: list[dict] = []
            for adv_output in adversarial_outputs:
                new_criteria = self._identify_gaps_and_generate_criteria(task, patched, adv_output)
                all_new_criteria.extend(new_criteria)

            if not all_new_criteria:
                self._log(f"Round {round_num}: red team couldn't find exploitable gaps — converged")
                audit_report["converged"] = True
                break

            audit_report["gaps_found"] += len(all_new_criteria)

            existing_ids = {c.id for c in patched.criteria}
            added = 0
            for spec in all_new_criteria:
                cid = spec.get("id", "")
                if cid and cid in existing_ids:
                    continue
                criterion = self._build_criterion(spec, patched.domain)
                patched.criteria.append(criterion)
                if cid:
                    existing_ids.add(cid)
                added += 1

            audit_report["criteria_added"] += added
            patched.total_points = sum(c.scoring.max_points for c in patched.criteria)
            self._log(f"Round {round_num}: added {added} criteria "
                      f"(total now: {len(patched.criteria)}, {patched.total_points} pts)")

        if audit_report["rounds"] == 0:
            audit_report["converged"] = True

        return patched, audit_report

    def _build_rubric_summary(self, rubric: Rubric) -> str:
        lines = []
        for c in rubric.criteria:
            lines.append(f"  {c.id} [{c.scoring.max_points}pts]: {c.description}")
            if c.pass_condition:
                lines.append(f"    Pass condition: {c.pass_condition}")
        return "\n".join(lines)

    def _generate_adversarial_outputs(self, task: str, rubric: Rubric) -> list[str]:
        """Generate 3-5 adversarial outputs that satisfy rubric criteria superficially."""
        rubric_summary = self._build_rubric_summary(rubric)

        prompt = f"""You are a clever but shallow AI trying to game a scoring rubric. Given this task and rubric, produce an output that would score 90%+ on every criterion but that a real domain expert would consider inadequate. Focus on: satisfying the letter of each criterion while missing the spirit. Find blind spots — what important qualities does this rubric NOT measure?

TASK: {task}

RUBRIC CRITERIA:
{rubric_summary}

Generate 3-5 adversarial outputs. Each should exploit a DIFFERENT blind spot in the rubric.

Return JSON in this format:
{{
  "adversarial_outputs": [
    {{
      "output": "<the adversarial output text>",
      "exploitation_strategy": "<brief description of which rubric blind spots this exploits>"
    }}
  ]
}}

Output ONLY the JSON."""

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=6000,
                temperature=1,
                messages=[{"role": "user", "content": prompt}],
            )
            raw = response.content[0].text
            parsed = self._parse_json(raw)
            if not parsed:
                return []
            outputs = parsed.get("adversarial_outputs", [])
            results = [o.get("output", "") for o in outputs if o.get("output")]
            self._log(f"  Generated {len(results)} adversarial outputs")
            return results
        except Exception as e:
            self._log(f"  Adversarial generation failed: {e}")
            return []

    def _identify_gaps_and_generate_criteria(
        self, task: str, rubric: Rubric, adv_output: str
    ) -> list[dict]:
        """Identify quality gaps in an adversarial output and propose criteria to close them."""
        rubric_summary = self._build_rubric_summary(rubric)

        prompt = f"""You are a domain expert reviewer. This output scores high on the rubric but was designed to exploit coverage gaps. Identify 2-4 specific quality dimensions that this output lacks but that the rubric fails to measure. For each gap, propose a new criterion with id, description, pass_condition, scoring_method, and max_points.

TASK: {task}

RUBRIC CRITERIA:
{rubric_summary}

ADVERSARIAL OUTPUT (designed to score well but be inadequate):
{adv_output[:3000]}

Return JSON in this format:
{{
  "exploits_found": true,
  "gaps": [
    {{
      "gap_description": "<what quality dimension is missing>",
      "criterion": {{
        "id": "<snake_case_id>",
        "category": "<category>",
        "description": "<what this evaluates>",
        "pass_condition": "<concrete, measurable threshold>",
        "scoring_method": "weighted_components",
        "max_points": 3,
        "sub_attributes": [
          {{"sub_id": "<id>", "description": "<desc>", "weight": 0.5, "measurement": "<scale>"}}
        ]
      }}
    }}
  ]
}}

Set "exploits_found" to false if this output would genuinely satisfy an expert (no real gaps found).
Output ONLY the JSON."""

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=4000,
                temperature=0,
                messages=[{"role": "user", "content": prompt}],
            )
            raw = response.content[0].text
            parsed = self._parse_json(raw)
            if not parsed:
                return []
            if not parsed.get("exploits_found", True):
                return []
            gaps = parsed.get("gaps", [])
            criteria = [g.get("criterion") for g in gaps if g.get("criterion")]
            self._log(f"  Found {len(criteria)} gap(s) to patch")
            return criteria
        except Exception as e:
            self._log(f"  Gap analysis failed: {e}")
            return []

    def _build_criterion(self, spec: dict, domain: str) -> Criterion:
        """Build a Criterion from an adversarial audit spec dict."""
        method_str = spec.get("scoring_method", "weighted_components")
        method_map = {
            "weighted_components": ScoringMethod.WEIGHTED_COMPONENTS,
            "penalty_based": ScoringMethod.PENALTY_BASED,
            "binary": ScoringMethod.BINARY,
            "percentage": ScoringMethod.PERCENTAGE,
            "threshold_tiers": ScoringMethod.THRESHOLD_TIERS,
            "count_based": ScoringMethod.COUNT_BASED,
        }
        method = method_map.get(method_str, ScoringMethod.WEIGHTED_COMPONENTS)
        max_points = spec.get("max_points", 3)

        sub_attributes: list[SubAttribute] = []
        if method == ScoringMethod.WEIGHTED_COMPONENTS:
            for sub in spec.get("sub_attributes", []):
                sub_attributes.append(SubAttribute(
                    sub_id=sub.get("sub_id", ""),
                    description=sub.get("description", ""),
                    weight=sub.get("weight", 0.5),
                    measurement=sub.get("measurement", ""),
                ))
            total_w = sum(s.weight for s in sub_attributes)
            if sub_attributes and abs(total_w - 1.0) > 0.01:
                for s in sub_attributes:
                    s.weight = s.weight / total_w

        scoring = ScoringRubric(method=method, max_points=max_points, sub_attributes=sub_attributes)

        return Criterion(
            id=spec.get("id", f"adv_gap_{id(spec)}"),
            category=spec.get("category", "adversarial_coverage"),
            description=spec.get("description", ""),
            pass_condition=spec.get("pass_condition", ""),
            scoring=scoring,
            source="adversarial_auditor",
            domain=domain,
        )

    def _parse_json(self, text: str):
        text = text.strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
        match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', text)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass
        match = re.search(r'\[[\s\S]*\]', text)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
        match = re.search(r'\{[\s\S]*\}', text)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
        return None


# ============================================================================
# Independent Evaluation Agent — isolated context window for pass/fail decisions
# ============================================================================

class EvaluationAgent:
    """Independent evaluation agent with isolated context window.

    The evaluator operates as the orchestration brain — it makes pass/fail
    decisions, detects regressions, identifies focus areas for the next
    iteration, and decides when to stop. It never sees:
    1. The generation agent's system prompt or generation strategy
    2. The scoring agent's calibration rules or measurement methodology
    3. The rubric agent's research or rubric design rationale

    It only receives:
    1. Numeric scores and criterion breakdowns from the scorer
    2. The rubric's pass threshold and structure
    3. Iteration history (score trajectories, not content)

    This isolation ensures evaluation decisions are based purely on score
    trajectories and convergence patterns, not influenced by how content
    was generated or how scores were derived.
    """

    EVALUATOR_SYSTEM_PROMPT = """You are an evaluation orchestrator. Your role is to analyze score trajectories across iterations and make objective pass/fail decisions.

EVALUATION PRINCIPLES:

1. SCORE TRAJECTORY ANALYSIS: Look at the trend across iterations, not just the latest score. Improving scores indicate the feedback loop is working. Flat or declining scores suggest the generator is stuck.

2. REGRESSION DETECTION: If a score drops more than 5% from the best prior iteration, flag it as a regression. Two consecutive regressions indicate the feedback loop is counterproductive.

3. CONVERGENCE DETECTION: If scores plateau (less than 2% improvement across 2 consecutive iterations), the loop has converged. Further iterations are unlikely to help.

4. FOCUS AREA IDENTIFICATION: Identify the sub-attributes with the largest gap between current score and maximum. These are the highest-leverage improvement targets for the next iteration.

5. HONEST ASSESSMENT: Do not rationalize passing scores that don't meet the threshold. The threshold exists for a reason — content either meets the bar or it doesn't."""

    def __init__(self, pass_threshold: float = 0.85, verbose: bool = True):
        self.pass_threshold = pass_threshold
        self.verbose = verbose
        self.stall_threshold = 2  # iterations without improvement before flagging

    def _log(self, msg: str):
        if self.verbose:
            print(f"[Evaluator] {msg}")

    def evaluate_iteration(
        self,
        iteration_number: int,
        percentage: float,
        criterion_scores: list,
        history: list,
        first_iter_ceiling: float = 0.90,
    ) -> dict:
        """Evaluate a single iteration and return a decision.

        Args:
            iteration_number: current iteration (1-indexed)
            percentage: overall score as fraction (0.0-1.0)
            criterion_scores: list of CriterionScore objects
            history: list of prior Iteration objects (before this one)
            first_iter_ceiling: maximum passable score for iteration 1

        Returns:
            dict with keys:
                - passed: bool — whether content meets threshold
                - should_stop: bool — whether to stop iterating (even if not passed)
                - focus_areas: list of (criterion_id, sub_id, score) tuples
                - regression: bool — whether this iteration regressed
                - consecutive_regressions: int — how many in a row
                - regression_note: str — guidance for next iteration if regressing
                - convergence: bool — whether the loop has converged
        """
        is_first = iteration_number == 1
        result = {
            "passed": False,
            "should_stop": False,
            "focus_areas": [],
            "regression": False,
            "consecutive_regressions": 0,
            "regression_note": "",
            "convergence": False,
        }

        # Determine effective pass threshold
        effective_pass = self.pass_threshold
        if is_first:
            effective_pass = max(self.pass_threshold, first_iter_ceiling)
            if percentage >= self.pass_threshold:
                self._log(f"First-iteration score {percentage:.1%} meets base threshold "
                          f"but ceiling is {first_iter_ceiling:.0%}")

        # Pass check
        if percentage >= effective_pass:
            result["passed"] = True
            self._log(f"PASSED at iteration {iteration_number} ({percentage:.1%})")
            return result

        # Focus area identification
        focus = []
        for cs in criterion_scores:
            for ss in cs.sub_scores:
                if ss.raw_value < 0.8:
                    focus.append((cs.criterion_id, ss.sub_id, ss.raw_value))
            for p in cs.penalties_applied:
                focus.append((cs.criterion_id, p["violation"], 0.0))
        focus.sort(key=lambda x: x[2])
        result["focus_areas"] = focus[:5]

        # Split criteria into protected (>= 75%) vs improvement targets (< 75%)
        result["protected_criteria"] = [
            cs.criterion_id for cs in criterion_scores if cs.percentage >= 0.90
        ]
        result["improvement_targets"] = [
            cs.criterion_id for cs in criterion_scores if cs.percentage < 0.90
        ]

        # Regression detection
        if history:
            best_prev_pct = max(h.percentage for h in history)
            if percentage < best_prev_pct * 0.95:
                drop = best_prev_pct - percentage
                result["regression"] = True
                self._log(f"Regression: {percentage:.1%} vs best {best_prev_pct:.1%} ({drop:.1%} drop)")

                # Count consecutive regressions from history
                consecutive = 1
                for h in reversed(history[1:]):  # skip first, check recent
                    prev_best = max(hh.percentage for hh in history if hh.number < h.number) if h.number > 1 else 0
                    if h.percentage < prev_best * 0.95:
                        consecutive += 1
                    else:
                        break
                result["consecutive_regressions"] = consecutive

                if consecutive >= 2:
                    result["regression_note"] = (
                        "Previous edits caused regressions — try a completely different "
                        "approach to improving these criteria."
                    )

        # Convergence detection (score plateau)
        if len(history) >= 2:
            recent_scores = [h.percentage for h in history[-2:]] + [percentage]
            max_delta = max(recent_scores) - min(recent_scores)
            if max_delta < 0.02:
                result["convergence"] = True
                self._log(f"Convergence detected: scores plateaued within {max_delta:.1%}")

        return result

    def get_focus_areas(self, criterion_scores: list) -> list:
        """Identify sub-attributes with biggest improvement potential."""
        focus = []
        for cs in criterion_scores:
            for ss in cs.sub_scores:
                if ss.raw_value < 0.8:
                    focus.append((cs.criterion_id, ss.sub_id, ss.raw_value))
            for p in cs.penalties_applied:
                focus.append((cs.criterion_id, p["violation"], 0.0))
        focus.sort(key=lambda x: x[2])
        return focus[:5]

    def format_score_breakdown(self, criterion_scores: list) -> str:
        """Format criterion scores as KEEP/IMPROVE breakdown for the edit prompt."""
        lines = []
        for cs in sorted(criterion_scores, key=lambda x: x.percentage):
            status = "KEEP" if cs.percentage >= 0.8 else "IMPROVE"
            lines.append(f"  [{status}] {cs.criterion_id}: {cs.percentage:.0%}")
            if cs.percentage < 0.8 and cs.sub_scores:
                for ss in cs.sub_scores:
                    lines.append(f"    - {ss.sub_id}: {ss.raw_value:.0%} (target: 80%)")
                # Include Stage 1 critique for failing criteria so the generator
                # knows exactly which checks failed and what evidence was missing
                critique = getattr(cs, 'critique', '')
                if critique:
                    lines.append(f"    SCORER CRITIQUE:")
                    for critique_line in critique.strip().split('\n'):
                        lines.append(f"      {critique_line}")
        return "\n".join(lines)


# ============================================================================
# Feedback Learning Loop — tracks fix effectiveness, accumulates learnings
# ============================================================================

class FeedbackLearningLoop:
    """Tracks whether FeedbackAgent fixes actually improve scores, and distills
    learnings into a persistent markdown file that future runs can reference.

    Lifecycle:
    1. After FeedbackAgent generates fixes, call `record_fixes()` to snapshot
       what was prescribed and the current scores.
    2. After the next scoring round, call `record_outcomes()` to compare
       post-fix scores against the snapshot — marking each fix as EFFECTIVE,
       INEFFECTIVE, or HARMFUL.
    3. At end-of-run, call `reflect()` to analyze accumulated effectiveness
       data and distill new learnings into the markdown file.
    4. On next run, `load_learnings()` returns the accumulated wisdom for
       injection into the FeedbackAgent's system prompt.
    """

    LEARNINGS_DIR = ".rubric_data/feedback_learnings"
    LEARNINGS_FILE = "learnings.md"
    HISTORY_FILE = "fix_history.json"

    def __init__(self, verbose: bool = True):
        self.verbose = verbose
        self.dir = Path(self.LEARNINGS_DIR)
        self.dir.mkdir(parents=True, exist_ok=True)
        # Pending fixes from the current iteration, awaiting outcome measurement
        self._pending_fixes: list[dict] = []
        self._pending_scores: dict[str, float] = {}
        self._pending_iteration: int = 0
        # Accumulated fix outcomes across all iterations in this run
        self._run_outcomes: list[dict] = []

    def _log(self, msg: str):
        if self.verbose:
            print(f"[FeedbackLearning] {msg}")

    # ----- Phase 1: Record what was prescribed -----

    def record_fixes(
        self,
        feedback: dict,
        criterion_scores: list,
        iteration: int,
    ):
        """Snapshot the fixes prescribed and current scores before the generator acts.

        Call this right after FeedbackAgent.generate_feedback() returns.
        """
        self._pending_fixes = feedback.get("fix", [])
        self._pending_scores = {
            cs.criterion_id: cs.percentage for cs in criterion_scores
        }
        self._pending_iteration = iteration

    # ----- Phase 2: Measure outcomes after generator acted -----

    def record_outcomes(self, new_criterion_scores: list):
        """Compare post-generation scores against the pre-fix snapshot.

        Call this after the next scoring round completes.
        Each fix is classified as EFFECTIVE (score improved 5%+),
        INEFFECTIVE (no significant change), or HARMFUL (score dropped 5%+).
        """
        if not self._pending_fixes:
            return

        new_scores = {cs.criterion_id: cs.percentage for cs in new_criterion_scores}

        for fix in self._pending_fixes:
            crit_id = fix.get("criterion_id", "")
            old_score = self._pending_scores.get(crit_id, 0)
            new_score = new_scores.get(crit_id, 0)
            delta = new_score - old_score

            if delta >= 0.05:
                effect = "EFFECTIVE"
            elif delta <= -0.05:
                effect = "HARMFUL"
            else:
                effect = "INEFFECTIVE"

            outcome = {
                "iteration": self._pending_iteration,
                "criterion_id": crit_id,
                "sub_id": fix.get("sub_id", ""),
                "instruction": fix.get("instruction", ""),
                "what_failed": fix.get("what_failed", ""),
                "old_score": round(old_score, 3),
                "new_score": round(new_score, 3),
                "delta": round(delta, 3),
                "effect": effect,
            }
            self._run_outcomes.append(outcome)

        effective = sum(1 for o in self._run_outcomes if o["effect"] == "EFFECTIVE")
        harmful = sum(1 for o in self._run_outcomes if o["effect"] == "HARMFUL")
        ineffective = sum(1 for o in self._run_outcomes if o["effect"] == "INEFFECTIVE")
        self._log(
            f"Fix outcomes (iter {self._pending_iteration}→{self._pending_iteration+1}): "
            f"{effective} effective, {ineffective} ineffective, {harmful} harmful"
        )

        # Clear pending state
        self._pending_fixes = []
        self._pending_scores = {}

    # ----- Phase 3: End-of-run reflection -----

    def reflect(self, task: str, model: str = "claude-sonnet-4-20250514"):
        """Analyze accumulated fix outcomes and distill new learnings.

        Uses Claude to identify patterns in what worked vs what didn't,
        then appends new insights to the learnings markdown file.
        """
        if not self._run_outcomes:
            self._log("No fix outcomes to reflect on — skipping")
            return

        # Save raw history for auditability
        self._append_history(task)

        # Load existing learnings for context
        existing = self.load_learnings()

        # Build the reflection prompt
        outcomes_text = self._format_outcomes_for_reflection()

        prompt = f"""You are analyzing the effectiveness of feedback instructions that were given to a content generator during an iterative improvement loop.

TASK CONTEXT: {task}

FIX OUTCOMES FROM THIS RUN:
{outcomes_text}

EXISTING LEARNINGS (accumulated from prior runs):
{existing if existing else "(none yet)"}

Analyze the outcomes and produce NEW learnings. Focus on:

1. PATTERNS IN EFFECTIVE FIXES: What made certain instructions work? Were they more specific? Did they include examples? Did they target structural vs content issues?

2. PATTERNS IN HARMFUL FIXES: What caused regressions? Did fixing one criterion break another? Were instructions too broad, causing rewrites of passing content?

3. PATTERNS IN INEFFECTIVE FIXES: Why didn't some instructions move the needle? Were they too vague? Did they target symptoms rather than root causes?

4. FEEDBACK STYLE RULES: Derive concrete rules for how to write better feedback instructions. Be specific — not "be more specific" but "always include the exact section header where the change should be made."

5. ANTI-PATTERNS TO AVOID: List specific instruction patterns that consistently fail or cause harm.

Return a markdown document with these sections:
## Effective Patterns
## Anti-Patterns (Harmful/Ineffective)
## Feedback Style Rules
## Domain-Specific Notes

Each item should be a concrete, actionable rule — not a vague observation. Include evidence from the outcomes data.
Keep it concise — each rule should be 1-2 sentences max. Remove any existing learnings that are contradicted by new evidence."""

        try:
            if Anthropic is None:
                self._log("anthropic package not available — skipping reflection")
                return
            client = Anthropic(timeout=_API_TIMEOUT)
            response = client.messages.create(
                model=model,
                max_tokens=4000,
                temperature=0,
                messages=[{"role": "user", "content": prompt}],
            )
            new_learnings = response.content[0].text

            # Write the learnings file (replace, not append — the LLM merges old+new)
            learnings_path = self.dir / self.LEARNINGS_FILE
            from datetime import datetime
            header = f"# FeedbackAgent Learnings\n\n_Last updated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}_\n_Runs analyzed: {self._count_runs()}_\n\n"
            learnings_path.write_text(header + new_learnings)
            self._log(f"Updated learnings → {learnings_path}")

        except Exception as e:
            self._log(f"Reflection failed (non-fatal): {e}")

        # Clear run state
        self._run_outcomes = []

    # ----- Loading learnings for injection -----

    def load_learnings(self) -> str:
        """Load the accumulated learnings markdown for injection into FeedbackAgent."""
        learnings_path = self.dir / self.LEARNINGS_FILE
        if learnings_path.exists():
            return learnings_path.read_text()
        return ""

    # ----- Persistence helpers -----

    def _append_history(self, task: str):
        """Append this run's fix outcomes to the persistent JSON history."""
        history_path = self.dir / self.HISTORY_FILE
        history = []
        if history_path.exists():
            try:
                history = json.loads(history_path.read_text())
            except (json.JSONDecodeError, IOError):
                pass

        from datetime import datetime
        history.append({
            "task": task[:200],
            "timestamp": datetime.utcnow().isoformat(),
            "outcomes": self._run_outcomes,
        })

        # Keep last 50 runs to bound file size
        history = history[-50:]
        history_path.write_text(json.dumps(history, indent=2))

    def _count_runs(self) -> int:
        """Count total runs in the history file."""
        history_path = self.dir / self.HISTORY_FILE
        if history_path.exists():
            try:
                return len(json.loads(history_path.read_text()))
            except (json.JSONDecodeError, IOError):
                pass
        return 1

    def _format_outcomes_for_reflection(self) -> str:
        """Format run outcomes into readable text for the reflection prompt."""
        lines = []
        for o in self._run_outcomes:
            lines.append(
                f"[{o['effect']}] {o['criterion_id']}.{o['sub_id']}: "
                f"{o['old_score']:.0%} → {o['new_score']:.0%} (Δ{o['delta']:+.0%})\n"
                f"  Instruction: {o['instruction'][:200]}\n"
                f"  Failed check: {o['what_failed'][:150]}"
            )
        return "\n\n".join(lines)


# ============================================================================
# Independent Feedback Agent — translates scores into actionable diagnostics
# ============================================================================

class FeedbackAgent:
    """Independent feedback agent with isolated context window.

    Sits between the ScoringAgent and GenerationAgent. Deterministically
    converts the ScoringAgent's structured critiques into actionable editing
    instructions for the generator.

    KEY DESIGN PRINCIPLE: The ScoringAgent is the sole source of truth for
    what failed, why, and what evidence was found. The FeedbackAgent does NOT
    re-interpret scores via LLM. It deterministically reads the scorer's
    embedded critiques (critique, suggestion, failed checks with evidence)
    and formats them as editing instructions.

    The ONLY LLM call this agent makes is for regression content comparison:
    when a criterion regressed, the agent compares actual content from the
    best iteration vs the current iteration to explain WHY the score dropped.
    This requires content understanding that can't be done deterministically.

    The feedback agent never sees:
    1. The generation prompt or generation strategy
    2. The scoring agent's calibration rules or system prompt
    3. The rubric design rationale

    It receives:
    1. Structured critiques from the ScoringAgent (per sub-attribute: score,
       critique, suggestion, failed checks with evidence quotes)
    2. CriterionScore objects (for points/weights)
    3. The rubric criteria descriptions (for measurement specs)
    4. Prior iteration scores (for trajectory/regression detection)
    5. Content from best and current iterations (for regression comparison)
    """

    REGRESSION_COMPARISON_PROMPT = """You are analyzing why a criterion's score REGRESSED between two iterations of generated content. Compare the two versions and explain exactly what changed to cause the drop.

CRITERION: {criterion_id}
MEASUREMENT: {measurement_spec}

BEST ITERATION ({best_iter_num}, scored {best_score:.0%}):
--- BEGIN BEST VERSION EXCERPT ---
{best_content}
--- END BEST VERSION EXCERPT ---

CURRENT ITERATION ({current_iter_num}, scored {current_score:.0%}):
--- BEGIN CURRENT VERSION EXCERPT ---
{current_content}
--- END CURRENT VERSION EXCERPT ---

SCORER'S CRITIQUE OF CURRENT VERSION:
{current_critique}

Respond with a JSON object:
{{
  "what_was_lost": "specific content/structure from the best version that was removed or weakened",
  "what_caused_regression": "what the current version changed that hurt the score",
  "recovery_instruction": "exact instruction to recover the lost quality while keeping current improvements"
}}"""

    def __init__(
        self,
        model: str = "claude-sonnet-4-20250514",
        verbose: bool = True,
        learning_loop=None,
    ):
        if Anthropic is None:
            raise ImportError("anthropic package required: pip install anthropic")
        self.client = Anthropic(timeout=_API_TIMEOUT)  # Fresh client, isolated from all other agents
        self.model = model
        self.verbose = verbose
        self.learning_loop = learning_loop or FeedbackLearningLoop(verbose=verbose)

    def _log(self, msg: str):
        if self.verbose:
            print(f"[Feedback] {msg}")

    def generate_feedback(
        self,
        critiques: dict,
        criterion_scores: list,
        rubric,
        iteration_number: int = 1,
        history: list = None,
        tradeoff_context: list = None,
        best_content: str = None,
        current_content: str = None,
    ) -> dict:
        """Generate structured feedback DETERMINISTICALLY from scorer critiques.

        No LLM call except for regression content comparison. Every fix item
        is built directly from the ScoringAgent's embedded critiques — the
        scorer's own words, not an LLM reinterpretation.

        Args:
            critiques: dict from ScoringAgent._last_critiques
                {criterion_id: [{"sub_id", "score", "critique", "suggestion",
                 "evidence", "checks", "is_violation"}]}
            criterion_scores: list of CriterionScore objects
            rubric: the Rubric object with criteria definitions
            iteration_number: current iteration number
            history: list of prior Iteration objects for trajectory analysis
            tradeoff_context: list of tension/priority notes from TradeoffDetector
            best_content: full text of the best-scoring iteration (for regression diff)
            current_content: full text of the current iteration (for regression diff)

        Returns:
            dict with 'preserve', 'fix', 'regressions', and 'summary' keys
        """
        self._log(f"Building deterministic feedback (iteration {iteration_number})...")

        # Index rubric criteria by ID for lookup
        criteria_by_id = {c.id: c for c in rubric.criteria}
        # Index criterion scores by ID
        scores_by_id = {cs.criterion_id: cs for cs in criterion_scores}

        preserve = []
        fix_items = []

        # 1. Deterministic pass: build fix items from scorer critiques
        for cs in sorted(criterion_scores, key=lambda x: x.percentage):
            crit = criteria_by_id.get(cs.criterion_id)
            if not crit:
                continue

            if cs.percentage >= 0.90:
                # This criterion is strong — lower priority for improvement
                preserve.append(f"{cs.criterion_id}: {cs.percentage:.0%} — strong, lower priority")
                continue

            # Get the scorer's critiques for this criterion
            crit_critiques = critiques.get(cs.criterion_id, [])

            if not crit_critiques:
                # No embedded critiques — fall back to score-based fix item
                fix_items.append({
                    "criterion_id": cs.criterion_id,
                    "sub_id": "",
                    "current_score": cs.percentage,
                    "points_at_stake": cs.max_points - cs.points_earned,
                    "what_failed": f"Score {cs.percentage:.0%} below 75% threshold",
                    "what_was_expected": crit.description[:300],
                    "what_was_found": "(no detailed critique from scorer)",
                    "instruction": f"Improve {cs.criterion_id} to meet: {crit.description[:200]}",
                    "failed_checks": [],
                })
                continue

            # Build one fix item per failing sub-attribute
            for sub_critique in crit_critiques:
                sub_score = sub_critique.get("score")
                if sub_score is not None and sub_score >= 0.90:
                    # This sub-attribute is passing
                    continue

                # Get the measurement spec from the rubric
                measurement_spec = ""
                sub_weight = 0
                if crit.scoring.sub_attributes:
                    for sub_attr in crit.scoring.sub_attributes:
                        if sub_attr.sub_id == sub_critique.get("sub_id"):
                            measurement_spec = sub_attr.measurement
                            sub_weight = sub_attr.weight
                            break

                # Calculate points at stake for this sub-attribute
                points_at_stake = cs.max_points * sub_weight if sub_weight else cs.max_points - cs.points_earned

                # Extract failed checks as quoted evidence
                failed_checks = []
                for check in sub_critique.get("checks", []):
                    if isinstance(check, dict) and check.get("result") == "NO":
                        failed_checks.append({
                            "check": check.get("check", ""),
                            "evidence": check.get("evidence", "not found"),
                        })

                # Build the fix item directly from scorer's output
                fix_items.append({
                    "criterion_id": cs.criterion_id,
                    "sub_id": sub_critique.get("sub_id", ""),
                    "current_score": sub_score if sub_score is not None else cs.percentage,
                    "points_at_stake": points_at_stake,
                    "what_failed": sub_critique.get("critique", ""),
                    "what_was_expected": measurement_spec[:300] if measurement_spec else crit.description[:300],
                    "what_was_found": sub_critique.get("evidence", ""),
                    "instruction": sub_critique.get("suggestion", ""),
                    "failed_checks": failed_checks,
                    "is_violation": sub_critique.get("is_violation", False),
                })

        # 2. Detect regressions and do content comparison (LLM call)
        regressions = []
        if history and len(history) >= 2:
            best_iter = max(history, key=lambda h: h.percentage)
            current_iter_obj = history[-1]

            if best_iter.number != current_iter_obj.number:
                best_scores_map = {cs.criterion_id: cs for cs in best_iter.criterion_scores}
                current_scores_map = {cs.criterion_id: cs for cs in current_iter_obj.criterion_scores}

                for crit_id in [c.id for c in rubric.criteria]:
                    b_cs = best_scores_map.get(crit_id)
                    c_cs = current_scores_map.get(crit_id)
                    if not b_cs or not c_cs:
                        continue
                    if b_cs.percentage > c_cs.percentage + 0.05:
                        regression_entry = {
                            "criterion_id": crit_id,
                            "best_score": b_cs.percentage,
                            "best_iteration": best_iter.number,
                            "current_score": c_cs.percentage,
                            "current_iteration": current_iter_obj.number,
                            "delta": round(b_cs.percentage - c_cs.percentage, 4),
                        }

                        # LLM call: compare actual content to explain WHY
                        if best_content and current_content:
                            comparison = self._compare_regression_content(
                                crit_id, criteria_by_id.get(crit_id),
                                best_iter.number, b_cs.percentage,
                                current_iter_obj.number, c_cs.percentage,
                                best_content, current_content,
                                critiques.get(crit_id, []),
                            )
                            if comparison:
                                regression_entry.update(comparison)

                        regressions.append(regression_entry)

        # 3. Apply tradeoff context as annotations on relevant fix items
        if tradeoff_context:
            for fix in fix_items:
                for note in tradeoff_context:
                    if fix["criterion_id"] in note:
                        fix["tradeoff_note"] = note

        # 4. Build summary
        fail_count = len(fix_items)
        pass_count = len(preserve)
        regression_count = len(regressions)
        total_points_at_stake = sum(f.get("points_at_stake", 0) for f in fix_items)

        summary_parts = [f"{fail_count} failing sub-attributes ({total_points_at_stake:.1f} pts recoverable), {pass_count} passing."]
        if regression_count:
            summary_parts.append(f"{regression_count} regressions detected — recovery is top priority.")

        result = {
            "preserve": preserve,
            "fix": fix_items,
            "regressions": regressions,
            "summary": " ".join(summary_parts),
        }

        self._log(f"Built {len(fix_items)} fix items, {len(preserve)} preserved, "
                  f"{len(regressions)} regressions (deterministic)")
        return result

    def _compare_regression_content(
        self,
        criterion_id: str,
        criterion,
        best_iter_num: int,
        best_score: float,
        current_iter_num: int,
        current_score: float,
        best_content: str,
        current_content: str,
        current_critiques: list,
    ) -> dict:
        """LLM call: compare content from best vs current iteration to explain regression.

        This is the ONLY LLM call in the FeedbackAgent. It's necessary because
        understanding WHY content changed requires reading comprehension that
        can't be done deterministically.
        """
        # Build measurement spec from criterion
        measurement_spec = ""
        if criterion and criterion.scoring.sub_attributes:
            measurement_spec = "\n".join(
                f"  - {s.sub_id}: {s.measurement[:200]}"
                for s in criterion.scoring.sub_attributes
            )
        elif criterion:
            measurement_spec = criterion.description

        # Build critique summary from scorer's output
        critique_text = ""
        if current_critiques:
            critique_parts = []
            for c in current_critiques:
                if c.get("critique"):
                    critique_parts.append(f"  {c.get('sub_id', '?')}: {c['critique']}")
                if c.get("evidence"):
                    critique_parts.append(f"    evidence: {c['evidence']}")
            critique_text = "\n".join(critique_parts)

        # Truncate content to relevant portions (avoid context overflow)
        max_chars = 3000
        best_excerpt = best_content[:max_chars]
        current_excerpt = current_content[:max_chars]

        prompt = self.REGRESSION_COMPARISON_PROMPT.format(
            criterion_id=criterion_id,
            measurement_spec=measurement_spec,
            best_iter_num=best_iter_num,
            best_score=best_score,
            current_iter_num=current_iter_num,
            current_score=current_score,
            best_content=best_excerpt,
            current_content=current_excerpt,
            current_critique=critique_text or "(no critique available)",
        )

        try:
            self._log(f"  [Regression] Comparing content for {criterion_id} "
                      f"(iter {best_iter_num} {best_score:.0%} → iter {current_iter_num} {current_score:.0%})...")

            response = self.client.messages.create(
                model=self.model,
                max_tokens=2000,
                temperature=0,
                messages=[{"role": "user", "content": prompt}],
            )
            raw = response.content[0].text

            # Parse JSON response
            match = re.search(r'\{[\s\S]*\}', raw)
            if match:
                result = json.loads(match.group())
                return {
                    "what_was_lost": result.get("what_was_lost", ""),
                    "what_caused_regression": result.get("what_caused_regression", ""),
                    "recovery_instruction": result.get("recovery_instruction", ""),
                }
        except Exception as e:
            self._log(f"  [Regression] Content comparison failed for {criterion_id}: {e}")

        return {}

    def format_for_generator(self, feedback: dict) -> str:
        """Format structured feedback as text for injection into the generation prompt.

        This is the ONLY signal the generator receives about what to fix.
        Every item quotes the scorer's own checks and evidence — no ambiguity,
        no conflicting signals.
        """
        lines = []

        if feedback.get("summary"):
            lines.append(f"DIAGNOSIS: {feedback['summary']}")
            lines.append("")

        # REGRESSIONS FIRST — highest priority
        regressions = feedback.get("regressions", [])
        if regressions:
            lines.append("=" * 50)
            lines.append("REGRESSIONS (RECOVER THESE FIRST — highest priority):")
            lines.append("=" * 50)
            for reg in sorted(regressions, key=lambda r: r.get("delta", 0), reverse=True):
                crit = reg.get("criterion_id", "?")
                delta_pct = int(round(reg.get("delta", 0) * 100))
                lines.append(f"")
                lines.append(f"  REGRESSED: {crit} — was {reg.get('best_score', 0):.0%} at iter {reg.get('best_iteration', '?')}, "
                             f"now {reg.get('current_score', 0):.0%} (-{delta_pct}%)")
                if reg.get("what_was_lost"):
                    lines.append(f"    What was lost: {reg['what_was_lost']}")
                if reg.get("what_caused_regression"):
                    lines.append(f"    Why it dropped: {reg['what_caused_regression']}")
                if reg.get("recovery_instruction"):
                    lines.append(f"    → RECOVER: {reg['recovery_instruction']}")
            lines.append("")

        # Preserve instructions
        if feedback.get("preserve"):
            lines.append("DO NOT CHANGE (these sections are passing):")
            for item in feedback["preserve"]:
                lines.append(f"  ✓ {item}")
            lines.append("")

        # Fix instructions, ordered by points_at_stake
        fixes = feedback.get("fix", [])
        if fixes:
            # Sort by points_at_stake descending
            fixes_sorted = sorted(fixes, key=lambda f: f.get("points_at_stake", 0), reverse=True)
            lines.append("REQUIRED FIXES (ordered by point impact):")
            lines.append("")
            for i, fix in enumerate(fixes_sorted, 1):
                crit = fix.get("criterion_id", "?")
                sub = fix.get("sub_id", "")
                score = fix.get("current_score", 0)
                points = fix.get("points_at_stake", 0)
                sub_label = f".{sub}" if sub else ""
                lines.append(f"  FIX {i}: {crit}{sub_label} (current: {score:.0%}, {points:.1f} pts at stake)")

                # Quote the scorer's critique directly
                if fix.get("what_failed"):
                    lines.append(f"    Scorer's critique: {fix['what_failed']}")
                if fix.get("what_was_expected"):
                    lines.append(f"    Measurement spec: {fix['what_was_expected'][:300]}")
                if fix.get("what_was_found"):
                    lines.append(f"    Evidence found: {fix['what_was_found']}")

                # Quote each failed check with evidence
                for fc in fix.get("failed_checks", []):
                    lines.append(f"    ✗ FAILED CHECK: {fc.get('check', '')}")
                    lines.append(f"      Evidence: {fc.get('evidence', 'not found')}")

                # The scorer's own suggestion
                if fix.get("instruction"):
                    lines.append(f"    → ACTION: {fix['instruction']}")

                # Tradeoff warning if applicable
                if fix.get("tradeoff_note"):
                    lines.append(f"    ⚖ TRADEOFF: {fix['tradeoff_note']}")

                if fix.get("is_violation"):
                    lines.append(f"    ⚠ This is a PENALTY violation — removing it recovers points")

                lines.append("")

        return "\n".join(lines)


# ============================================================================
# PathAgent — Alternative Strategy Explorer for Stuck Criteria
# ============================================================================


def detect_stuck_criteria(
    criterion_scores: list,
    history: list,
    min_iterations: int = 2,
    stuck_threshold: float = 0.05,
    score_ceiling: float = 0.50,
) -> list[dict]:
    """Identify criteria that are stuck: below ceiling and <threshold improvement over min_iterations.

    Returns list of dicts with criterion_id and score_history for each stuck criterion.
    """
    if len(history) < min_iterations:
        return []

    stuck = []
    recent = history[-min_iterations:]
    for cs in criterion_scores:
        if cs.percentage >= score_ceiling:
            continue
        # Check if this criterion failed to improve across recent iterations
        crit_history = []
        for h in recent:
            for hcs in h.criterion_scores:
                if hcs.criterion_id == cs.criterion_id:
                    crit_history.append(hcs.percentage)
                    break
        if len(crit_history) >= min_iterations:
            improvement = max(crit_history) - min(crit_history)
            if improvement < stuck_threshold:
                full_history = []
                for h in history:
                    for hcs in h.criterion_scores:
                        if hcs.criterion_id == cs.criterion_id:
                            full_history.append(hcs.percentage)
                            break
                stuck.append({
                    "criterion_id": cs.criterion_id,
                    "current_score": cs.percentage,
                    "score_history": full_history,
                })
    return stuck


class PathAgent:
    """Explores alternative strategies for stuck criteria.

    Sits alongside the FeedbackAgent. While FeedbackAgent tells the generator
    WHAT is wrong (incremental fixes), PathAgent suggests fundamentally different
    APPROACHES when a criterion is stuck — breaking out of local optima.

    Activation: Only fires when a criterion is below 50% AND has failed to improve
    by >5pp across 2+ iterations. Most criteria never trigger this agent.

    Output: 2-3 ranked alternative strategies per stuck criterion. The generator
    picks ONE and commits to it for 2 iterations (lock-in prevents thrashing).

    Isolation: Own Anthropic client, own context window. Never sees scorer reasoning,
    rubric negotiation, or feedback agent internals.
    """

    EXPLORE_PROMPT = """You are a strategy advisor. A content generator has been trying to satisfy a scoring criterion but is stuck — its score hasn't improved despite multiple attempts.

Your job: suggest 2-3 fundamentally DIFFERENT approaches the generator could try. Not incremental tweaks — completely different strategies.

TASK: {task}

STUCK CRITERION: {criterion_id}
Description: {criterion_description}
Measurement spec: {measurement_spec}
Current score: {current_score:.0%} (stuck for {stuck_iterations} iterations)
Score history: {score_history}

CURRENT APPROACH (what the generator has been doing):
{current_approach}

FAILED FEEDBACK (instructions that didn't help):
{failed_feedback}

Respond with EXACTLY this JSON structure (no other text):
{{
  "current_approach_summary": "1 sentence describing what the generator is currently doing",
  "alternatives": [
    {{
      "rank": 1,
      "strategy": "2-3 sentence description of a fundamentally different approach",
      "why_it_might_work": "1 sentence rationale connecting this to the measurement spec",
      "example_signal": "1 sentence showing what a good implementation would look like"
    }},
    {{
      "rank": 2,
      "strategy": "...",
      "why_it_might_work": "...",
      "example_signal": "..."
    }}
  ],
  "recommendation": "Which alternative you recommend and a 1-sentence reason why"
}}

RULES:
- Suggest 2-3 alternatives (not more)
- Each must be a genuinely different STRATEGY, not a tweak of the current approach
- Ground alternatives in what the measurement spec actually measures
- Do NOT suggest changes to criteria that are passing — only address this stuck criterion"""

    def __init__(self, model: str = "claude-sonnet-4-20250514", verbose: bool = True):
        if Anthropic is None:
            raise ImportError("anthropic package required: pip install anthropic")
        self.client = Anthropic(timeout=_API_TIMEOUT)
        self.model = model
        self.verbose = verbose
        self._path_locks: dict[str, int] = {}  # criterion_id → iteration when path was chosen

    def _log(self, msg: str):
        if self.verbose:
            print(msg)

    def is_locked(self, criterion_id: str, current_iteration: int, lock_duration: int = 2) -> bool:
        """Check if a criterion is locked (path recently chosen, let generator refine it)."""
        if criterion_id not in self._path_locks:
            return False
        return (current_iteration - self._path_locks[criterion_id]) < lock_duration

    def lock(self, criterion_id: str, iteration: int):
        """Lock a criterion after a path is chosen."""
        self._path_locks[criterion_id] = iteration

    def unlock_if_improved(self, criterion_id: str):
        """Unlock a criterion if its score improved significantly (path worked)."""
        if criterion_id in self._path_locks:
            del self._path_locks[criterion_id]

    def explore_alternatives(
        self,
        stuck_criteria: list[dict],
        rubric,
        history: list,
        current_content: str,
        task: str,
        current_iteration: int,
        failed_feedback: list[str] = None,
    ) -> list[dict]:
        """Explore alternative strategies for stuck criteria.

        Returns list of path result dicts, one per stuck criterion.
        """
        results = []
        for stuck in stuck_criteria:
            crit_id = stuck["criterion_id"]

            if self.is_locked(crit_id, current_iteration):
                self._log(f"  [PathAgent] {crit_id} locked — letting generator refine chosen path")
                continue

            # Find the criterion in the rubric
            criterion = None
            for c in rubric.criteria:
                if c.id == crit_id:
                    criterion = c
                    break
            if not criterion:
                continue

            measurement_spec = getattr(criterion, 'measurement', '')
            if not measurement_spec:
                measurement_spec = getattr(criterion, 'description', str(criterion))

            # Build failed feedback from recent history
            recent_feedback = failed_feedback or []
            if not recent_feedback and len(history) >= 2:
                for h in history[-2:]:
                    for cs in h.criterion_scores:
                        if cs.criterion_id == crit_id and cs.improvement_hints:
                            recent_feedback.extend(cs.improvement_hints[:2])

            content_excerpt = current_content[:2000] if current_content else "(no content)"

            score_history_str = " → ".join(
                f"{s:.0%}" for s in stuck.get("score_history", [])
            )

            prompt = self.EXPLORE_PROMPT.format(
                task=task,
                criterion_id=crit_id,
                criterion_description=getattr(criterion, 'description', str(criterion)),
                measurement_spec=measurement_spec,
                current_score=stuck["current_score"],
                stuck_iterations=len(stuck.get("score_history", [])),
                score_history=score_history_str or "N/A",
                current_approach=content_excerpt,
                failed_feedback="\n".join(f"- {f}" for f in recent_feedback) if recent_feedback else "(none recorded)",
            )

            try:
                self._log(f"  [PathAgent] Exploring alternatives for {crit_id} "
                          f"({stuck['current_score']:.0%}, stuck)...")
                response = self.client.messages.create(
                    model=self.model,
                    max_tokens=1500,
                    temperature=0.3,
                    tools=[{"type": "web_search_20250305", "name": "web_search"}],
                    messages=[{"role": "user", "content": prompt}],
                )
                raw = "".join(
                    block.text for block in response.content if hasattr(block, "text")
                )

                match = re.search(r'\{[\s\S]*\}', raw)
                if match:
                    result = json.loads(match.group())
                    result["criterion_id"] = crit_id
                    result["current_score"] = stuck["current_score"]
                    result["score_history"] = score_history_str
                    results.append(result)
                    self.lock(crit_id, current_iteration)
                    self._log(f"  [PathAgent] Found {len(result.get('alternatives', []))} alternatives "
                              f"for {crit_id} (locked for 2 iterations)")
                else:
                    self._log(f"  [PathAgent] Could not parse response for {crit_id}")
            except Exception as e:
                self._log(f"  [PathAgent] Failed for {crit_id} (non-fatal): {e}")

        return results

    def format_for_generator(self, path_results: list[dict]) -> str:
        """Format path exploration results for injection into the generation prompt."""
        if not path_results:
            return ""

        lines = [
            "",
            "ALTERNATIVE STRATEGIES (for stuck criteria — pick ONE approach and commit fully):",
            "",
        ]

        for result in path_results:
            crit_id = result.get("criterion_id", "?")
            current_score = result.get("current_score", 0)
            score_history = result.get("score_history", "N/A")
            current_approach = result.get("current_approach_summary", "")

            lines.append(f"  STUCK: {crit_id} ({current_score:.0%}, history: {score_history})")
            if current_approach:
                lines.append(f"  Current approach: {current_approach}")
            lines.append("")

            for alt in result.get("alternatives", []):
                rank = alt.get("rank", "?")
                strategy = alt.get("strategy", "")
                why = alt.get("why_it_might_work", "")
                example = alt.get("example_signal", "")

                rec = result.get("recommendation", "")
                is_recommended = f"rank {rank}" in str(rec).lower() or (rank == 1 and "1" in str(rec))
                tag = " (RECOMMENDED)" if is_recommended else ""

                lines.append(f"  Alternative {rank}{tag}: {strategy}")
                if why:
                    lines.append(f"  Why: {why}")
                if example:
                    lines.append(f"  Signal: {example}")
                lines.append("")

            lines.append(
                "  INSTRUCTION: Choose ONE alternative above for this criterion. "
                "Do NOT blend multiple alternatives. Commit fully to the chosen "
                "strategy for all sections addressing this criterion."
            )
            lines.append("")

        return "\n".join(lines)


# ============================================================================
# Compute-Aware Iteration Planning (DGM-H Upgrade 5)
# ============================================================================


@_dataclass
class IterationBudget:
    """Snapshot of iteration budget state for ComputePlanner decisions."""
    max_iterations: int
    current_iteration: int
    current_score: float
    score_trajectory: list      # last N scores (floats)


class ComputePlanner:
    """Adapts iteration strategy based on remaining budget and score trajectory.

    Mirrors the compute-aware planning that DGM-H agents developed autonomously —
    built here deliberately rather than left to chance.
    """

    def should_run_self_editor(self, budget: IterationBudget) -> bool:
        """Run SelfEditor when score is stuck and budget is available.

        Don't run when: budget is tight, score is converging, or early in run.
        """
        if budget.current_iteration < 3:
            return False  # too early — not enough data

        # Don't run when close to budget limit
        if budget.max_iterations > 0:
            remaining = budget.max_iterations - budget.current_iteration
            if remaining < 2:
                return False

        # Run if score has been flat for 2+ iterations
        if len(budget.score_trajectory) >= 2:
            recent_delta = abs(
                budget.score_trajectory[-1] - budget.score_trajectory[-2]
            )
            if recent_delta < 0.02:  # stuck
                return True

        return False

    def adjust_max_iterations(self, budget: IterationBudget) -> int:
        """Extend or contract max_iterations based on trajectory.

        - Fast converger: reduce to save budget
        - Stuck but improving: extend to let it run
        - Stuck flat: trigger SelfEditor instead of extending
        """
        if budget.max_iterations == 0:
            return 0  # unlimited mode — don't cap

        if len(budget.score_trajectory) < 3:
            return budget.max_iterations

        recent = budget.score_trajectory[-3:]
        avg_delta = sum(abs(recent[i + 1] - recent[i]) for i in range(2)) / 2

        if avg_delta < 0.01 and budget.current_score > 0.80:
            # Converged at high score — stop early
            return budget.current_iteration + 1

        if avg_delta > 0.03 and budget.current_score < 0.75:
            # Still improving at low score — extend
            return min(budget.max_iterations + 3, 20)

        return budget.max_iterations

    def exploitation_mode(self, budget: IterationBudget) -> bool:
        """Switch to exploitation (no new SelfEditor proposals) when budget < 20%."""
        if budget.max_iterations == 0:
            return False  # unlimited mode
        pct_remaining = (
            (budget.max_iterations - budget.current_iteration)
            / budget.max_iterations
        )
        return pct_remaining < 0.2


# ============================================================================
# Main Harness
# ============================================================================

class RubricLoop:
    def __init__(
        self,
        model: str = "claude-sonnet-4-20250514",
        max_iterations: int = 0,  # 0 = unlimited (run until pass or convergence)
        pass_threshold: float = 0.85,
        verbose: bool = True,
        feedback_dir: str = ".rubric_feedback",
        enable_checkpoints: bool = True,
        checkpoint_callback: callable = None,
        repo_path: str = ".",
        enable_self_improve: bool = True,
        enable_research: bool = True,
        enable_expert_persona: bool = True,
        enable_expert_panel: bool = False,
        enable_exemplar: bool = True,
        enable_rubric_store: bool = True,
        auto_improve_interval: int = 3,
        auto_improve_min_uses: int = 5,
        auto_improve_max_edits: int = 3,
        lean_mode: bool = False,
        iterations_dir: str = ".rubric_iterations",
        use_deterministic: bool = True,
        enable_tradeoff_detection: bool = True,
        enable_quality_gate: bool = True,
        skip_negotiation: bool = False,
        persist_feedback: bool = False,
    ):
        if Anthropic is None:
            raise ImportError("anthropic package is required: pip install anthropic")
        self.client = Anthropic(timeout=_API_TIMEOUT)
        self.model = model
        self.max_iterations = max_iterations
        self.pass_threshold = pass_threshold
        self.verbose = verbose
        self.engine = ScoringEngine()

        # Component 1: Feedback self-improvement loop
        from rubric_system.feedback_loop import FeedbackStore, FeedbackInjector
        self.feedback_store = FeedbackStore(feedback_dir)
        self.feedback_injector = FeedbackInjector(self.feedback_store)

        # Component 2: Verification tracking
        from rubric_system.verification_dashboard import VerificationTracker
        self.tracker = VerificationTracker()

        # Component 3: Checkpoint policy
        from rubric_system.checkpoint_policy import CheckpointPolicy
        self.checkpoint_policy = CheckpointPolicy(
            history_path=str(Path(feedback_dir) / "checkpoint_history.json")
        )
        self.enable_checkpoints = enable_checkpoints
        self.checkpoint_callback = checkpoint_callback  # fn(Checkpoint) -> (action, feedback)

        # Component 4: Self-improvement (Loop 3)
        self.repo_path = repo_path
        self.enable_self_improve = enable_self_improve
        self.persist_feedback = persist_feedback
        self.rubric_store = RubricStore()
        self.outcome_tracker = OutcomeTracker(self.rubric_store, verbose=verbose)
        self.learning_integrator = LearningIntegrator(
            store=self.rubric_store,
            feedback_store=self.feedback_store,
            verbose=verbose,
        )
        self.enable_research = enable_research
        self.enable_expert_persona = enable_expert_persona
        self.enable_expert_panel = enable_expert_panel
        self.enable_exemplar = enable_exemplar
        self.enable_rubric_store = enable_rubric_store
        self.rag_store: Optional[RubricRAGStore] = RubricRAGStore() if enable_rubric_store else None
        self.auto_improve_interval = auto_improve_interval
        self.auto_improve_min_uses = auto_improve_min_uses
        self.auto_improve_max_edits = auto_improve_max_edits
        self.stall_threshold = 2  # iterations without improvement before stopping

        # Component 5: Independent scoring agent (isolated context window)
        self.scoring_agent = ScoringAgent(model=model, verbose=verbose)

        # Component 6: Sprint contract — rubric negotiation agent (isolated context)
        self.negotiation_agent = RubricNegotiationAgent(model=model, verbose=verbose)

        # Component 7: Generation agent (isolated context — separate from scorer)
        self.generation_agent = GenerationAgent(model=model, verbose=verbose)

        # Component 8: Independent evaluation agent (isolated context window)
        self.evaluation_agent = EvaluationAgent(
            pass_threshold=pass_threshold, verbose=verbose
        )

        # Component 9: Independent feedback agent (translates scores → actionable diagnostics)
        self.feedback_agent = FeedbackAgent(model=model, verbose=verbose)

        # Component 12: Path exploration agent (alternative strategy discovery for stuck criteria)
        self.path_agent = PathAgent(model=model, verbose=verbose)

        # Component 10: Trade-off detector (isolated context — resolves inversely
        # correlated criteria before the gen-verify loop begins)
        self.enable_tradeoff_detection = enable_tradeoff_detection
        self.tradeoff_detector = TradeoffDetector(model=model, verbose=verbose)

        # Component 11: Quality gate (isolated context — filters rubric for
        # discriminative power, redundancy, and measurability before the loop)
        self.enable_quality_gate = enable_quality_gate
        from rubric_system.quality_gate import RubricQualityGate
        self.quality_gate = RubricQualityGate(model=model, verbose=verbose)

        # Lean mode: strips iteration-aware scaffolding for A/B testing
        self.lean_mode = lean_mode

        # Component 10: Deterministic verifier (zero-LLM scoring for objectively
        # checkable criteria: word count, format, code syntax, section presence)
        self.use_deterministic = use_deterministic
        if use_deterministic:
            from rubric_system.deterministic_verifier import DeterministicVerifier
            self.det_verifier = DeterministicVerifier()
        else:
            self.det_verifier = None

        # Sprint contract: skip negotiation step when flag is set
        self.skip_negotiation = skip_negotiation

        # File-based artifact handoffs: each iteration written to disk for
        # structured handoff and crash resumability
        self.iterations_dir = iterations_dir

    def _log(self, msg: str):
        if self.verbose:
            print(msg)

    def _log_error_to_file(self, context: str, error: Exception):
        """Persist errors to a log file so they're visible even when stdout is lost."""
        try:
            import traceback
            from datetime import datetime
            log_path = Path(".rubric_data") / "error_log.jsonl"
            log_path.parent.mkdir(parents=True, exist_ok=True)
            entry = {
                "timestamp": datetime.utcnow().isoformat(),
                "context": context,
                "error": str(error),
                "traceback": traceback.format_exc(),
            }
            with open(log_path, "a") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception:
            pass  # Last resort — don't crash the harness

    @staticmethod
    def _extract_hard_constraints(rubric) -> list[str]:
        """Extract word count, slide count, and other hard limits from rubric criteria.

        Scans criterion descriptions and measurement specs for quantitative limits
        (e.g., 'under 600 words', 'exactly 12 slides', '3-5 bullet points') and
        returns them as explicit hard constraints for the generation prompt.
        """
        import re as _re
        constraints = []
        patterns = [
            (_re.compile(r'(?:under|no more than|at most|fewer than|less than|maximum of?)\s+([\d,]+)\s+words?', _re.IGNORECASE),
             lambda m: f"WORD LIMIT: Keep output under {m.group(1)} words. Count carefully."),
            (_re.compile(r'(?:at least|minimum of?|no fewer than)\s+([\d,]+)\s+words?', _re.IGNORECASE),
             lambda m: f"MINIMUM WORDS: Output must be at least {m.group(1)} words."),
            (_re.compile(r'(?:approximately|roughly|around|~)\s*([\d,]+)\s+words?', _re.IGNORECASE),
             lambda m: f"TARGET LENGTH: Aim for ~{m.group(1)} words (stay within ±20%)."),
            (_re.compile(r'(?:exactly|precisely)\s+([\d]+)\s+(?:slides?|sections?|bullets?|points?|items?)', _re.IGNORECASE),
             lambda m: f"EXACT COUNT: Must have exactly {m.group(1)} {m.group(0).split()[-1]}."),
            (_re.compile(r'([\d]+)\s*[-–—]\s*([\d]+)\s+(?:sentences?|bullets?|points?|items?)\s+(?:per|each)', _re.IGNORECASE),
             lambda m: f"PER-SECTION LIMIT: {m.group(1)}-{m.group(2)} {m.group(0).split()[-2]} per section."),
        ]
        seen = set()
        for criterion in rubric.criteria:
            for text_source in [
                getattr(criterion, 'description', ''),
                getattr(criterion, 'measurement', ''),
                str(getattr(criterion, 'scoring', '')),
            ]:
                if not text_source:
                    continue
                for pattern, formatter in patterns:
                    for match in pattern.finditer(text_source):
                        constraint = formatter(match)
                        if constraint not in seen:
                            seen.add(constraint)
                            constraints.append(constraint)
        return constraints

    async def _retry_on_rate_limit(self, fn, *args, max_retries: int = 3, **kwargs):
        """Call fn with exponential backoff on rate limit errors.

        Retries up to max_retries times with 30s, 60s, 120s waits.
        On final failure, re-raises the exception so the caller can
        break the loop and return best-so-far.
        """
        for attempt in range(max_retries + 1):
            try:
                if asyncio.iscoroutinefunction(fn):
                    return await fn(*args, **kwargs)
                else:
                    return fn(*args, **kwargs)
            except Exception as e:
                is_rate_limit = (
                    (RateLimitError is not None and isinstance(e, RateLimitError))
                    or "rate_limit" in str(e).lower()
                    or "429" in str(e)
                )
                is_scoring_error = isinstance(e, ScoringError)
                if is_scoring_error:
                    raise  # Don't retry scoring parse failures — already retried internally
                if not is_rate_limit or attempt >= max_retries:
                    raise
                wait = 30 * (2 ** attempt)  # 30s, 60s, 120s
                self._log(f"  [RateLimit] 429 on attempt {attempt + 1}/{max_retries + 1} — "
                          f"waiting {wait}s before retry...")
                await asyncio.sleep(wait)

    def _save_rubric_markdown(self, rubric: Rubric, task: str) -> Path:
        """Serialize the rubric to a markdown document in rubrics/.

        Creates a human-readable .md file capturing the full rubric structure:
        task, domain, criteria, scoring methods, sub-attributes, penalties,
        thresholds, and research basis.
        """
        import hashlib
        from datetime import datetime

        rubrics_dir = Path("rubrics")
        rubrics_dir.mkdir(exist_ok=True)

        task_hash = hashlib.sha256(task.encode()).hexdigest()[:8]
        timestamp = datetime.utcnow().strftime("%Y-%m-%d_%H%M%S")
        filename = f"rubric_{timestamp}_{task_hash}.md"
        path = rubrics_dir / filename

        lines = []
        lines.append(f"# Rubric: {rubric.domain}")
        lines.append("")
        lines.append(f"**Task:** {task}")
        lines.append("")
        lines.append(f"**Domain:** {rubric.domain}")
        lines.append(f"**Total Points:** {rubric.total_points}")
        lines.append(f"**Pass Threshold:** {rubric.pass_threshold:.0%}")
        lines.append(f"**Criteria Count:** {len(rubric.criteria)}")
        lines.append(f"**Generated:** {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}")
        lines.append("")
        lines.append("---")
        lines.append("")

        for i, c in enumerate(rubric.criteria, 1):
            lines.append(f"## {i}. {c.id}")
            lines.append("")
            lines.append(f"**Category:** {c.category}")
            lines.append(f"**Description:** {c.description}")
            lines.append("")

            if c.pass_condition:
                lines.append(f"**Pass Condition:** {c.pass_condition}")
                lines.append("")

            # Scoring details
            lines.append(f"**Scoring Method:** `{c.scoring.method.value}`")
            lines.append(f"**Max Points:** {c.scoring.max_points}")
            lines.append("")

            # Sub-attributes
            if c.scoring.sub_attributes:
                lines.append("### Sub-Attributes")
                lines.append("")
                lines.append("| Sub-ID | Weight | Description | Measurement |")
                lines.append("|--------|--------|-------------|-------------|")
                for sub in c.scoring.sub_attributes:
                    desc = sub.description.replace("|", "\\|")[:80]
                    meas = sub.measurement.replace("|", "\\|").replace("\n", " ")[:100]
                    lines.append(f"| `{sub.sub_id}` | {sub.weight:.0%} | {desc} | {meas} |")
                lines.append("")

            # Penalties
            if c.scoring.penalties:
                lines.append("### Penalties")
                lines.append("")
                for violation, deduction in c.scoring.penalties.items():
                    lines.append(f"- **{violation}:** {deduction} pts")
                lines.append("")

            # Tiers
            if c.scoring.tiers:
                lines.append("### Threshold Tiers")
                lines.append("")
                for tier_name, tier_val in c.scoring.tiers.items():
                    lines.append(f"- **{tier_name}:** {tier_val}")
                lines.append("")

            # Examples
            if c.pass_examples:
                lines.append("### Pass Examples")
                lines.append("")
                for ex in c.pass_examples:
                    lines.append(f"- {ex}")
                lines.append("")

            if c.fail_examples:
                lines.append("### Fail Examples")
                lines.append("")
                for ex in c.fail_examples:
                    lines.append(f"- {ex}")
                lines.append("")

            # Research basis
            if c.research_basis:
                lines.append(f"**Research Basis:** {c.research_basis}")
                lines.append("")

            lines.append("---")
            lines.append("")

        path.write_text("\n".join(lines))
        self._log(f"Rubric saved: {path}")
        return path

    def _call_claude(self, prompt: str, max_tokens: int = 8000) -> str:
        response = self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.content[0].text

    def _extract_json(self, text: str) -> dict:
        match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', text)
        if match:
            text = match.group(1)
        text = text.strip()

        try:
            return json.loads(text)
        except:
            match = re.search(r'\{[\s\S]*\}', text)
            if match:
                return json.loads(match.group())
            return {}

    async def extract_measurements(self, content: str, rubric: Rubric) -> dict:
        """Use isolated scoring agent to extract measurements (fresh context window)."""
        return self.scoring_agent.score(
            content=content,
            rubric=rubric,
            feedback_injector=self.feedback_injector,
        )

    async def score_content(self, content: str, rubric: Rubric) -> tuple[float, int, list, dict]:
        """Score content against rubric with granular measurements.

        Returns:
            (total_score, max_score, criterion_scores, critiques_dict)
            where critiques_dict is the structured output from ScoringAgent._last_critiques:
            {criterion_id: [{"sub_id", "score", "critique", "suggestion", "evidence", "checks"}]}
        """
        measurements = await self.extract_measurements(content, rubric)

        # Capture structured critiques from the scoring agent for the feedback agent.
        # This is the NEW primary source — embedded critiques from the scorer's JSON,
        # not the old fragile Stage 1 checklist text.
        critiques = getattr(self.scoring_agent, '_last_critiques', {})

        # Legacy fallback: parse Stage 1 checklist text for criterion-level critique strings
        # (used only to populate CriterionScore.critique when _last_critiques is empty)
        checklist = getattr(self.scoring_agent, '_last_checklist', '')
        criterion_ids = [c.id for c in rubric.criteria]
        legacy_critiques = parse_stage1_per_criterion(checklist, criterion_ids) if not critiques else {}

        criterion_scores = []
        det_count = 0
        llm_count = 0

        for criterion in rubric.criteria:
            # Try deterministic verification first (skips LLM scorer for exact checks)
            if self.use_deterministic and self.det_verifier is not None:
                det_score = self.det_verifier.verify_criterion(criterion, content)
                if det_score is not None:
                    det_score.critique = legacy_critiques.get(criterion.id, "")
                    criterion_scores.append(det_score)
                    det_count += 1
                    self._log(
                        f"  [det] {criterion.id}: "
                        f"{det_score.points_earned}/{det_score.max_points} — "
                        f"{det_score.evidence}"
                    )
                    continue

            # Fall through to LLM-based scorer
            crit_measurements = measurements.get(criterion.id, {})
            violations = crit_measurements.pop("violations", []) if isinstance(crit_measurements, dict) else []
            score = self.engine.score_criterion(criterion, crit_measurements, violations)
            # Attach per-criterion critique from Stage 1 checklist
            score.critique = legacy_critiques.get(criterion.id, "")
            criterion_scores.append(score)
            llm_count += 1

        if det_count > 0:
            self._log(
                f"  Scoring breakdown: {det_count} deterministic, "
                f"{llm_count} LLM-scored"
            )

        total = sum(cs.points_earned for cs in criterion_scores)
        max_total = sum(cs.max_points for cs in criterion_scores)

        return total, max_total, criterion_scores, critiques

    def _get_focus_areas(self, criterion_scores: list[CriterionScore]) -> list[tuple[str, str, float]]:
        """Delegate to evaluation agent for focus area identification."""
        return self.evaluation_agent.get_focus_areas(criterion_scores)

    def _format_score_breakdown(self, criterion_scores: list[CriterionScore]) -> str:
        """Delegate to evaluation agent for score breakdown formatting."""
        return self.evaluation_agent.format_score_breakdown(criterion_scores)

    # -------------------------------------------------------------------------
    # Sprint contract helpers (improvement #1)
    # -------------------------------------------------------------------------

    def _negotiate_rubric(self, rubric: Rubric, task: str) -> Rubric:
        """Sprint contract: two-round generator/scorer negotiation before iteration 1.

        Generator reviews the rubric from the producer's perspective and proposes
        changes; scorer reviews each proposal and accepts, rejects, or counter-proposes.
        Skipped when self.skip_negotiation is True.
        """
        if self.skip_negotiation:
            self._log("\n[Sprint Contract] Skipped (--skip-negotiation).")
            return rubric

        self._log("\n[Sprint Contract] Starting rubric negotiation (generator → scorer)...")
        refined, flags = self.negotiation_agent.negotiate(rubric, task)
        if flags:
            self._log(f"  Negotiation log ({len(flags)} flags):")
            for msg in flags:
                self._log(f"    {msg}")
        else:
            self._log("  No flags raised — rubric accepted as-is.")
        return refined

    def _resolve_tradeoffs(self, rubric: "Rubric") -> "tuple[Rubric, List[str]]":
        """Detect and resolve inversely correlated criteria before iteration 1.

        One extra LLM call — the TradeoffDetector (isolated context) analyses
        all criteria pairwise, identifies inverse correlations that would cause
        the loop to ping-pong, and returns a resolved rubric.

        Returns:
            (resolved_rubric, tradeoff_context) — tradeoff_context is a list of
            priority-note strings to inject into the generation agent's prompt.
            Criterion descriptions are NOT modified; the notes live separately.
        """
        self._log("\n[Trade-off Detection] Analysing criteria for inverse correlations...")
        resolved, messages, tradeoff_context = self.tradeoff_detector.detect_and_resolve(rubric)
        if messages:
            self._log(f"  {len(messages)} trade-off(s) resolved:")
            for msg in messages:
                self._log(f"    {msg}")
        else:
            self._log("  No trade-offs detected.")
        return resolved, tradeoff_context

    def _apply_quality_gate(self, rubric: "Rubric", task: str) -> "Rubric":
        """Quality gate: post-generation filter before the gen-verify loop.

        One LLM call — the RubricQualityGate (isolated context) checks
        discriminative power, redundancy, and measurability of each criterion
        and returns a refined rubric ready for the loop.
        """
        self._log("\n[Quality Gate] Filtering rubric for discriminative power...")
        refined, messages = self.quality_gate.run(rubric, task)
        if messages:
            self._log(f"  {len(messages)} refinement(s) applied:")
            for msg in messages:
                self._log(f"    {msg}")
        else:
            self._log("  All criteria passed quality gate — no changes.")
        return refined

    # -------------------------------------------------------------------------
    # File-based artifact handoff helpers (improvements #2 and #3)
    # -------------------------------------------------------------------------

    def _run_id(self, task: str) -> str:
        """Stable run ID derived from task hash + UTC timestamp."""
        import hashlib
        from datetime import datetime
        task_hash = hashlib.sha256(task.encode()).hexdigest()[:8]
        return f"{task_hash}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"

    def _write_iteration_artifact(
        self,
        run_id: str,
        iteration: Iteration,
        prior_percentage: Optional[float] = None,
    ) -> Path:
        """Serialize an iteration result to disk.

        Writes three files per iteration:
        - iter_NNN_content.md  — full generated content (for masking + resume)
        - iter_NNN_meta.json   — scores, delta, focus areas (crash resumability)
        - iter_NNN.json        — combined artifact (backward compatibility)

        Returns the content path (iter_NNN_content.md).
        """
        from dataclasses import asdict
        run_dir = Path(self.iterations_dir) / run_id
        run_dir.mkdir(parents=True, exist_ok=True)

        n = iteration.number
        content_path = run_dir / f"iter_{n:03d}_content.md"
        content_path.write_text(iteration.attempt)

        delta = (
            round(iteration.percentage - prior_percentage, 4)
            if prior_percentage is not None
            else None
        )
        meta = {
            "run_id": run_id,
            "iteration": n,
            "total_score": iteration.total_score,
            "max_score": iteration.max_score,
            "percentage": iteration.percentage,
            "delta_from_prior": delta,
            "focus_areas": iteration.focus_areas,
            "content_path": str(content_path),
            "criterion_scores": [
                {
                    "criterion_id": cs.criterion_id,
                    "points_earned": cs.points_earned,
                    "max_points": cs.max_points,
                    "percentage": cs.percentage,
                }
                for cs in iteration.criterion_scores
            ],
        }
        meta_path = run_dir / f"iter_{n:03d}_meta.json"
        meta_path.write_text(json.dumps(meta, indent=2))

        # Combined artifact for backward compatibility
        combined_path = run_dir / f"iter_{n:03d}.json"
        combined_path.write_text(json.dumps({
            "run_id": run_id,
            "iteration": n,
            "content": iteration.attempt,
            "total_score": iteration.total_score,
            "max_score": iteration.max_score,
            "percentage": iteration.percentage,
            "criterion_scores": [asdict(cs) for cs in iteration.criterion_scores],
            "focus_areas": iteration.focus_areas,
        }, indent=2))

        return content_path



    def _load_best_artifact(self, run_id: str) -> Optional[dict]:
        """Load the best-scoring iteration artifact from disk.

        Used to resume a crashed run or to provide the next iteration with
        a minimal, structured handoff instead of the full in-memory history.
        """
        run_dir = Path(self.iterations_dir) / run_id
        if not run_dir.exists():
            return None
        best: Optional[dict] = None
        for p in sorted(run_dir.glob("iter_*.json")):
            try:
                data = json.loads(p.read_text())
                if best is None or data["percentage"] > best["percentage"]:
                    best = data
            except Exception:
                pass
        return best

    # -------------------------------------------------------------------------
    # Observation masking helpers
    # -------------------------------------------------------------------------

    _MASK_PREFIX = "[CONTENT OFFLOADED"

    def _make_mask(self, iteration: Iteration, content_path: Path) -> str:
        """Return a 3-line summary+pointer that replaces the full content in memory."""
        char_count = len(iteration.attempt)
        return (
            f"[CONTENT OFFLOADED — Iteration {iteration.number}: "
            f"{iteration.percentage:.0%} score, {char_count:,} chars]\n"
            f"Full content saved to: {content_path}\n"
            f"Score: {iteration.total_score:.1f}/{iteration.max_score} pts"
        )

    def _is_masked(self, attempt: str) -> bool:
        return attempt.startswith(self._MASK_PREFIX)

    def _resolve_attempt(self, attempt: str) -> str:
        """Return full content — reads from disk if the attempt was offloaded."""
        if not self._is_masked(attempt):
            return attempt
        m = re.search(r"Full content saved to: (.+)", attempt)
        if m:
            path = Path(m.group(1).strip())
            if path.exists():
                return path.read_text()
        return attempt  # fallback: return the mask (generator sees the pointer)

    # -------------------------------------------------------------------------
    # Resume helpers: rubric serialization + history reconstruction
    # -------------------------------------------------------------------------

    def _save_rubric_artifact(self, run_id: str, rubric: Rubric) -> Path:
        """Persist the rubric to disk so a crashed run can be resumed."""
        run_dir = Path(self.iterations_dir) / run_id
        run_dir.mkdir(parents=True, exist_ok=True)

        def _criterion_to_dict(c: Criterion) -> dict:
            return {
                "id": c.id,
                "category": c.category,
                "description": c.description,
                "pass_condition": c.pass_condition,
                "scoring": {
                    "method": c.scoring.method.value,
                    "max_points": c.scoring.max_points,
                    "sub_attributes": [
                        {
                            "sub_id": sa.sub_id,
                            "description": sa.description,
                            "weight": sa.weight,
                            "measurement": sa.measurement,
                            "thresholds": sa.thresholds,
                        }
                        for sa in c.scoring.sub_attributes
                    ],
                    "penalties": c.scoring.penalties,
                    "tiers": c.scoring.tiers,
                    "points_per_instance": c.scoring.points_per_instance,
                    "max_instances": c.scoring.max_instances,
                },
                "source": c.source,
                "pass_examples": c.pass_examples,
                "fail_examples": c.fail_examples,
                "domain": c.domain,
                "research_basis": c.research_basis,
            }

        data = {
            "task": rubric.task,
            "domain": rubric.domain,
            "total_points": rubric.total_points,
            "pass_threshold": rubric.pass_threshold,
            "criteria": [_criterion_to_dict(c) for c in rubric.criteria],
            "dimensions": [
                {
                    "id": d.id,
                    "name": d.name,
                    "description": d.description,
                    "weight": d.weight,
                    "criteria_ids": d.criteria_ids,
                }
                for d in rubric.dimensions
            ] if rubric.dimensions else None,
        }
        path = run_dir / "rubric.json"
        path.write_text(json.dumps(data, indent=2))
        return path

    def _load_rubric_from_artifact(self, run_id: str) -> Optional[Rubric]:
        """Reconstruct a Rubric from a previously saved rubric.json."""
        path = Path(self.iterations_dir) / run_id / "rubric.json"
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text())
            criteria = []
            for cd in data["criteria"]:
                sd = cd["scoring"]
                scoring = ScoringRubric(
                    method=ScoringMethod(sd["method"]),
                    max_points=sd["max_points"],
                    sub_attributes=[
                        SubAttribute(
                            sub_id=sa["sub_id"],
                            description=sa["description"],
                            weight=sa["weight"],
                            measurement=sa["measurement"],
                            thresholds=sa.get("thresholds", {}),
                        )
                        for sa in sd.get("sub_attributes", [])
                    ],
                    penalties=sd.get("penalties", {}),
                    tiers=sd.get("tiers", {}),
                    points_per_instance=sd.get("points_per_instance", 1.0),
                    max_instances=sd.get("max_instances", 10),
                )
                criteria.append(Criterion(
                    id=cd["id"],
                    category=cd["category"],
                    description=cd["description"],
                    pass_condition=cd["pass_condition"],
                    scoring=scoring,
                    source=cd.get("source", "loaded"),
                    pass_examples=cd.get("pass_examples", []),
                    fail_examples=cd.get("fail_examples", []),
                    domain=cd.get("domain", ""),
                    research_basis=cd.get("research_basis", ""),
                ))
            dimensions = None
            if data.get("dimensions"):
                dimensions = [
                    RubricDimension(
                        id=d["id"],
                        name=d["name"],
                        description=d["description"],
                        weight=d["weight"],
                        criteria_ids=d["criteria_ids"],
                    )
                    for d in data["dimensions"]
                ]
            return Rubric(
                task=data["task"],
                domain=data["domain"],
                criteria=criteria,
                total_points=data["total_points"],
                pass_threshold=data["pass_threshold"],
                dimensions=dimensions,
            )
        except Exception as e:
            self._log(f"[Resume] Failed to load rubric from {path}: {e}")
            return None

    def _load_history_for_resume(self, run_id: str) -> List[Iteration]:
        """Reconstruct history from per-iteration meta.json files.

        All iterations are loaded with their content masked (pointer to disk)
        so they don't bloat context. The caller can selectively resolve the
        most recent ones when needed.
        """
        run_dir = Path(self.iterations_dir) / run_id
        if not run_dir.exists():
            return []
        iterations = []
        for meta_path in sorted(run_dir.glob("iter_*_meta.json")):
            try:
                meta = json.loads(meta_path.read_text())
                n = meta["iteration"]
                content_path = run_dir / f"iter_{n:03d}_content.md"
                # Start with all iterations masked; run() will unmask the last 2
                if content_path.exists():
                    attempt = (
                        f"[CONTENT OFFLOADED — Iteration {n}: "
                        f"{meta['percentage']:.0%} score, "
                        f"{content_path.stat().st_size:,} chars]\n"
                        f"Full content saved to: {content_path}\n"
                        f"Score: {meta['total_score']:.1f}/{meta['max_score']} pts"
                    )
                else:
                    attempt = f"[Content not found: {content_path}]"
                criterion_scores = [
                    CriterionScore(
                        criterion_id=cs["criterion_id"],
                        points_earned=cs["points_earned"],
                        max_points=cs["max_points"],
                        percentage=cs["percentage"],
                    )
                    for cs in meta.get("criterion_scores", [])
                ]
                iterations.append(Iteration(
                    number=n,
                    attempt=attempt,
                    total_score=meta["total_score"],
                    max_score=meta["max_score"],
                    percentage=meta["percentage"],
                    criterion_scores=criterion_scores,
                    focus_areas=meta.get("focus_areas", []),
                ))
            except Exception as e:
                self._log(f"[Resume] Skipping {meta_path.name}: {e}")
        return iterations

    async def generate_content(
        self,
        rubric: Rubric,
        history: list[Iteration],
        focus_areas: list[tuple[str, str, float]],
        current_iter: int = 1,
        max_iterations: int = 1,
        regression_note: str = "",
        context: str = None,
        structured_feedback: str = "",
        tradeoff_context: Optional[List[str]] = None,
        path_alternatives: str = "",
    ) -> str:
        """Generate content optimized for rubric scores, with feedback injection.

        Iteration 1: generate from scratch.
        Iterations 2+: edit the best prior attempt, preserving passing sections.
        """
        # Inject learned feedback into generation prompt
        criteria_ids = [c.id for c in rubric.criteria]
        feedback_section = self.feedback_injector.format_for_generation_prompt(
            task=rubric.task, domain=rubric.domain, criteria_ids=criteria_ids
        )

        if history:
            # Edit mode: improve the most recent draft, using best as a learning signal
            current = history[-1]
            best = max(history, key=lambda h: h.percentage)
            # Resolve content from disk if it was offloaded to save context
            current_content = self._resolve_attempt(current.attempt)

            # Build regression recovery section when current draft fell behind the peak
            regression_section = ""
            if current.percentage < best.percentage - 0.005 and best.number != current.number:
                current_pct = int(round(current.percentage * 100))
                best_pct = int(round(best.percentage * 100))
                # Per-criterion comparison: list criteria where best scored higher
                best_scores = {cs.criterion_id: cs.percentage for cs in best.criterion_scores}
                current_scores = {cs.criterion_id: cs.percentage for cs in current.criterion_scores}
                comparison_lines = []
                for crit_id, b_pct in sorted(best_scores.items()):
                    c_pct = current_scores.get(crit_id, 0.0)
                    if b_pct > c_pct + 0.01:
                        delta = int(round((b_pct - c_pct) * 100))
                        comparison_lines.append(
                            f"  - {crit_id}: iteration {best.number} scored {b_pct:.0%} "
                            f"vs your current {c_pct:.0%} (delta: +{delta}%)"
                        )
                criterion_comparison = "\n".join(comparison_lines) if comparison_lines else "  (no per-criterion data)"
                # Excerpt from best version — first ~1200 chars as reference
                best_content = self._resolve_attempt(best.attempt)
                excerpt = best_content[:1200].rstrip()
                if len(best_content) > 1200:
                    excerpt += "\n[... excerpt truncated ...]"
                regression_section = (
                    f"⚠ REGRESSION DETECTED: Your current draft scored {current_pct}%, "
                    f"but iteration {best.number} scored {best_pct}%.\n\n"
                    f"Here is what iteration {best.number} did well that you should learn from:\n"
                    f"{criterion_comparison}\n\n"
                    f"Your task: incorporate the strengths from iteration {best.number} into your "
                    f"CURRENT DRAFT. Do NOT replace your current draft with the old version — instead, "
                    f"surgically improve the areas where you regressed while keeping your current "
                    f"structure and narrative intact.\n\n"
                    f"For reference, here are the relevant sections from the higher-scoring version "
                    f"(use as inspiration, do not copy verbatim):\n"
                    f"--- BEGIN REFERENCE EXCERPT (iteration {best.number}) ---\n"
                    f"{excerpt}\n"
                    f"--- END REFERENCE EXCERPT ---"
                )

            # Iteration-aware strategy guidance (improvement #5: --lean disables this)
            # In lean mode, skip scaffolding entirely — lets you A/B test whether
            # the early/mid/late prompting is still necessary with newer models.
            if self.lean_mode:
                iteration_guidance = ""
            elif current_iter <= 2:
                iteration_guidance = (
                    "ITERATION STRATEGY (early — iterations 1-2): Make fundamental structural improvements. "
                    "Reorganize, add missing sections, establish the framework. Broad changes are appropriate."
                )
            elif current_iter <= 4:
                iteration_guidance = (
                    "ITERATION STRATEGY (mid — iterations 3-4): Refine existing content. "
                    "Add specificity, evidence, and quantitative detail to weak sections. "
                    "The structure should be solid; now deepen the substance."
                )
            else:
                iteration_guidance = (
                    "ITERATION STRATEGY (late — iteration 5+): Surgical fixes only. "
                    "Target the 2-3 lowest-scoring sub-attributes with precise additions. "
                    "Do not reorganize — make targeted, minimal changes to the weakest spots."
                )

            _protected = [cs.criterion_id for cs in current.criterion_scores if cs.percentage >= 0.90]
            _weak = [cs.criterion_id for cs in current.criterion_scores if cs.percentage < 0.90]
            prompt = EDIT_PROMPT.format(
                task=rubric.task,
                current_score=f"{current.percentage:.0%}",
                current_content=current_content,
                regression_section=regression_section,
                iteration_guidance=iteration_guidance,
                protected_criteria_list=", ".join(_protected) if _protected else "(none)",
                improvement_targets_list=", ".join(_weak) if _weak else "(none)",
            )
            mode_tag = "[lean]" if self.lean_mode else f"[iter {current_iter}/{max_iterations}]"
            regression_tag = f" [REGRESSION from iter {best.number} {best.percentage:.0%}]" if regression_section else ""
            self._log(f"Editing current draft ({current.percentage:.0%}){regression_tag} {mode_tag}...")
        else:
            # First iteration: generate from scratch
            history_section = format_history_for_generation(history)
            focus_section = format_focus_for_generation(focus_areas)
            if regression_note:
                focus_section = (focus_section + f"\n\n⚠ REGRESSION WARNING: {regression_note}").strip()
            prompt = GENERATION_PROMPT.format(
                task=rubric.task,
                history_section=history_section,
                focus_section=focus_section,
            )
            self._log("Generating content...")

        if feedback_section:
            prompt += "\n" + feedback_section

        # Inject trade-off constraints as hard rules (not baked into the rubric
        # descriptions).  These come from TradeoffDetector and are NON-NEGOTIABLE:
        # the generator must not trade away the higher-priority criterion.
        if tradeoff_context:
            prompt += "\n\nHARD PRIORITY RULES (NON-NEGOTIABLE — enforce before all other considerations):\n"
            for note in tradeoff_context:
                prompt += f"  - {note}\n"

        # Inject structured feedback from the FeedbackAgent (iteration 2+)
        # This is the rich, actionable diagnostic that tells the generator
        # exactly what failed, what was expected, and how to fix it.
        if structured_feedback:
            prompt += "\n\nSTRUCTURED FEEDBACK FROM EVALUATOR:\n" + structured_feedback

        # Inject PathAgent alternatives for stuck criteria (iteration 3+)
        # These suggest fundamentally different approaches when incremental
        # feedback hasn't moved the needle on a criterion.
        if path_alternatives:
            prompt += "\n" + path_alternatives

        # Inject hard constraints extracted from rubric criteria (word count, slide count, etc.)
        # These are enforced as NON-NEGOTIABLE limits, not just scoring penalties.
        hard_constraints = self._extract_hard_constraints(rubric)
        if hard_constraints:
            prompt += "\n\nHARD CONSTRAINTS (violating these WILL tank your score — do NOT exceed):\n"
            for hc in hard_constraints:
                prompt += f"  - {hc}\n"

        if context:
            prompt += "\n\nCONTEXT FROM PRIOR WORK:\n---\n" + context + "\n---\n"

        # Route through the isolated GenerationAgent (separate Anthropic client,
        # separate context window — GAN-inspired agent separation)
        return self.generation_agent.generate(prompt, max_tokens=12000)

    def _handle_checkpoint(self, checkpoint) -> tuple[str, str]:
        """Handle a checkpoint — call callback or default to continue."""
        if self.checkpoint_callback:
            action, feedback = self.checkpoint_callback(checkpoint)
            self.checkpoint_policy.record_outcome(checkpoint, action, feedback)
            return action, feedback
        else:
            # Default: log and continue
            self._log(checkpoint.format_prompt())
            self.checkpoint_policy.record_outcome(checkpoint, "continue")
            return "continue", ""

    async def run(
        self,
        task: str,
        context: str = "",
        rubric: Optional[Rubric] = None,
        rubric_name: Optional[str] = None,
        generate_rubric: bool = True,
        seed_content: Optional[str] = None,
        resume_run_id: Optional[str] = None,
    ) -> LoopResult:
        """Run the generation-verification loop with granular scoring,
        feedback injection, verification tracking, and checkpoints.

        Rubric resolution order:
        1. Explicit rubric object (rubric=...)
        2. Resume from prior run (resume_run_id=...) — loads rubric + history from disk
        3. Explicit registry name (rubric_name=...)
        4. Generate bespoke rubric via LLM (default when generate_rubric=True)
        5. Fall back to registry matching (when generate_rubric=False)

        Args:
            task: task description
            context: optional context (file content, etc.)
            rubric: explicit Rubric object — bypasses all resolution
            rubric_name: explicit registry name — looks up by name
            generate_rubric: if True (default), generates a bespoke rubric via LLM
                             when no explicit rubric/name is provided
            resume_run_id: run ID of a prior (possibly crashed) run to continue from
        """
        self._log(f"\n{'='*60}")
        self._log(f"Task: {task[:60]}...")
        self._log(f"{'='*60}")

        # Resume: load prior run state before rubric resolution
        _resuming = False
        _resume_history: List[Iteration] = []
        if resume_run_id:
            _loaded_rubric = self._load_rubric_from_artifact(resume_run_id)
            _resume_history = self._load_history_for_resume(resume_run_id)
            if _loaded_rubric and _resume_history:
                _resuming = True
                if rubric is None:
                    rubric = _loaded_rubric
                self._log(
                    f"Resuming run {resume_run_id} — "
                    f"{len(_resume_history)} prior iteration(s) loaded"
                )
            else:
                self._log(
                    f"[Resume] No valid state found for {resume_run_id}, starting fresh"
                )

        # Rubric resolution
        if rubric is not None:
            matched_name = "explicit" if not _resuming else f"resumed:{rubric.domain}"
            self._log(f"Rubric: {matched_name} ({len(rubric.criteria)} criteria, {rubric.total_points}pts)")
        elif rubric_name is not None:
            rubric, matched_name, _ = resolve_rubric(task, rubric_name=rubric_name)
            self._log(f"Rubric: {matched_name} (registry lookup)")
            self._log(f"  {len(rubric.criteria)} criteria, {rubric.total_points} max points")
        elif generate_rubric:
            # Primary path: generate bespoke rubric (with research + learning context)
            generator = RubricAgent(
                model=self.model, verbose=self.verbose,
                learning_integrator=self.learning_integrator if self.enable_self_improve else None,
                enable_research=self.enable_research,
                enable_expert_persona=self.enable_expert_persona,
                enable_expert_panel=self.enable_expert_panel,
                enable_exemplar=self.enable_exemplar,
                enable_rubric_store=self.enable_rubric_store,
                rag_store=self.rag_store,
            )
            rubric = generator.generate(task, context=context)
            matched_name = f"generated:{rubric.domain}"
            self._log(f"Rubric: {matched_name}")
            self._log(f"  {len(rubric.criteria)} criteria, {rubric.total_points} max points")
        else:
            # Legacy path: registry matching
            rubric, matched_name, confidence = resolve_rubric(task)
            self._log(f"Rubric: {matched_name} (registry match, {confidence:.0%})")
            self._log(f"  {len(rubric.criteria)} criteria, {rubric.total_points} max points")

        # Sprint contract: review generated rubric before first iteration (improvement #1)
        # Skip on resume — the rubric was already negotiated and saved in the prior run.
        if not _resuming:
            rubric = self._negotiate_rubric(rubric, task)

        # Trade-off detection: resolve inversely correlated criteria before the loop
        # starts so that feedback never ping-pongs between opposing objectives.
        # Skip on resume — the rubric was already resolved in the prior run.
        tradeoff_context: List[str] = []
        if not _resuming and self.enable_tradeoff_detection:
            rubric, tradeoff_context = self._resolve_tradeoffs(rubric)

        # Quality gate (Stage 5): filter for discriminative power, redundancy,
        # and measurability before the gen-verify loop starts.
        # Skip on resume — the rubric was already filtered in the prior run.
        if not _resuming and self.enable_quality_gate:
            rubric = self._apply_quality_gate(rubric, task)

        domain = rubric.domain

        # Save rubric as markdown document (skip on resume — already exists)
        if not _resuming:
            self._save_rubric_markdown(rubric, task)

        # Initialize verification tracker
        self.tracker.set_task(task, domain)

        # Configure checkpoint policy
        has_critical = any(c.scoring.max_points >= 10 for c in rubric.criteria)
        self.checkpoint_policy.configure(
            task_complexity="high" if len(rubric.criteria) > 10 else "medium",
            has_critical_criteria=has_critical,
            max_iterations=self.max_iterations,
            pass_threshold=self.pass_threshold,
        )

        # Checkpoint: rubric review (before any work)
        if self.enable_checkpoints:
            rubric_summary = format_rubric_for_generation(rubric)
            checkpoint = self.checkpoint_policy.should_checkpoint_rubric(rubric_summary)
            action, feedback = self._handle_checkpoint(checkpoint)
            if feedback:
                self.feedback_store.add("rubric", feedback, task=task, domain=domain)
            if action == "stop":
                self.tracker.complete()
                return LoopResult(
                    success=False, output="", iterations=0,
                    final_score=0, final_percentage=0,
                    rubric=rubric, history=[],
                    improvement_summary=["Stopped at rubric review checkpoint"]
                )

        consecutive_regressions = 0
        stall_count = 0  # consecutive iterations without score improvement
        regression_note = ""
        last_feedback_text = ""  # Structured feedback from FeedbackAgent for next iteration
        last_path_text = ""  # Alternative strategies from PathAgent for stuck criteria

        # Run ID + history init (resume reuses the existing run directory)
        if _resuming:
            run_id = resume_run_id
            history = _resume_history
            # Apply masking to all but the most recent 2 iterations so older
            # content doesn't bloat context.  Recent 2 keep full content in
            # memory; generator resolves older ones from disk when needed.
            for old_iter in history[:-2]:
                if not self._is_masked(old_iter.attempt):
                    run_dir = Path(self.iterations_dir) / run_id
                    content_path = run_dir / f"iter_{old_iter.number:03d}_content.md"
                    old_iter.attempt = self._make_mask(old_iter, content_path)
        else:
            run_id = self._run_id(task)
            history = []
            # Persist rubric to disk for crash resumability
            self._save_rubric_artifact(run_id, rubric)

        self._log(f"Run ID: {run_id}")

        # Compute-aware iteration planner (DGM-H Upgrade 5)
        compute_planner = ComputePlanner()

        i = len(history)  # Resume continues from the last completed iteration
        while self.max_iterations == 0 or i < self.max_iterations:
            i += 1

            # Build iteration budget and dynamically adjust max_iterations
            score_trajectory = [h.percentage for h in history]
            budget = IterationBudget(
                max_iterations=self.max_iterations,
                current_iteration=i,
                current_score=score_trajectory[-1] if score_trajectory else 0.0,
                score_trajectory=score_trajectory,
            )
            adjusted_max = compute_planner.adjust_max_iterations(budget)
            if adjusted_max != self.max_iterations and adjusted_max > 0:
                self._log(
                    f"  [ComputePlanner] Adjusting max_iterations: "
                    f"{self.max_iterations} → {adjusted_max}"
                )
                self.max_iterations = adjusted_max

            self._log(f"\n{'─'*50}")
            self._log(f"Iteration {i} (threshold: {self.pass_threshold:.0%})")

            focus_areas = []
            if history:
                focus_areas = self._get_focus_areas(history[-1].criterion_scores)
                if focus_areas:
                    self._log(f"Focus: {focus_areas[0][0]}.{focus_areas[0][1]} ({focus_areas[0][2]:.0%})")

            if i == 1 and seed_content:
                # Warm start: use seed as iteration 1 content, skip generation
                content = seed_content
                self._log(f"Warm start: scoring existing draft ({len(seed_content)} chars)...")
            else:
                # Generation with rate limit retry and graceful degradation
                try:
                    content = await self._retry_on_rate_limit(
                        self.generate_content,
                        rubric, history, focus_areas,
                        current_iter=i, max_iterations=self.max_iterations,
                        regression_note=regression_note,
                        context=context if context else None,
                        structured_feedback=last_feedback_text,
                        tradeoff_context=tradeoff_context,
                        path_alternatives=last_path_text,
                    )
                except (RateLimitError, APIError) as e:
                    self._log(f"  [ERROR] Generation failed after retries: {e}")
                    break  # Exit loop — return best so far

            # Track verification iteration
            self.tracker.start_iteration(i, [f"{f[0]}.{f[1]}" for f in focus_areas])

            # Adaptive evaluator tuning (improvement #4): detect score plateau
            # across the last two completed iterations and inject a meta-prompt
            # so the scorer re-examines its checklist rather than rubber-stamping.
            if len(history) >= 2:
                prev_delta = abs(history[-1].percentage - history[-2].percentage)
                if prev_delta <= 0.02:
                    self._log(
                        f"  [Adaptive] Plateau detected "
                        f"({history[-2].percentage:.1%} → {history[-1].percentage:.1%}, "
                        f"Δ={prev_delta:.1%}) — injecting meta-prompt to evaluator"
                    )
                    self.scoring_agent.inject_plateau_prompt()
                else:
                    self.scoring_agent.reset_system_prompt()

            # Scoring with rate limit retry and scoring error recovery
            try:
                total, max_total, criterion_scores, critiques = await self._retry_on_rate_limit(
                    self.score_content, content, rubric,
                )
            except ScoringError as e:
                self._log(f"  [ERROR] Scoring parse failure — skipping iteration {i}: {e}")
                continue  # Skip this iteration, try next
            except (RateLimitError, APIError) as e:
                self._log(f"  [ERROR] Scoring failed after retries: {e}")
                break  # Exit loop — return best so far
            percentage = total / max_total if max_total > 0 else 0

            # Record verification steps
            self.tracker.add_steps_from_criterion_scores(criterion_scores)
            self.tracker.complete_iteration(total, max_total)

            # Feedback learning: measure outcomes of prior iteration's fixes
            if i > 1:
                self.feedback_agent.learning_loop.record_outcomes(criterion_scores)

            self._log(f"\nScore: {total:.1f}/{max_total} ({percentage:.1%})")
            for cs in criterion_scores:
                emoji = "PASS" if cs.percentage >= 0.8 else "WARN" if cs.percentage >= 0.5 else "FAIL"
                self._log(f"   [{emoji}] {cs.criterion_id}: {cs.points_earned:.1f}/{cs.max_points} ({cs.percentage:.0%})")
                if cs.percentage < 0.8 and cs.sub_scores:
                    for ss in cs.sub_scores:
                        if ss.raw_value < 0.8:
                            self._log(f"      - {ss.sub_id}: {ss.raw_value:.0%}")

            # Delegate pass/fail decision to isolated evaluation agent
            eval_result = self.evaluation_agent.evaluate_iteration(
                iteration_number=i,
                percentage=percentage,
                criterion_scores=criterion_scores,
                history=history,  # history before this iteration
            )

            history.append(Iteration(
                number=i,
                attempt=content,
                total_score=total,
                max_score=max_total,
                percentage=percentage,
                criterion_scores=criterion_scores,
                focus_areas=[f"{f[0]}.{f[1]}" for f in focus_areas]
            ))

            # File-based artifact handoff: write content.md + meta.json + combined JSON.
            # Also makes the harness resumable if it crashes mid-loop.
            prior_pct = history[-2].percentage if len(history) >= 2 else None
            content_path = self._write_iteration_artifact(run_id, history[-1], prior_pct)
            self._log(f"  [Artifact] → {content_path}")

            # Observation masking: replace the content of iterations older than the
            # most recent 2 with a summary+pointer so they don't accumulate in context.
            # The generator always resolves the best attempt from disk when needed.
            if len(history) > 2:
                for old_iter in history[:-2]:
                    if not self._is_masked(old_iter.attempt):
                        run_dir = Path(self.iterations_dir) / run_id
                        old_content_path = run_dir / f"iter_{old_iter.number:03d}_content.md"
                        old_iter.attempt = self._make_mask(old_iter, old_content_path)
                        self._log(
                            f"  [Mask] Iter {old_iter.number} offloaded "
                            f"({old_iter.percentage:.0%}) → {old_content_path.name}"
                        )

            # Update regression tracking from evaluation agent
            if eval_result["regression"]:
                consecutive_regressions = eval_result["consecutive_regressions"]
                regression_note = eval_result["regression_note"]
            else:
                consecutive_regressions = 0
                regression_note = ""

            if eval_result["passed"]:
                self.tracker.complete()
                result = LoopResult(
                    success=True,
                    output=content,
                    iterations=i,
                    final_score=total,
                    final_percentage=percentage,
                    rubric=rubric,
                    history=history,
                    best_iteration=i,
                )
                self._post_run(result)
                return result

            # Convergence stop: if scores have plateaued, further iterations won't help
            if eval_result.get("convergence") and i >= 3:
                self._log(f"\nConverged at iteration {i} — scores plateaued. Stopping.")
                break

            # Stall detection: stop if score hasn't improved for stall_threshold consecutive iterations
            if len(history) >= 2:
                best_before_last = max(h.percentage for h in history[:-1])
                if history[-1].percentage > best_before_last + 0.005:
                    stall_count = 0
                else:
                    stall_count += 1

                # DGM-H Upgrade 5: ComputePlanner mid-run self-improvement trigger
                # When score is stuck and budget allows, run SelfEditor before giving up
                if (stall_count >= 1
                        and self.enable_self_improve
                        and compute_planner.should_run_self_editor(budget)
                        and not compute_planner.exploitation_mode(budget)):
                    self._log(
                        "[ComputePlanner] Score stuck — triggering mid-run self-improvement"
                    )
                    try:
                        self._run_auto_improve()
                    except Exception as _cp_e:
                        self._log(f"[ComputePlanner] Mid-run self-improve failed: {_cp_e}")

                if stall_count >= self.stall_threshold:
                    self._log(
                        f"\n[Stall detected] Stopping after iter {i} — "
                        f"no improvement for {stall_count} consecutive iterations"
                    )
                    break

            # Focus-area stall: if the same focus areas appear in 3+ consecutive iterations,
            # the generation agent is stuck and cannot fix those criteria.
            if len(history) >= 3:
                last_3_focus = [frozenset(h.focus_areas) for h in history[-3:]]
                if last_3_focus[0] and last_3_focus[0] == last_3_focus[1] == last_3_focus[2]:
                    self._log(
                        f"\n[Stall detected] Same focus areas repeated 3 consecutive times "
                        f"({', '.join(sorted(last_3_focus[0]))}) — generation agent is stuck. Stopping."
                    )
                    break

            # Checkpoint check (after scoring, before next iteration)
            if self.enable_checkpoints:
                checkpoint = self.checkpoint_policy.should_checkpoint(
                    iteration=i,
                    current_score=percentage,
                    criterion_scores=criterion_scores,
                    history=history,
                )
                if checkpoint:
                    action, feedback = self._handle_checkpoint(checkpoint)
                    if feedback:
                        self.feedback_store.add(
                            "verification", feedback,
                            task=task, domain=domain
                        )
                    if action == "stop":
                        self.tracker.complete()
                        _cp_best = max(history, key=lambda h: h.percentage) if history else None
                        _cp_result = LoopResult(
                            success=False,
                            output=content,
                            iterations=i,
                            final_score=total,
                            final_percentage=percentage,
                            rubric=rubric,
                            history=history,
                            improvement_summary=[f"Stopped at {checkpoint.checkpoint_type} checkpoint"],
                            best_iteration=_cp_best.number if _cp_best else i,
                        )
                        self._post_run(_cp_result)
                        return _cp_result

            # Generate structured feedback for the next iteration's generator
            # The FeedbackAgent deterministically converts scorer critiques into
            # actionable editing instructions. LLM call only for regression diffs.
            #
            # Resolve best iteration content for regression comparison
            _best_content_for_feedback = None
            if len(history) >= 2:
                _best_iter_for_fb = max(history, key=lambda h: h.percentage)
                if _best_iter_for_fb.number != history[-1].number:
                    _best_content_for_feedback = self._resolve_attempt(_best_iter_for_fb.attempt)

            try:
                structured_feedback = self.feedback_agent.generate_feedback(
                    critiques=critiques,
                    criterion_scores=criterion_scores,
                    rubric=rubric,
                    iteration_number=i,
                    history=history,
                    tradeoff_context=tradeoff_context if tradeoff_context else None,
                    best_content=_best_content_for_feedback,
                    current_content=content,
                )
                last_feedback_text = self.feedback_agent.format_for_generator(structured_feedback)
                self._log(f"  [Feedback] {len(structured_feedback.get('fix', []))} fixes, "
                          f"{len(structured_feedback.get('preserve', []))} preserved")
                # Feedback learning: snapshot what we prescribed + current scores
                self.feedback_agent.learning_loop.record_fixes(
                    feedback=structured_feedback,
                    criterion_scores=criterion_scores,
                    iteration=i,
                )
                # Persist feedback to disk alongside iter meta files for auditability
                try:
                    _fb_run_dir = Path(self.iterations_dir) / run_id
                    _fb_path = _fb_run_dir / f"iter_{i + 1:03d}_feedback.json"
                    _fb_record = {
                        "iteration": i + 1,
                        "feedback_text": last_feedback_text,
                        "focus_areas": [
                            cs.criterion_id
                            for cs in criterion_scores
                            if cs.percentage < 0.90
                        ],
                        "protected_criteria": [
                            cs.criterion_id
                            for cs in criterion_scores
                            if cs.percentage >= 0.90
                        ],
                        "improvement_targets": [
                            cs.criterion_id
                            for cs in criterion_scores
                            if cs.percentage < 0.90
                        ],
                        "prior_score": round(percentage, 4),
                        "prior_criterion_scores": {
                            cs.criterion_id: round(cs.percentage, 4)
                            for cs in criterion_scores
                        },
                    }
                    _fb_path.write_text(json.dumps(_fb_record, indent=2))
                    self._log(f"  [Feedback] Persisted → {_fb_path.name}")
                except Exception as _fb_exc:
                    self._log(f"  [Feedback] Could not write feedback file (non-fatal): {_fb_exc}")
            except Exception as e:
                self._log(f"  [Feedback] Generation failed (non-fatal): {e}")
                last_feedback_text = ""

            # PathAgent: explore alternative strategies for stuck criteria (iteration 3+)
            # Only activates when a criterion is below 50% and hasn't improved in 2+ iterations.
            # Provides fundamentally different approaches, not incremental tweaks.
            if i >= 3:
                try:
                    stuck = detect_stuck_criteria(criterion_scores, history)
                    if stuck:
                        # Unlock criteria that improved >10pp (path worked, allow re-exploration)
                        for cs in criterion_scores:
                            if cs.criterion_id in self.path_agent._path_locks:
                                lock_iter = self.path_agent._path_locks[cs.criterion_id]
                                # Find score at lock time
                                for h in history:
                                    if h.number == lock_iter:
                                        for hcs in h.criterion_scores:
                                            if hcs.criterion_id == cs.criterion_id:
                                                if cs.percentage - hcs.percentage > 0.10:
                                                    self.path_agent.unlock_if_improved(cs.criterion_id)
                                                    self._log(f"  [PathAgent] Unlocked {cs.criterion_id} "
                                                              f"(improved {hcs.percentage:.0%} → {cs.percentage:.0%})")
                                                break
                                        break

                        path_results = self.path_agent.explore_alternatives(
                            stuck_criteria=stuck,
                            rubric=rubric,
                            history=history,
                            current_content=content,
                            task=rubric.task,
                            current_iteration=i,
                        )
                        last_path_text = self.path_agent.format_for_generator(path_results)
                        if path_results:
                            # Persist path alternatives to disk for auditability
                            try:
                                _pa_run_dir = Path(self.iterations_dir) / run_id
                                _pa_path = _pa_run_dir / f"iter_{i + 1:03d}_path_alternatives.json"
                                _pa_path.write_text(json.dumps(path_results, indent=2, default=str))
                                self._log(f"  [PathAgent] Persisted → {_pa_path.name}")
                            except Exception as _pa_exc:
                                self._log(f"  [PathAgent] Could not write file (non-fatal): {_pa_exc}")
                    else:
                        last_path_text = ""
                except Exception as e:
                    self._log(f"  [PathAgent] Exploration failed (non-fatal): {e}")
                    last_path_text = ""

        # Return the best-scoring iteration's output. History is preserved in full for
        # the learning loop — regressions are visible there without polluting the output.
        best = max(history, key=lambda h: h.percentage)
        last = history[-1]
        limit_msg = f"Max iterations ({self.max_iterations}) reached" if self.max_iterations > 0 else "Loop ended"
        self._log(
            f"\n{limit_msg}. Last: {last.percentage:.1%} (iter {last.number}), "
            f"Best was: {best.percentage:.1%} (iter {best.number})"
        )
        self.tracker.complete()

        improvements = []
        for cs in sorted(best.criterion_scores, key=lambda x: x.percentage):
            if cs.percentage < 0.8:
                gap = cs.max_points - cs.points_earned
                improvements.append(f"{cs.criterion_id}: +{gap:.1f} pts available")

        # Per-criterion delta analysis across iterations
        if len(history) >= 2:
            iter1_scores = {cs.criterion_id: cs.percentage for cs in history[0].criterion_scores}
            best_scores = {cs.criterion_id: cs.percentage for cs in best.criterion_scores}
            final_scores = {cs.criterion_id: cs.percentage for cs in history[-1].criterion_scores}

            criterion_deltas = []
            for crit_id, s1 in iter1_scores.items():
                sb = best_scores.get(crit_id, s1)
                sf = final_scores.get(crit_id, s1)
                best_delta = sb - s1
                criterion_deltas.append((crit_id, s1, sb, sf, best_delta))

            criterion_deltas.sort(key=lambda x: -x[4])  # Sort by best_delta descending

            improved = [(cid, s1, sb, sf) for cid, s1, sb, sf, d in criterion_deltas if d > 0.05]
            regressed = [(cid, s1, sb, sf) for cid, s1, sb, sf, d in criterion_deltas if d < -0.05]
            plateaued = [(cid, s1, sb, sf) for cid, s1, sb, sf, d in criterion_deltas if -0.05 <= d <= 0.05]

            self._log(f"\nPer-criterion delta analysis ({len(history)} iterations):")
            if improved:
                self._log("  IMPROVED (feedback effective):")
                for cid, s1, sb, sf in improved:
                    self._log(f"    {cid}: {s1:.0%} → best {sb:.0%}, final {sf:.0%}")
            if regressed:
                self._log("  REGRESSED (feedback harmful/ineffective):")
                for cid, s1, sb, sf in regressed:
                    self._log(f"    {cid}: {s1:.0%} → best {sb:.0%}, final {sf:.0%}")
            if plateaued:
                self._log("  PLATEAUED (no significant change):")
                for cid, s1, sb, sf in plateaued:
                    self._log(f"    {cid}: {s1:.0%} → best {sb:.0%}")

            delta_lines = [f"DELTA ANALYSIS ({len(history)} iterations, iter1→best→final):"]
            for cid, s1, sb, sf, d in criterion_deltas:
                status = "IMPROVED" if d > 0.05 else "REGRESSED" if d < -0.05 else "PLATEAUED"
                delta_lines.append(f"  [{status}] {cid}: {s1:.0%} → {sb:.0%} → {sf:.0%}")
            improvements.extend(delta_lines)

        result = LoopResult(
            success=False,
            output=self._resolve_attempt(best.attempt),
            iterations=len(history),
            final_score=best.total_score,
            final_percentage=best.percentage,
            rubric=rubric,
            history=history,
            improvement_summary=improvements,
            best_iteration=best.number,
        )
        self._post_run(result)
        return result

    def _post_run(self, result: LoopResult):
        """Post-run hook: persist scored rubric, scan outcomes, improve generation, auto-edit."""
        try:
            import hashlib
            from datetime import datetime

            # Save scored rubric to store for long-term learning
            task_hash = hashlib.sha256(result.rubric.task.encode()).hexdigest()[:12]
            rubric_id = f"run_{task_hash}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"

            record = ScoredRubricRecord(
                id=rubric_id,
                task=result.rubric.task,
                task_hash=task_hash,
                template_id=None,
                criteria=[
                    {"id": c.id, "description": c.description, "category": c.category,
                     "max_points": c.scoring.max_points}
                    for c in result.rubric.criteria
                ],
                scores=[
                    {"criterion_id": cs.criterion_id, "points_earned": cs.points_earned,
                     "max_points": cs.max_points, "percentage": cs.percentage,
                     "passed": cs.percentage >= 0.8}
                    for cs in result.history[-1].criterion_scores
                ],
                overall_score=result.final_percentage,
                outcome=None,
                outcome_details=None,
                days_to_bug=None,
                created_at=datetime.utcnow().isoformat(),
                project=None,
                author=None,
                iteration_count=result.iterations,
            )
            self.rubric_store.save_rubric(record)
            self._log(f"[Loop3] Saved scored rubric: {rubric_id}")

            # RubricRAG: persist rubric for future retrieval-augmented generation
            if self.enable_rubric_store and self.rag_store is not None:
                try:
                    self.rag_store.save(result.rubric.task, result.rubric, result.final_percentage)
                    self._log("[RubricRAG] Saved rubric to retrieval store")
                except Exception as _e:
                    self._log(f"[RubricRAG] Save failed (non-fatal): {_e}")

                # RubricRAG seeding: persist per-criterion effectiveness metadata so
                # future runs can retrieve individual criteria (not whole rubrics) that
                # proved discriminating on similar tasks, injecting them as seeds.
                if result.history:
                    try:
                        self.rag_store.save_criterion_effectiveness(
                            result.rubric.task, result.rubric, result.history
                        )
                        self._log("[RubricRAG] Saved per-criterion effectiveness metadata")
                    except Exception as _e:
                        self._log(f"[RubricRAG] Criterion effectiveness save failed (non-fatal): {_e}")

            # Scan for outcome signals from prior runs
            signals = self.outcome_tracker.scan_git_outcomes(
                repo_path=self.repo_path, lookback_days=14
            )
            if signals:
                self._log(f"[Loop3] Detected {len(signals)} outcome signals from git")

            # --- Regression suite: auto-grow ---
            # Append best-scoring task results so future patches are validated against them.
            try:
                suite = RegressionSuite(verbose=self.verbose)
                cs_for_suite = [
                    {"criterion_id": cs["criterion_id"], "percentage": cs["percentage"]}
                    for cs in record.scores
                ]
                added = suite.add_entry(
                    task=result.rubric.task,
                    rubric_id=rubric_id,
                    criterion_scores=cs_for_suite,
                    overall_score=result.final_percentage,
                )
                if added:
                    self._log(
                        f"[RegressionSuite] Entry added/updated "
                        f"(score: {result.final_percentage:.1%}, "
                        f"{len(cs_for_suite)} criteria)"
                    )
            except Exception as _rs_e:
                self._log(f"[RegressionSuite] Auto-grow failed (non-fatal): {_rs_e}")

        except Exception as e:
            self._log(f"[Loop3] Post-run hook error (non-fatal): {e}")
            self._log_error_to_file("post_run_save", e)

        if not self.enable_self_improve and not self.persist_feedback:
            return

        # Feedback learning loop: reflect on fix effectiveness and update learnings
        if self.enable_self_improve or self.persist_feedback:
            try:
                self.feedback_agent.learning_loop.reflect(
                    task=result.rubric.task,
                    model=self.model,
                )
            except Exception as e:
                self._log(f"[FeedbackLearning] Reflection failed (non-fatal): {e}")
                self._log_error_to_file("feedback_reflect", e)

        if not self.enable_self_improve:
            return

        # Analyze rubric generation quality and store improvement signals
        self._post_run_improve_generation(result)

        # --- Regression suite: post-apply monitoring ---
        if self.enable_self_improve:
            self._check_post_apply_regression()

        # Auto self-improvement: propose and apply code edits when enough data
        if self._should_auto_improve():
            self._run_auto_improve()

    def _post_run_improve_generation(self, result: LoopResult):
        """Analyze rubric generation quality and log improvement signals.

        Detects non-discriminating criteria (always pass) and stuck criteria
        (never improve), writes them as feedback so LearningIntegrator picks
        them up on the next rubric generation.
        """
        if not self.enable_self_improve or not result.history:
            return

        try:
            final_scores = result.history[-1].criterion_scores

            # Criteria that max-score on first attempt (too easy / not discriminating)
            always_pass = [
                cs for cs in final_scores
                if cs.percentage >= 0.95
            ]

            # Criteria that never improve across iterations (possibly unmeasurable)
            never_improve = []
            if len(result.history) >= 2:
                first_scores = {cs.criterion_id: cs.percentage for cs in result.history[0].criterion_scores}
                final_scores_map = {cs.criterion_id: cs.percentage for cs in final_scores}
                for cid, first_pct in first_scores.items():
                    final_pct = final_scores_map.get(cid, 0)
                    if final_pct <= first_pct and final_pct < 0.7:
                        never_improve.append(cid)

            # Store as feedback for future rubric generation
            if always_pass:
                ids = [cs.criterion_id for cs in always_pass]
                self.feedback_store.add(
                    "rubric",
                    f"These criteria scored 95%+ on first attempt and don't discriminate quality "
                    f"— consider making them harder or removing: {', '.join(ids)}",
                    task=result.rubric.task,
                    domain=result.rubric.domain,
                )
                self._log(f"[Loop3] Flagged {len(always_pass)} non-discriminating criteria")

            if never_improve:
                self.feedback_store.add(
                    "rubric",
                    f"These criteria never improved across {result.iterations} iterations and scored "
                    f"<70% — may be unmeasurable or need clearer measurements: {', '.join(never_improve)}",
                    task=result.rubric.task,
                    domain=result.rubric.domain,
                )
                self._log(f"[Loop3] Flagged {len(never_improve)} stuck criteria")

        except Exception as e:
            self._log(f"[Loop3] Generation improvement analysis error (non-fatal): {e}")

    def _should_auto_improve(self) -> bool:
        """Decide whether to trigger automatic self-improvement.

        Triggers every N runs (auto_improve_interval), but only if:
        - At least 3 scored rubrics exist in the store
        - Total criterion evaluations across all runs meet threshold

        Note: with generated rubrics, individual criterion IDs rarely repeat.
        So we check TOTAL evaluations across all criteria, not per-criterion usage.
        This means even with unique criterion IDs per run, the system accumulates
        enough signal from aggregate patterns (e.g., all "methodology" criteria
        tend to score high, all "precision" criteria tend to score low).
        """
        try:
            if not self.auto_improve_interval:
                return False

            # Use rubric run count for interval trigger (not criterion evals)
            total_runs = self.rubric_store.count_rubrics()
            if total_runs < 3:
                return False

            # Only trigger every Nth run
            if total_runs % self.auto_improve_interval != 0:
                return False

            # With generated rubrics, check total criterion data points
            # rather than per-criterion usage (since IDs don't repeat)
            from rubric_system.rubric_learning import RubricLearner
            learner = RubricLearner(self.rubric_store)
            insights = learner.get_insights()

            all_stats = insights.get("all_criteria_stats", [])
            total_criterion_datapoints = sum(
                s.get("times_used", 0) for s in all_stats
            ) if all_stats else 0

            # Need at least min_uses total data points across all criteria
            return total_criterion_datapoints >= self.auto_improve_min_uses
        except Exception:
            return False

    def _run_auto_improve(self):
        """Execute automatic self-improvement: propose and apply code edits."""
        self._log("[Loop3] Auto self-improvement triggered")
        try:
            editor = SelfEditor(
                store=self.rubric_store,
                feedback_store=self.feedback_store,
                verbose=self.verbose,
            )
            proposals = editor.auto_improve(
                min_uses=self.auto_improve_min_uses,
                dry_run=False,
                max_edits=self.auto_improve_max_edits,
            )
            if proposals:
                self._log(f"[Loop3] Auto-applied {len(proposals)} self-edit(s)")
                for p in proposals:
                    self._log(f"  - {p.target_function}: {p.rationale[:80]}")
        except Exception as e:
            self._log(f"[Loop3] Auto self-improvement error (non-fatal): {e}")

    def _check_post_apply_regression(self):
        """Post-apply monitoring: revert last self-edit if mean score drops >2pp.

        Pulls the N most recent overall scores from the rubric store and compares
        them against the regression suite baseline mean.  If the drop exceeds 2pp,
        the last self-edit commit is reverted via git.
        """
        try:
            suite = RegressionSuite(verbose=self.verbose)
            if not suite.entries:
                return  # nothing to compare against yet

            import sqlite3
            with sqlite3.connect(self.rubric_store.db_path) as conn:
                rows = conn.execute(
                    "SELECT overall_score FROM scored_rubrics "
                    "ORDER BY created_at DESC LIMIT 5"
                ).fetchall()
            if not rows:
                return

            recent_scores = [r[0] for r in rows]
            regressed, delta = suite.mean_score_regression(recent_scores, threshold_pp=0.02)

            if regressed:
                self._log(
                    f"[RegressionSuite] Mean score regression detected: "
                    f"{delta:.1%} drop (baseline mean from {len(suite.entries)} entries). "
                    f"Auto-reverting last self-edit..."
                )
                editor = SelfEditor(
                    store=self.rubric_store,
                    feedback_store=self.feedback_store,
                    verbose=self.verbose,
                )
                reverted = editor.revert_last_edit()
                if reverted:
                    self._log("[RegressionSuite] Last self-edit reverted successfully")
                else:
                    self._log("[RegressionSuite] Revert skipped (last commit was not a self-edit)")
            else:
                self._log(
                    f"[RegressionSuite] Post-apply check passed "
                    f"(delta: {delta:+.1%} vs baseline)"
                )
        except Exception as e:
            self._log(f"[RegressionSuite] Post-apply monitoring failed (non-fatal): {e}")

    def self_improve(self, dry_run: bool = True, max_edits: int = 3) -> list:
        """Run the self-improvement cycle: analyze learnings and propose/apply source edits.

        Args:
            dry_run: if True, only proposes edits without applying. Set False to auto-apply.
            max_edits: maximum number of edits to apply in one cycle.

        Returns:
            List of SelfEditProposal objects (applied or proposed).
        """
        if not self.enable_self_improve:
            self._log("Self-improvement disabled")
            return []

        editor = SelfEditor(
            store=self.rubric_store,
            feedback_store=self.feedback_store,
            verbose=self.verbose,
        )
        return editor.auto_improve(
            min_uses=5,
            dry_run=dry_run,
            max_edits=max_edits,
        )

    def save_dashboard(self, path: str = "verification_dashboard.html"):
        """Save the verification dashboard after a run completes."""
        from rubric_system.verification_dashboard import DashboardGenerator
        DashboardGenerator(self.tracker).save(path)
        self._log(f"Dashboard saved to {path}")

    def add_feedback(self, feedback_type: str, content: str, criterion_id: str = "", **kwargs):
        """Add human feedback to the persistent store."""
        self.feedback_store.add(
            feedback_type=feedback_type,
            content=content,
            criterion_id=criterion_id,
            **kwargs
        )


# ============================================================================
# Module initialization — register all built-in rubrics
# ============================================================================

_register_builtin_rubrics()


# ============================================================================
# CLI
# ============================================================================

async def main():
    import argparse

    parser = argparse.ArgumentParser(description="Rubric Loop - Granular Scoring")
    parser.add_argument("task", nargs="?", help="Task description")
    parser.add_argument("--context", "-c", nargs="+", metavar="FILE",
                        help="One or more context files (chat summaries, notes, reference docs)")
    parser.add_argument("--seed", "-s", metavar="FILE",
                        help="Existing draft file to warm-start from (skips initial generation)")
    parser.add_argument("--rubric", "-r", help="Explicit rubric name (see --list-rubrics)")
    parser.add_argument("--no-generate", action="store_true",
                        help="Disable rubric generation; use registry matching instead")
    parser.add_argument("--list-rubrics", action="store_true", help="List all registered rubrics")
    parser.add_argument("--explain", action="store_true", help="Show rubric resolution explanation")
    parser.add_argument("--max-iter", "-m", type=int, default=0, help="Max iterations (0 = unlimited)")
    parser.add_argument("--threshold", "-t", type=float, default=0.85)
    parser.add_argument("--quiet", "-q", action="store_true")
    parser.add_argument("--json", "-j", action="store_true")
    parser.add_argument("--self-improve", action="store_true",
                        help="Run self-improvement cycle after the loop completes")
    parser.add_argument("--self-improve-apply", action="store_true",
                        help="Run self-improvement and apply edits (not dry run)")
    parser.add_argument("--no-learn", action="store_true",
                        help="Disable learning/outcome tracking for this run")
    parser.add_argument("--no-auto-improve", action="store_true",
                        help="Disable automatic self-editing (keeps learning active)")
    parser.add_argument("--no-research", action="store_true",
                        help="Skip deep research step during rubric generation")
    parser.add_argument("--no-tradeoff-detection", action="store_true",
                        help="Skip trade-off detection step (the pass that resolves inversely "
                             "correlated criteria before the gen-verify loop starts)")
    parser.add_argument("--no-expert-persona", action="store_true",
                        help="Skip expert persona elicitation step during rubric generation")
    parser.add_argument("--expert-panel", action="store_true",
                        help="Enable expert panel simulation: elicit 3 complementary expert "
                             "perspectives and reconcile their criteria into a unified rubric "
                             "(more thorough than single-persona mode; falls back gracefully)")
    parser.add_argument("--no-exemplar", action="store_true",
                        help="Skip exemplar retrieval and contrastive criterion extraction")
    parser.add_argument("--no-rubric-store", action="store_true",
                        help="Disable RubricRAG retrieval store (skip retrieval seeding and persistence)")
    parser.add_argument("--lean", action="store_true",
                        help="Lean mode: strip iteration-aware scaffolding (early/mid/late strategy) "
                             "for A/B testing whether that guidance is still necessary with newer models")
    parser.add_argument("--no-paired-trajectories", action="store_true",
                        help="Disable ACON paired trajectory collection (on by default)")
    parser.add_argument("--paired-iteration", type=int, default=2,
                        help="Which iteration to run paired paths on (default: 2)")
    parser.add_argument("--no-deterministic", action="store_true",
                        help="Disable deterministic verification; use LLM scoring for all criteria")
    parser.add_argument("--no-quality-gate", action="store_true",
                        help="Skip quality gate step (discriminative power, redundancy, "
                             "and measurability checks) that runs after rubric generation")
    parser.add_argument("--resume", metavar="RUN_ID",
                        help="Resume a previous (possibly crashed) run from its last saved checkpoint. "
                             "Provide the run ID printed at the start of the original run "
                             "(e.g. 'abc12345_20260327_143022'). The task argument is still required "
                             "for tracker display but the rubric and history are loaded from disk.")
    parser.add_argument("--skip-negotiation", action="store_true",
                        help="Skip the sprint contract negotiation step (generator/scorer rubric review)")

    args = parser.parse_args()

    # List all registered rubrics
    if args.list_rubrics:
        print(f"\nRegistered rubrics ({len(REGISTRY.registered_names)}):")
        print(f"{'─'*50}")
        for name in sorted(REGISTRY.registered_names):
            sig = REGISTRY.get(name)
            rubric = sig.builder("test")
            kw_preview = ", ".join(sig.keywords[:5])
            print(f"  {name:30s} | {len(rubric.criteria):2d} criteria | {rubric.total_points:3d}pts | kw: {kw_preview}")
        print(f"\nFallback: {REGISTRY._fallback_name}")
        sys.exit(0)

    if not args.task:
        args.task = "Write a research brief on the AI chip market in 2025, including market size, key players, and 2-year forecast"

    # Explain rubric resolution
    if args.explain:
        explanation = REGISTRY.resolve_with_explanation(args.task)
        print(f"\nTask: {explanation['task'][:80]}")
        print(f"Matched: {explanation['matched']} (confidence: {explanation['confidence']:.0%})")
        print(f"Rubric: {explanation['rubric_criteria_count']} criteria, {explanation['rubric_max_points']}pts")
        print(f"\nAll scores:")
        for entry in explanation["all_scores"]:
            bd = entry["breakdown"]
            print(f"  {entry['name']:30s} | score: {entry['score']:5.1f} | "
                  f"kw: {bd['keyword_score']:+.0f} anti: {bd['anti_score']:+.0f} "
                  f"pat: {bd['pattern_score']:+.0f} pri: {bd['priority_bonus']:+.1f}")
            if bd["keyword_hits"]:
                print(f"    keywords hit: {', '.join(bd['keyword_hits'])}")
            if bd["pattern_hits"]:
                print(f"    patterns hit: {', '.join(bd['pattern_hits'][:2])}")
        sys.exit(0)

    context = ""
    if args.context:
        for ctx_path in args.context:
            p = Path(ctx_path)
            if p.exists():
                context += f"\n--- {p.name} ---\n{p.read_text()}\n"
            else:
                print(f"Warning: context file not found: {ctx_path}")

    seed_content = None
    if args.seed:
        p = Path(args.seed)
        if p.exists():
            seed_content = p.read_text()
        else:
            print(f"Error: seed file not found: {args.seed}")
            sys.exit(1)

    loop = RubricLoop(
        max_iterations=args.max_iter,
        pass_threshold=args.threshold,
        verbose=not args.quiet,
        enable_self_improve=not args.no_learn,
        enable_research=not args.no_research,
        enable_expert_persona=not args.no_expert_persona,
        enable_expert_panel=args.expert_panel,
        enable_exemplar=not args.no_exemplar,
        enable_rubric_store=not args.no_rubric_store,
        auto_improve_interval=0 if args.no_auto_improve else 3,
        lean_mode=args.lean,
        use_deterministic=not args.no_deterministic,
        enable_tradeoff_detection=not args.no_tradeoff_detection,
        enable_quality_gate=not args.no_quality_gate,
        skip_negotiation=args.skip_negotiation,
    )

    result = await loop.run(
        args.task, context,
        rubric_name=args.rubric,
        generate_rubric=not args.no_generate,
        seed_content=seed_content,
        resume_run_id=args.resume,
    )

    # ACON paired trajectories (runs automatically after every main loop)
    if not getattr(args, 'no_paired_trajectories', False) and result.history:
        try:
            from rubric_system.acon_trajectory import PairedTrajectoryCollector
            collector = PairedTrajectoryCollector(
                paired_iteration=args.paired_iteration,
                verbose=not args.quiet,
            )
            await collector.collect(
                task=args.task,
                domain=result.rubric.domain,
                rubric=result.rubric,
                history=result.history,
                generate_fn=loop.generate_content,
                score_fn=loop.score_content,
                max_iterations=args.max_iter,
            )
        except Exception as _acon_e:
            if not args.quiet:
                print(f"[ACON] Paired trajectory collection failed: {_acon_e}")

    # Self-improvement cycle
    if args.self_improve or args.self_improve_apply:
        dry_run = not args.self_improve_apply
        proposals = loop.self_improve(dry_run=dry_run)
        if proposals:
            print(f"\n{'='*60}")
            print(f"SELF-IMPROVEMENT: {len(proposals)} proposal(s) {'(dry run)' if dry_run else '(applied)'}")
            for p in proposals:
                print(f"  - {p.target_function}: {p.rationale[:80]}")
        else:
            print("\nSelf-improvement: no proposals (need more data or everything looks healthy)")

    if args.json:
        last_criterion_scores = result.history[-1].criterion_scores if result.history else []
        print(json.dumps({
            "success": result.success,
            "iterations": result.iterations,
            "best_iteration": result.best_iteration,
            "final_score": result.final_score,
            "final_percentage": result.final_percentage,
            "max_points": result.rubric.total_points,
            "criterion_scores": {
                cs.criterion_id: {
                    "points": cs.points_earned,
                    "max": cs.max_points,
                    "percentage": cs.percentage
                }
                for cs in last_criterion_scores
            },
            "dimension_scores": compute_dimension_scores(
                result.rubric.dimensions, last_criterion_scores
            ),
            "improvements": result.improvement_summary
        }, indent=2))
    else:
        print(f"\n{'='*60}")
        print("FINAL RESULT")
        print(f"{'='*60}")
        print(f"Success: {result.success}")
        print(f"Score: {result.final_score:.1f}/{result.rubric.total_points} ({result.final_percentage:.1%})")
        print(f"Iterations: {result.iterations}")

        if result.improvement_summary:
            print(f"\nRemaining improvements:")
            for imp in result.improvement_summary[:5]:
                print(f"  - {imp}")

        if result.success:
            print(f"\n{'─'*60}")
            print("OUTPUT:")
            print(f"{'─'*60}")
            print(result.output[:2000] + "..." if len(result.output) > 2000 else result.output)

    sys.exit(0 if result.success else 1)


if __name__ == "__main__":
    asyncio.run(main())
