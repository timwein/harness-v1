#!/usr/bin/env python3
"""
Rubric Scoring Engine - Granular Point-Based Scoring

Standalone scoring engine that can be used independently of the harness.
All data models are imported from models.py (single source of truth).

Key features:
1. Each criterion has max_points (not just weight 1-3)
2. Scoring is continuous (0 to max_points), not binary
3. Multiple scoring methods: binary, percentage, weighted components, penalties, tiers, count-based
4. Sub-attributes within criteria for fine-grained measurement
5. Weighted penalties for severity

Example: Source Freshness (max 10 points)
- 100 sources total, 80 fresh (80%)
- But 5 of 10 headline citations are stale (50% of critical citations)
- Score = 10 * (0.3 * 0.80 + 0.7 * 0.50) = 10 * 0.59 = 5.9/10
"""

import json
import re
from typing import Optional, Callable

from rubric_system.models import (
    ScoringMethod,
    SubAttribute,
    ScoringRubric,
    SubScore,
    CriterionScore,
    Criterion,
    DocumentScore,
    RubricDimension,
)


# ============================================================================
# Pre-built Scoring Rubrics for Common Criteria
# ============================================================================

def source_freshness_rubric(max_points: int = 10) -> ScoringRubric:
    """Scoring rubric for source freshness/currency."""
    return ScoringRubric(
        method=ScoringMethod.WEIGHTED_COMPONENTS,
        max_points=max_points,
        sub_attributes=[
            SubAttribute(
                sub_id="headline_citation_freshness",
                description="Freshness of sources cited for key claims (Tier 1)",
                weight=0.50,
                measurement="% of Tier 1 cited sources within currency threshold",
                thresholds={"excellent": 1.0, "good": 0.9, "acceptable": 0.75, "poor": 0.5}
            ),
            SubAttribute(
                sub_id="supporting_citation_freshness",
                description="Freshness of sources cited for supporting claims (Tier 2-3)",
                weight=0.30,
                measurement="% of Tier 2-3 cited sources within currency threshold",
                thresholds={"excellent": 0.95, "good": 0.85, "acceptable": 0.7, "poor": 0.5}
            ),
            SubAttribute(
                sub_id="overall_source_freshness",
                description="Freshness of all sources in bibliography",
                weight=0.20,
                measurement="% of all sources within appropriate currency threshold",
                thresholds={"excellent": 0.9, "good": 0.8, "acceptable": 0.6, "poor": 0.4}
            ),
        ]
    )


def source_authority_rubric(max_points: int = 10) -> ScoringRubric:
    """Scoring rubric for source authority/credibility."""
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
                measurement="% of sources from established institutions vs blogs/forums"
            ),
        ]
    )


