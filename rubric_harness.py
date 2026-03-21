#!/usr/bin/env python3
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
    ScoredRubricRecord,
)

try:
    from anthropic import Anthropic
except ImportError:
    Anthropic = None

from rubric_system.rubric_learning import RubricStore, RubricLearner
from rubric_system.self_improve import OutcomeTracker, LearningIntegrator, SelfEditor


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

MEASUREMENT_PROMPT = """Analyze this content and extract precise measurements for scoring.

CONTENT:
```
{content}
```

CRITERIA TO MEASURE:
{criteria_specs}

For each criterion and sub-attribute, count actual instances and calculate percentages.

OUTPUT FORMAT (JSON):
{{
  "criterion_id": {{
    "sub_attribute_id": <float 0.0-1.0>,
    "sub_attribute_id_evidence": "specific count or observation",
    "violations": ["list", "of", "violations"]  // for penalty-based criteria
  }}
}}

MEASUREMENT RULES:
1. SOURCE FRESHNESS:
   - Identify all sources cited
   - For each, check publication date vs domain threshold
   - headline_citation_freshness = (fresh Tier1 sources) / (total Tier1 sources)
   - Tier 1 = sources for headline claims, key statistics, thesis
   - Tier 2-3 = supporting, background sources

2. SOURCE AUTHORITY:
   - primary_source_authority = (peer-reviewed + official + expert) / (total for key claims)
   - expert_credentials = (experts with stated credentials) / (total experts quoted)

3. TRIANGULATION:
   - tier1_triangulation = (Tier1 claims with 3+ sources) / (total Tier1 claims)
   - tier2_triangulation = (Tier2 claims with 2+ sources) / (total Tier2 claims)

4. EVIDENCE ALIGNMENT (penalty-based):
   - List violations found: unsupported_headline_claim, weak_evidence_strong_claim, etc.

5. VISUALIZATION:
   - Count charts, check each for violations
   - violations list for accuracy; percentages for clarity sub-attributes

6. UNCERTAINTY:
   - prediction_labeling = (labeled predictions) / (total forward statements)
   - uncertainty_ranges = (predictions with ranges) / (quantitative predictions)

Be thorough. Count everything. Output ONLY valid JSON."""


def format_criteria_for_measurement(criteria: list[Criterion]) -> str:
    lines = []
    for c in criteria:
        lines.append(f"\n=== {c.id} ({c.scoring.method.value}) ===")
        lines.append(f"Description: {c.description}")

        if c.scoring.sub_attributes:
            lines.append("Measure these sub-attributes (each 0.0-1.0):")
            for sub in c.scoring.sub_attributes:
                lines.append(f"  - {sub.sub_id}: {sub.measurement}")

        if c.scoring.penalties:
            lines.append("Check for these violations:")
            for v, p in c.scoring.penalties.items():
                lines.append(f"  - {v} (penalty: {p})")

    return "\n".join(lines)


# ============================================================================
# Generation Prompt with Granular Feedback
# ============================================================================

GENERATION_PROMPT = """Create content for this task, optimizing for the rubric scores.

TASK: {task}

RUBRIC CRITERIA (optimize for these):
{rubric_summary}

{history_section}

{focus_section}

For each criterion, aim for the PASS patterns and avoid FAIL patterns.
Pay special attention to sub-attributes with low scores - these are your biggest point opportunities.

Output complete, high-quality content."""


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
            lines.append(f"     Evidence: {ss.evidence[:60]}...")

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


# ============================================================================
# Rubric Generator — builds bespoke rubrics for any task via LLM
# ============================================================================

