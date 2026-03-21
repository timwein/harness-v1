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
)

try:
    from anthropic import Anthropic
except ImportError:
    Anthropic = None


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
# Domain Detection
# ============================================================================

DOMAIN_PATTERNS = {
    "knowledge_work_research": [
        r"\b(research|report|analysis|whitepaper|brief)\b",
        r"\b(document|write|draft|study|paper)\b",
        r"\b(source|citation|evidence|data)\b",
    ],
    "api_rest_endpoint": [
        r"\b(endpoint|api|route|REST|GET|POST)\b",
        r"\b(express|fastapi|flask|router)\b",
    ],
    "frontend_design": [
        r"\b(design|ui|ux|frontend|landing)\b",
        r"\b(css|tailwind|component|layout)\b",
    ],
}


def detect_domain(task: str) -> tuple[str, float]:
    task_lower = task.lower()
    scores = {}
    for domain, patterns in DOMAIN_PATTERNS.items():
        score = sum(len(re.findall(p, task_lower, re.I)) for p in patterns)
        if score > 0:
            scores[domain] = score
    if not scores:
        return ("generic", 0.0)
    best = max(scores, key=scores.get)
    return (best, min(scores[best] / 4.0, 1.0))


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

    async def run(self, task: str, context: str = "") -> LoopResult:
        """Run the generation-verification loop with granular scoring,
        feedback injection, verification tracking, and checkpoints."""
        self._log(f"\n{'='*60}")
        self._log(f"Task: {task[:60]}...")
        self._log(f"{'='*60}")

        domain, confidence = detect_domain(task)
        self._log(f"Domain: {domain} ({confidence:.0%})")

        if domain == "knowledge_work_research":
            rubric = build_knowledge_work_rubric(task)
        elif domain == "frontend_design":
            rubric = build_frontend_design_rubric(task)
        else:
            rubric = build_knowledge_work_rubric(task)  # Default fallback

        self._log(f"Rubric: {len(rubric.criteria)} criteria, {rubric.total_points} max points")

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
                return LoopResult(
                    success=True,
                    output=content,
                    iterations=i,
                    final_score=total,
                    final_percentage=percentage,
                    rubric=rubric,
                    history=history
                )

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

        return LoopResult(
            success=False,
            output=history[-1].attempt,
            iterations=self.max_iterations,
            final_score=history[-1].total_score,
            final_percentage=history[-1].percentage,
            rubric=rubric,
            history=history,
            improvement_summary=improvements
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
# CLI
# ============================================================================

async def main():
    import argparse

    parser = argparse.ArgumentParser(description="Rubric Loop - Granular Scoring")
    parser.add_argument("task", nargs="?", help="Task description")
    parser.add_argument("--context", "-c", help="Context file or text")
    parser.add_argument("--max-iter", "-m", type=int, default=5)
    parser.add_argument("--threshold", "-t", type=float, default=0.85)
    parser.add_argument("--quiet", "-q", action="store_true")
    parser.add_argument("--json", "-j", action="store_true")

    args = parser.parse_args()

    if not args.task:
        args.task = "Write a research brief on the AI chip market in 2025, including market size, key players, and 2-year forecast"

    context = ""
    if args.context:
        p = Path(args.context)
        context = p.read_text() if p.exists() else args.context

    loop = RubricLoop(
        max_iterations=args.max_iter,
        pass_threshold=args.threshold,
        verbose=not args.quiet
    )

    result = await loop.run(args.task, context)

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