def source_triangulation_rubric(max_points: int = 10) -> ScoringRubric:
    """Scoring rubric for source triangulation."""
    return ScoringRubric(
        method=ScoringMethod.WEIGHTED_COMPONENTS,
        max_points=max_points,
        sub_attributes=[
            SubAttribute(
                sub_id="tier1_triangulation",
                description="Headline claims have 3+ independent sources",
                weight=0.50,
                measurement="% of Tier 1 claims with 3+ sources"
            ),
            SubAttribute(
                sub_id="tier2_triangulation",
                description="Supporting claims have 2+ independent sources",
                weight=0.30,
                measurement="% of Tier 2 claims with 2+ sources"
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
    """Scoring rubric for claim-evidence alignment."""
    return ScoringRubric(
        method=ScoringMethod.PENALTY_BASED,
        max_points=max_points,
        penalties={
            "unsupported_headline_claim": -3.0,
            "unsupported_supporting_claim": -1.5,
            "weak_evidence_for_strong_claim": -2.0,
            "citation_drift": -1.0,
            "missing_quantitative_backing": -1.0,
        }
    )


def visualization_accuracy_rubric(max_points: int = 10) -> ScoringRubric:
    """Scoring rubric for data visualization accuracy."""
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
            "chartjunk": -0.5,
        }
    )


def uncertainty_quantification_rubric(max_points: int = 10) -> ScoringRubric:
    """Scoring rubric for forward-looking statement uncertainty."""
    return ScoringRubric(
        method=ScoringMethod.WEIGHTED_COMPONENTS,
        max_points=max_points,
        sub_attributes=[
            SubAttribute(
                sub_id="prediction_labeling",
                description="Predictions clearly labeled as such",
                weight=0.30,
                measurement="% of forward-looking statements with explicit labels"
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
                weight=0.25,
                measurement="% of quantitative predictions with ranges"
            ),
            SubAttribute(
                sub_id="assumption_transparency",
                description="Key assumptions stated",
                weight=0.20,
                measurement="% of predictions with explicit assumptions"
            ),
        ]
    )


# ============================================================================
# Scoring Engine
# ============================================================================

class ScoringEngine:
    """
    Calculates granular scores for criteria based on extracted measurements.

    This is the same engine used by the canonical RubricLoop in rubric_harness.py,
    exposed here for standalone usage (e.g., scoring without the full loop).
    """

    def score_criterion(
        self,
        criterion: Criterion,
        measurements: dict,
        violations: list[str] = None,
    ) -> CriterionScore:
        scoring = criterion.scoring

        # Guard against empty measurements — when JSON parsing fails, weighted_components
        # silently defaults to 0% while penalty_based defaults to 100%. Both should
        # return a midpoint estimate to avoid asymmetric scoring artifacts.
        if not measurements and not violations:
            midpoint = scoring.max_points * 0.5
            return CriterionScore(
                criterion_id=criterion.id,
                points_earned=round(midpoint, 2),
                max_points=scoring.max_points,
                percentage=0.5,
                evidence="WARNING: No measurements extracted — score is a 50% fallback estimate",
                methodology="Fallback: no measurements available, defaulting to 50%",
            )

        if scoring.method == ScoringMethod.BINARY:
            return self._score_binary(criterion, measurements)
        elif scoring.method == ScoringMethod.PERCENTAGE:
            return self._score_percentage(criterion, measurements)
        elif scoring.method == ScoringMethod.WEIGHTED_COMPONENTS:
            return self._score_weighted_components(criterion, measurements)
        elif scoring.method == ScoringMethod.PENALTY_BASED:
            return self._score_penalty_based(criterion, violations or [])
        elif scoring.method == ScoringMethod.THRESHOLD_TIERS:
            return self._score_threshold_tiers(criterion, measurements)
        elif scoring.method == ScoringMethod.COUNT_BASED:
            return self._score_count_based(criterion, measurements)
        else:
            raise ValueError(f"Unknown scoring method: {scoring.method}")

    def _score_binary(self, criterion: Criterion, measurements: dict) -> CriterionScore:
        passed = measurements.get("passed", False)
        points = criterion.scoring.max_points if passed else 0
        return CriterionScore(
            criterion_id=criterion.id,
            points_earned=points,
            max_points=criterion.scoring.max_points,
            percentage=1.0 if passed else 0.0,
            evidence=measurements.get("evidence", ""),
            methodology="Binary: full points if pass, zero if fail"
        )

    def _score_percentage(self, criterion: Criterion, measurements: dict) -> CriterionScore:
        pct = measurements.get("percentage", 0.0)
        points = criterion.scoring.max_points * pct
        return CriterionScore(
            criterion_id=criterion.id,
            points_earned=points,
            max_points=criterion.scoring.max_points,
            percentage=pct,
            evidence=measurements.get("evidence", ""),
            methodology=f"Percentage: {pct:.1%} of max points"
        )

    def _score_weighted_components(self, criterion: Criterion, measurements: dict) -> CriterionScore:
        sub_scores = []
        total_weighted = 0.0
        methodology_parts = []

        for sub_attr in criterion.scoring.sub_attributes:
            raw_value = measurements.get(sub_attr.sub_id, 0.0)
            raw_value = max(0.0, min(1.0, raw_value))
            weighted_value = raw_value * sub_attr.weight
            total_weighted += weighted_value

            sub_scores.append(SubScore(
                sub_id=sub_attr.sub_id,
                raw_value=raw_value,
                weighted_value=weighted_value,
                evidence=measurements.get(f"{sub_attr.sub_id}_evidence", ""),
                details={
                    "description": sub_attr.description,
                    "weight": sub_attr.weight,
                    "measurement": sub_attr.measurement,
                }
            ))
            methodology_parts.append(f"{sub_attr.sub_id}: {raw_value:.1%} x {sub_attr.weight:.0%}")

        points = criterion.scoring.max_points * total_weighted

        hints = []
        for ss in sorted(sub_scores, key=lambda x: x.raw_value):
            if ss.raw_value < 0.8:
                hints.append(f"Improve {ss.sub_id}: currently {ss.raw_value:.0%}, target >=80%")

        return CriterionScore(
            criterion_id=criterion.id,
            points_earned=round(points, 2),
            max_points=criterion.scoring.max_points,
            percentage=total_weighted,
            sub_scores=sub_scores,
            evidence=measurements.get("evidence", ""),
            methodology=f"Weighted components: {' + '.join(methodology_parts)} = {total_weighted:.1%}",
            improvement_hints=hints[:3]
        )

    def _score_penalty_based(self, criterion: Criterion, violations: list[str]) -> CriterionScore:
        points = float(criterion.scoring.max_points)
        penalties_applied = []

        for violation in violations:
            penalty = criterion.scoring.penalties.get(violation, 0)
            if penalty:
                points += penalty
                penalties_applied.append({
                    "violation": violation,
                    "penalty": penalty,
                    "remaining": max(0, points)
                })

        points = max(0, points)

        hints = [f"Fix {p['violation']} (+{abs(p['penalty'])} points)"
                 for p in sorted(penalties_applied, key=lambda x: x['penalty'])]

        return CriterionScore(
            criterion_id=criterion.id,
            points_earned=round(points, 2),
            max_points=criterion.scoring.max_points,
            percentage=points / criterion.scoring.max_points,
            penalties_applied=penalties_applied,
            methodology=f"Penalty-based: {criterion.scoring.max_points} - {sum(p['penalty'] for p in penalties_applied):.1f} = {points:.1f}",
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

    def _score_count_based(self, criterion: Criterion, measurements: dict) -> CriterionScore:
        count = measurements.get("count", 0)
        points = min(
            count * criterion.scoring.points_per_instance,
            criterion.scoring.max_points
        )
        return CriterionScore(
            criterion_id=criterion.id,
            points_earned=round(points, 2),
            max_points=criterion.scoring.max_points,
            percentage=points / criterion.scoring.max_points if criterion.scoring.max_points > 0 else 0,
            evidence=measurements.get("evidence", ""),
            methodology=f"Count-based: {count} x {criterion.scoring.points_per_instance} = {points}"
        )


# ============================================================================
# Dimension Score Computation
# ============================================================================

def compute_dimension_scores(
    dimensions: Optional[list],
    criterion_scores: list,
) -> list[dict]:
    """Compute per-dimension scores from already-computed criterion scores.

    Dimension score = sum of points earned by its criteria / sum of their max_points.
    This is equivalent to a max_points-weighted average of criterion percentages.

    Args:
        dimensions: list of RubricDimension objects, or None for flat rubrics
        criterion_scores: list of CriterionScore objects

    Returns:
        list of dicts: {dimension_id, dimension_name, score, max_score,
                        percentage, criteria_count}
        Empty list if dimensions is None or empty.
    """
    if not dimensions:
        return []

    score_by_id = {cs.criterion_id: cs for cs in criterion_scores}
    results = []

    for dim in dimensions:
        dim_criteria = [score_by_id[cid] for cid in dim.criteria_ids if cid in score_by_id]

        if not dim_criteria:
            results.append({
                "dimension_id": dim.id,
                "dimension_name": dim.name,
                "score": 0.0,
                "max_score": 0,
                "percentage": 0.0,
                "criteria_count": 0,
            })
            continue

        dim_score = sum(cs.points_earned for cs in dim_criteria)
        dim_max = sum(cs.max_points for cs in dim_criteria)
        dim_pct = dim_score / dim_max if dim_max > 0 else 0.0

        results.append({
            "dimension_id": dim.id,
            "dimension_name": dim.name,
            "score": round(dim_score, 2),
            "max_score": dim_max,
            "percentage": round(dim_pct, 4),
            "criteria_count": len(dim_criteria),
        })

    return results


# ============================================================================
# Measurement Extraction (LLM-based)
# ============================================================================

MEASUREMENT_EXTRACTION_PROMPT = """Analyze this content and extract measurements for scoring.

CONTENT TO ANALYZE:
{content}

CRITERIA TO MEASURE:
{criteria_specs}

For each criterion, extract the required measurements. Be precise and count actual instances.

Output as JSON:
{{
  "criterion_id": {{
    "sub_attribute_id": <float 0.0-1.0 or count>,
    "sub_attribute_id_evidence": "specific evidence from content",
    ...
  }},
  ...
}}

MEASUREMENT RULES:
- Percentages: Count instances meeting criteria / total instances
- For source freshness: Check publication dates against thresholds
- For triangulation: Count independent sources per claim
- For penalties: List specific violations found

Be thorough and accurate. Count everything explicitly.
Output ONLY valid JSON."""


def format_criteria_for_measurement(criteria: list[Criterion]) -> str:
    """Format criteria specs for measurement extraction prompt."""
    lines = []
    for c in criteria:
        lines.append(f"\n=== {c.id} ===")
        lines.append(f"Description: {c.description}")
        lines.append(f"Scoring method: {c.scoring.method.value}")

        if c.scoring.sub_attributes:
            lines.append("Measurements needed:")
            for sub in c.scoring.sub_attributes:
                lines.append(f"  - {sub.sub_id}: {sub.measurement}")

        if c.scoring.penalties:
            lines.append("Check for violations:")
            for violation, penalty in c.scoring.penalties.items():
                lines.append(f"  - {violation} (penalty: {penalty})")

    return "\n".join(lines)


# ============================================================================
# Complete Scoring Pipeline
# ============================================================================

class DocumentScorer:
    """
    Scores a document against a full rubric.
    Can be used standalone without the generation loop.
    """

    def __init__(self, llm_client=None):
        self.engine = ScoringEngine()
        self.llm = llm_client

    async def score_document(
        self,
        content: str,
        criteria: list[Criterion],
        pass_threshold: float = 0.85,
        dimensions: Optional[list] = None,
    ) -> DocumentScore:
        measurements = await self._extract_measurements(content, criteria)

        criterion_scores = []
        for criterion in criteria:
            crit_measurements = measurements.get(criterion.id, {})
            violations = crit_measurements.pop("violations", []) if isinstance(crit_measurements, dict) else []
            score = self.engine.score_criterion(criterion, crit_measurements, violations)
            criterion_scores.append(score)

        total_points = sum(cs.points_earned for cs in criterion_scores)
        max_points = sum(cs.max_points for cs in criterion_scores)
        percentage = total_points / max_points if max_points > 0 else 0

        sorted_by_impact = sorted(
            criterion_scores,
            key=lambda cs: (cs.max_points - cs.points_earned),
            reverse=True
        )

        top_improvements = []
        for cs in sorted_by_impact[:5]:
            gap = cs.max_points - cs.points_earned
            if gap > 0:
                top_improvements.append(
                    f"{cs.criterion_id}: +{gap:.1f} points possible. {cs.improvement_hints[0] if cs.improvement_hints else ''}"
                )

        critical_failures = [
            f"{cs.criterion_id}: {cs.percentage:.0%}"
            for cs in criterion_scores
            if cs.percentage < 0.5
        ]

        return DocumentScore(
            total_points=round(total_points, 2),
            max_points=max_points,
            percentage=percentage,
            criterion_scores=criterion_scores,
            passed=percentage >= pass_threshold,
            pass_threshold=pass_threshold,
            top_improvements=top_improvements,
            critical_failures=critical_failures,
            dimension_scores=compute_dimension_scores(dimensions, criterion_scores),
        )

    async def _extract_measurements(
        self,
        content: str,
        criteria: list[Criterion]
    ) -> dict:
        if not self.llm:
            return {c.id: {"percentage": 0.75} for c in criteria}

        criteria_specs = format_criteria_for_measurement(criteria)
        prompt = MEASUREMENT_EXTRACTION_PROMPT.format(
            content=content[:60000],
            criteria_specs=criteria_specs
        )

        response = self.llm.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4000,
            messages=[{"role": "user", "content": prompt}]
        )

        text = response.content[0].text
        json_match = re.search(r'\{[\s\S]*\}', text)
        if json_match:
            return json.loads(json_match.group())

        return {}


# ============================================================================
# Example: Knowledge Work Document Scoring
# ============================================================================

def build_knowledge_work_rubric() -> list[Criterion]:
    """
    Build the full knowledge work rubric with granular scoring.

    NOTE: The canonical version of this function (which returns a Rubric object)
    is in rubric_harness.py as build_knowledge_work_rubric(task).
    This version returns a list[Criterion] for standalone scoring use.
    """
    criteria = [
        Criterion(
            id="src_freshness",
            category="source_quality",
            description="Sources are appropriately recent for the domain",
            pass_condition="Fast-changing domains <2y, medium <5y, slow context-appropriate",
            scoring=source_freshness_rubric(max_points=10),
            pass_examples=[
                "90% of cited sources within currency threshold",
                "All headline claims use sources <12 months old"
            ],
            fail_examples=[
                "Key market data from 3 years ago",
                "Cited 2019 study for current policy claim"
            ]
        ),
        Criterion(
            id="src_authority",
            category="source_quality",
            description="Sources from credible, authoritative entities",
            pass_condition="Peer-reviewed, official data, recognized experts",
            scoring=source_authority_rubric(max_points=10),
            pass_examples=[
                "Claims backed by Nature/Science papers",
                "Expert quotes include credentials"
            ],
            fail_examples=[
                "Key claim from anonymous blog",
                "Expert quoted without credentials"
            ]
        ),
        Criterion(
            id="src_triangulation",
            category="source_quality",
            description="Key claims validated by multiple independent sources",
            pass_condition="Tier1: 3+ sources, Tier2: 2+ sources, independent",
            scoring=source_triangulation_rubric(max_points=10),
            pass_examples=[
                "Market size claim backed by 3 analyst reports",
                "Sources don't cite each other"
            ],
            fail_examples=[
                "Headline statistic from single source",
                "All 3 'independent' sources cite same primary"
            ]
        ),
        Criterion(
            id="evd_alignment",
            category="evidence",
            description="Claims supported by appropriate evidence",
            pass_condition="No unsupported assertions, evidence matches claim strength",
            scoring=evidence_alignment_rubric(max_points=10),
            pass_examples=[
                "Each claim has citation",
                "Strong claims backed by RCTs/meta-analyses"
            ],
            fail_examples=[
                "'X causes Y' with only correlational data",
                "Statistics without source"
            ]
        ),
        Criterion(
            id="viz_accuracy",
            category="visualization",
            description="Visualizations accurately represent data",
            pass_condition="Proper axes, scales, chart types, no distortion",
            scoring=visualization_accuracy_rubric(max_points=10),
            pass_examples=[
                "Bar chart with zero baseline",
                "All axes labeled with units"
            ],
            fail_examples=[
                "Truncated Y-axis exaggerating differences",
                "Pie chart for trend data"
            ]
        ),
        Criterion(
            id="fwd_uncertainty",
            category="predictions",
            description="Predictions include appropriate uncertainty",
            pass_condition="Labeled as predictions, confidence levels, ranges provided",
            scoring=uncertainty_quantification_rubric(max_points=10),
            pass_examples=[
                "Forecast includes 90% CI",
                "Bull/base/bear scenarios provided"
            ],
            fail_examples=[
                "'Revenue will be $X' without range",
                "Predictions stated as facts"
            ]
        ),
    ]

    return criteria


# ============================================================================
# Demo
# ============================================================================

def demo():
    """Demonstrate granular scoring."""

    engine = ScoringEngine()

    # Example: Score source freshness
    criterion = Criterion(
        id="src_freshness",
        category="source_quality",
        description="Sources are appropriately recent",
        pass_condition="Sources within currency threshold",
        scoring=source_freshness_rubric(max_points=10)
    )

    measurements = {
        "headline_citation_freshness": 0.60,
        "headline_citation_freshness_evidence": "3 of 5 key claims cite sources >2 years old",
        "supporting_citation_freshness": 0.90,
        "supporting_citation_freshness_evidence": "18 of 20 supporting sources are current",
        "overall_source_freshness": 0.85,
        "overall_source_freshness_evidence": "85 of 100 sources within threshold",
    }

    score = engine.score_criterion(criterion, measurements)

    print("=" * 60)
    print("SOURCE FRESHNESS SCORING EXAMPLE")
    print("=" * 60)
    print(f"\nCriterion: {criterion.id}")
    print(f"Max Points: {score.max_points}")
    print(f"\nSub-scores:")
    for ss in score.sub_scores:
        print(f"  {ss.sub_id}:")
        print(f"    Raw value: {ss.raw_value:.0%}")
        print(f"    Weighted: {ss.weighted_value:.2f}")
        print(f"    Evidence: {ss.evidence}")

    print(f"\nMethodology: {score.methodology}")
    print(f"\nFINAL SCORE: {score.points_earned}/{score.max_points} ({score.percentage:.1%})")

    print(f"\nImprovement hints:")
    for hint in score.improvement_hints:
        print(f"  -> {hint}")

    # Example: Penalty-based scoring
    print("\n" + "=" * 60)
    print("VISUALIZATION ACCURACY SCORING EXAMPLE")
    print("=" * 60)

    viz_criterion = Criterion(
        id="viz_accuracy",
        category="visualization",
        description="Visualizations are accurate",
        pass_condition="No misleading elements",
        scoring=visualization_accuracy_rubric(max_points=10)
    )

    violations = ["truncated_axis", "missing_units", "chartjunk"]
    viz_score = engine.score_criterion(viz_criterion, {}, violations)

    print(f"\nViolations found: {violations}")
    print(f"\nPenalties applied:")
    for p in viz_score.penalties_applied:
        print(f"  {p['violation']}: {p['penalty']} points")

    print(f"\nMethodology: {viz_score.methodology}")
    print(f"\nFINAL SCORE: {viz_score.points_earned}/{viz_score.max_points} ({viz_score.percentage:.1%})")

    print(f"\nImprovement hints:")
    for hint in viz_score.improvement_hints:
        print(f"  -> {hint}")


if __name__ == "__main__":
    demo()