RUBRIC_GENERATION_PROMPT = """You are a rubric architect. Given a task, produce a scoring rubric that a verifier can use to evaluate the output.

TASK:
{task}

{context_section}

INSTRUCTIONS:
1. Analyze the task and identify 4-7 evaluation criteria. Each criterion must be:
   - Specific to THIS task (not generic quality platitudes)
   - Measurable (a verifier can score it without subjectivity)
   - Ordered by importance (most critical first)

2. For each criterion, choose the best scoring method:
   - "weighted_components": When quality is a composite of measurable sub-dimensions. Use for criteria where multiple aspects contribute (e.g., "source quality" = freshness + authority + triangulation). Each sub-attribute gets a weight (must sum to 1.0) and a measurement description.
   - "penalty_based": When you start perfect and deduct for violations. Use for criteria where specific anti-patterns exist (e.g., code safety = 10pts minus deductions for hardcoded secrets, missing error handling, etc.). Define each violation and its penalty (negative float).
   - "binary": When it either passes or fails with no gradient. Use sparingly — only for structural requirements (e.g., "exactly 3 bullets", "includes a return type").

3. Assign max_points reflecting importance: critical criteria get 10-12, important get 8, standard get 4-6.

4. Set pass_threshold between 0.75-0.90 based on task type:
   - Creative/subjective tasks: 0.75-0.80
   - Technical/precision tasks: 0.85-0.90

{examples_section}

OUTPUT FORMAT — valid JSON only, no markdown fences:
{{
  "domain": "<short domain label for this task type>",
  "pass_threshold": <float>,
  "criteria": [
    {{
      "id": "<short_snake_case>",
      "category": "<category>",
      "description": "<what this criterion evaluates>",
      "pass_condition": "<specific conditions for passing>",
      "scoring_method": "weighted_components|penalty_based|binary",
      "max_points": <int>,
      "sub_attributes": [
        {{
          "sub_id": "<snake_case>",
          "description": "<what this measures>",
          "weight": <float 0.0-1.0>,
          "measurement": "<how to measure, produce a float 0.0-1.0>"
        }}
      ],
      "penalties": {{
        "<violation_name>": <negative_float>,
        ...
      }},
      "pass_examples": ["<example of passing>"],
      "fail_examples": ["<example of failing>"]
    }}
  ]
}}

RULES:
- sub_attributes only for weighted_components (weights must sum to 1.0)
- penalties only for penalty_based
- Neither for binary
- Every criterion needs pass_examples and fail_examples (1-2 each)
- Be specific: "function handles edge cases" is bad. "Function handles empty input, mixed quoting, and trailing delimiters without crash" is good.
- Criteria should be evaluatable from the output alone — don't require external validation
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


class RubricGenerator:
    """Generates bespoke rubrics for any task by calling Claude.

    The generator uses few-shot examples from pre-built rubrics to teach
    the model what good criteria look like, then produces a task-specific
    rubric configuration that gets hydrated into canonical Criterion objects.

    Before generating, it performs deep research using web search to understand
    what domain experts consider best practices for the task type. This ensures
    rubrics capture real-world quality standards, not just LLM intuitions.

    Usage:
        gen = RubricGenerator()
        rubric = gen.generate("Write a cold email to a VC partner")

        # Or with the RubricLoop:
        loop = RubricLoop()
        result = await loop.run("any task here")  # auto-generates rubric
    """

    def __init__(self, model: str = "claude-sonnet-4-20250514", verbose: bool = True,
                 learning_integrator: LearningIntegrator = None,
                 enable_research: bool = True,
                 research_model: str = "claude-sonnet-4-20250514"):
        if Anthropic is None:
            raise ImportError("anthropic package required: pip install anthropic")
        self.client = Anthropic()
        self.model = model
        self.verbose = verbose
        self.learning_integrator = learning_integrator
        self.enable_research = enable_research
        self.auto_improve_interval = auto_improve_interval
        self.auto_improve_min_uses = auto_improve_min_uses
        self.auto_improve_max_edits = auto_improve_max_edits
        self.research_model = research_model

    def _log(self, msg: str):
        if self.verbose:
            print(msg)

    def _research_best_practices(self, task: str) -> str:
        """Deep research step: use web search to find what domain experts consider
        best practices and quality standards for this task type.

        Uses Claude with the web_search tool to ground rubric generation in
        real-world expert standards rather than LLM intuitions.

        Returns:
            Formatted research brief to inject into the generation prompt.
        """
        self._log("Researching best practices for task domain...")

        prompt = RESEARCH_PROMPT.format(task=task)

        try:
            response = self.client.messages.create(
                model=self.research_model,
                max_tokens=4000,
                tools=[{
                    "type": "web_search_20250305",
                    "name": "web_search",
                    "max_uses": 5,
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

        # Step 1: Deep research — what do domain experts consider best practices?
        research_section = ""
        if self.enable_research:
            research_section = self._research_best_practices(task)

        # Step 2: Inject learning context from prior evaluations
        learning_section = ""
        if self.learning_integrator:
            try:
                learning_section = self.learning_integrator.build_learning_context(task)
                if learning_section:
                    self._log(f"Injected learning context ({len(learning_section)} chars)")
            except Exception as e:
                self._log(f"Learning context unavailable: {e}")

        prompt = RUBRIC_GENERATION_PROMPT.format(
            task=task,
            context_section=context_section,
            examples_section=examples_section,
        )
        # Append research + learnings after the base prompt so the rubric architect
        # has full domain context before generating criteria
        if research_section:
            prompt += "\n" + research_section
        if learning_section:
            prompt += "\n" + learning_section

        response = self.client.messages.create(
            model=self.model,
            max_tokens=4000,
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
# Main Harness
# ============================================================================

class RubricLoop:
    def __init__(
        self,
        model: str = "claude-sonnet-4-20250514",
        max_iterations: int = 5,
        pass_threshold: float = 0.85,
        verbose: bool = True,
        feedback_dir: str = ".rubric_feedback",
        enable_checkpoints: bool = True,
        checkpoint_callback: callable = None,
        repo_path: str = ".",
        enable_self_improve: bool = True,
        enable_research: bool = True,
        auto_improve_interval: int = 10,
        auto_improve_min_uses: int = 20,
        auto_improve_max_edits: int = 2,
    ):
        if Anthropic is None:
            raise ImportError("anthropic package is required: pip install anthropic")
        self.client = Anthropic()
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
        self.rubric_store = RubricStore()
        self.outcome_tracker = OutcomeTracker(self.rubric_store, verbose=verbose)
        self.learning_integrator = LearningIntegrator(
            store=self.rubric_store,
            feedback_store=self.feedback_store,
            verbose=verbose,
        )
        self.enable_research = enable_research

    def _log(self, msg: str):
        if self.verbose:
            print(msg)

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
        """Use LLM to extract granular measurements from content, with scoring feedback."""
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

        # Inject scoring calibration feedback
        criteria_ids = [c.id for c in rubric.criteria]
        scoring_feedback = self.feedback_injector.format_for_scoring_prompt(
            domain=rubric.domain, criteria_ids=criteria_ids
        )
        if scoring_feedback:
            prompt += "\n" + scoring_feedback

        self._log("Extracting measurements...")
        response = self._call_claude(prompt, max_tokens=4000)
        return self._extract_json(response)

    async def score_content(self, content: str, rubric: Rubric) -> tuple[float, int, list[CriterionScore]]:
        """Score content against rubric with granular measurements."""
        measurements = await self.extract_measurements(content, rubric)

        criterion_scores = []
        for criterion in rubric.criteria:
            crit_measurements = measurements.get(criterion.id, {})
            violations = crit_measurements.pop("violations", []) if isinstance(crit_measurements, dict) else []
            score = self.engine.score_criterion(criterion, crit_measurements, violations)
            criterion_scores.append(score)

        total = sum(cs.points_earned for cs in criterion_scores)
        max_total = sum(cs.max_points for cs in criterion_scores)

        return total, max_total, criterion_scores

    def _get_focus_areas(self, criterion_scores: list[CriterionScore]) -> list[tuple[str, str, float]]:
        """Identify sub-attributes with biggest improvement potential."""
        focus = []

        for cs in criterion_scores:
            for ss in cs.sub_scores:
                if ss.raw_value < 0.8:
                    focus.append((cs.criterion_id, ss.sub_id, ss.raw_value))

        for cs in criterion_scores:
            for p in cs.penalties_applied:
                focus.append((cs.criterion_id, p["violation"], 0.0))

        focus.sort(key=lambda x: x[2])
        return focus[:5]

    async def generate_content(
        self,
        rubric: Rubric,
        history: list[Iteration],
        focus_areas: list[tuple[str, str, float]]
    ) -> str:
        """Generate content optimized for rubric scores, with feedback injection."""
        rubric_summary = format_rubric_for_generation(rubric)
        history_section = format_history_for_generation(history)
        focus_section = format_focus_for_generation(focus_areas)

        # Inject learned feedback into generation prompt
        criteria_ids = [c.id for c in rubric.criteria]
        feedback_section = self.feedback_injector.format_for_generation_prompt(
            task=rubric.task, domain=rubric.domain, criteria_ids=criteria_ids
        )

        prompt = GENERATION_PROMPT.format(
            task=rubric.task,
            rubric_summary=rubric_summary,
            history_section=history_section,
            focus_section=focus_section
        )
        if feedback_section:
            prompt += "\n" + feedback_section

        self._log("Generating content...")
        return self._call_claude(prompt, max_tokens=12000)

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
        rubric: Rubric = None,
        rubric_name: str = None,
        generate_rubric: bool = True,
    ) -> LoopResult:
        """Run the generation-verification loop with granular scoring,
        feedback injection, verification tracking, and checkpoints.

        Rubric resolution order:
        1. Explicit rubric object (rubric=...)
        2. Explicit registry name (rubric_name=...)
        3. Generate bespoke rubric via LLM (default when generate_rubric=True)
        4. Fall back to registry matching (when generate_rubric=False)

        Args:
            task: task description
            context: optional context (file content, etc.)
            rubric: explicit Rubric object — bypasses all resolution
            rubric_name: explicit registry name — looks up by name
            generate_rubric: if True (default), generates a bespoke rubric via LLM
                             when no explicit rubric/name is provided
        """
        self._log(f"\n{'='*60}")
        self._log(f"Task: {task[:60]}...")
        self._log(f"{'='*60}")

        # Rubric resolution
        if rubric is not None:
            matched_name = "explicit"
            self._log(f"Rubric: explicit ({len(rubric.criteria)} criteria, {rubric.total_points}pts)")
        elif rubric_name is not None:
            rubric, matched_name, _ = resolve_rubric(task, rubric_name=rubric_name)
            self._log(f"Rubric: {matched_name} (registry lookup)")
            self._log(f"  {len(rubric.criteria)} criteria, {rubric.total_points} max points")
        elif generate_rubric:
            # Primary path: generate bespoke rubric (with research + learning context)
            generator = RubricGenerator(
                model=self.model, verbose=self.verbose,
                learning_integrator=self.learning_integrator if self.enable_self_improve else None,
                enable_research=self.enable_research,
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

        domain = rubric.domain

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

        history = []

        for i in range(1, self.max_iterations + 1):
            self._log(f"\n{'─'*50}")
            self._log(f"Iteration {i}/{self.max_iterations}")

            focus_areas = []
            if history:
                focus_areas = self._get_focus_areas(history[-1].criterion_scores)
                if focus_areas:
                    self._log(f"Focus: {focus_areas[0][0]}.{focus_areas[0][1]} ({focus_areas[0][2]:.0%})")

            content = await self.generate_content(rubric, history, focus_areas)

            # Track verification iteration
            self.tracker.start_iteration(i, [f"{f[0]}.{f[1]}" for f in focus_areas])

            total, max_total, criterion_scores = await self.score_content(content, rubric)
            percentage = total / max_total if max_total > 0 else 0

            # Record verification steps
            self.tracker.add_steps_from_criterion_scores(criterion_scores)
            self.tracker.complete_iteration(total, max_total)

            self._log(f"\nScore: {total:.1f}/{max_total} ({percentage:.1%})")
            for cs in criterion_scores:
                emoji = "PASS" if cs.percentage >= 0.8 else "WARN" if cs.percentage >= 0.5 else "FAIL"
                self._log(f"   [{emoji}] {cs.criterion_id}: {cs.points_earned:.1f}/{cs.max_points} ({cs.percentage:.0%})")
                if cs.percentage < 0.8 and cs.sub_scores:
                    for ss in cs.sub_scores:
                        if ss.raw_value < 0.8:
                            self._log(f"      - {ss.sub_id}: {ss.raw_value:.0%}")

            history.append(Iteration(
                number=i,
                attempt=content,
                total_score=total,
                max_score=max_total,
                percentage=percentage,
                criterion_scores=criterion_scores,
                focus_areas=[f"{f[0]}.{f[1]}" for f in focus_areas]
            ))

            if percentage >= self.pass_threshold:
                self._log(f"\nPASSED at iteration {i}! ({percentage:.1%})")
                self.tracker.complete()
                result = LoopResult(
                    success=True,
                    output=content,
                    iterations=i,
                    final_score=total,
                    final_percentage=percentage,
                    rubric=rubric,
                    history=history
                )
                self._post_run(result)
                return result

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
                        return LoopResult(
                            success=False,
                            output=content,
                            iterations=i,
                            final_score=total,
                            final_percentage=percentage,
                            rubric=rubric,
                            history=history,
                            improvement_summary=[f"Stopped at {checkpoint.checkpoint_type} checkpoint"]
                        )

        self._log(f"\nMax iterations reached. Final: {percentage:.1%}")
        self.tracker.complete()

        final_scores = history[-1].criterion_scores
        improvements = []
        for cs in sorted(final_scores, key=lambda x: x.percentage):
            if cs.percentage < 0.8:
                gap = cs.max_points - cs.points_earned
                improvements.append(f"{cs.criterion_id}: +{gap:.1f} pts available")

        result = LoopResult(
            success=False,
            output=history[-1].attempt,
            iterations=self.max_iterations,
            final_score=history[-1].total_score,
            final_percentage=history[-1].percentage,
            rubric=rubric,
            history=history,
            improvement_summary=improvements
        )
        self._post_run(result)
        return result

    def _post_run(self, result: LoopResult):
        """Post-run hook: persist scored rubric, scan outcomes, improve generation, auto-edit."""
        if not self.enable_self_improve:
            return

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
                     "max_points": cs.max_points, "percentage": cs.percentage}
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

            # Scan for outcome signals from prior runs
            signals = self.outcome_tracker.scan_git_outcomes(
                repo_path=self.repo_path, lookback_days=14
            )
            if signals:
                self._log(f"[Loop3] Detected {len(signals)} outcome signals from git")

        except Exception as e:
            self._log(f"[Loop3] Post-run hook error (non-fatal): {e}")

        # Analyze rubric generation quality and store improvement signals
        self._post_run_improve_generation(result)

        # Auto self-improvement: propose and apply code edits when enough data
        if self._should_auto_improve():
            self._run_auto_improve()

    def _post_run_improve_generation(self, result: LoopResult):
        """Analyze rubric generation quality and log improvement signals.

        Detects non-discriminating criteria (always pass) and stuck criteria
        (never improve), writes them as feedback so LearningIntegrator picks
        them up on the next rubric generation.
        """
        if not result.history:
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
        - At least 10 scored rubrics exist in the store
        - At least one criterion has enough uses (auto_improve_min_uses)
        """
        try:
            from rubric_system.rubric_learning import RubricLearner
            learner = RubricLearner(self.rubric_store)
            insights = learner.get_insights()

            total_evals = insights.get("total_evaluations", 0)
            if total_evals < 10:
                return False

            # Only trigger every Nth run
            if total_evals % self.auto_improve_interval != 0:
                return False

            # At least one criterion needs enough data points
            all_stats = insights.get("all_criteria_stats", [])
            has_enough_data = any(
                s.get("times_used", 0) >= self.auto_improve_min_uses
                for s in all_stats
            ) if all_stats else False

            return has_enough_data
        except Exception:
            return False

    def _run_auto_improve(self):
        """Execute automatic self-improvement: propose and apply code edits."""
        self._log("[Loop3] Auto self-improvement triggered")
        try:
            editor = SelfEditor(
                store=self.rubric_store,
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
    parser.add_argument("--context", "-c", help="Context file or text")
    parser.add_argument("--rubric", "-r", help="Explicit rubric name (see --list-rubrics)")
    parser.add_argument("--no-generate", action="store_true",
                        help="Disable rubric generation; use registry matching instead")
    parser.add_argument("--list-rubrics", action="store_true", help="List all registered rubrics")
    parser.add_argument("--explain", action="store_true", help="Show rubric resolution explanation")
    parser.add_argument("--max-iter", "-m", type=int, default=5)
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
        p = Path(args.context)
        context = p.read_text() if p.exists() else args.context

    loop = RubricLoop(
        max_iterations=args.max_iter,
        pass_threshold=args.threshold,
        verbose=not args.quiet,
        enable_self_improve=not args.no_learn,
        enable_research=not args.no_research,
        auto_improve_interval=0 if args.no_auto_improve else 10,
    )

    result = await loop.run(
        args.task, context,
        rubric_name=args.rubric,
        generate_rubric=not args.no_generate,
    )

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
        print(json.dumps({
            "success": result.success,
            "iterations": result.iterations,
            "final_score": result.final_score,
            "final_percentage": result.final_percentage,
            "max_points": result.rubric.total_points,
            "criterion_scores": {
                cs.criterion_id: {
                    "points": cs.points_earned,
                    "max": cs.max_points,
                    "percentage": cs.percentage
                }
                for cs in result.history[-1].criterion_scores
            },
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
