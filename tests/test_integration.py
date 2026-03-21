#!/usr/bin/env python3
"""
Integration tests for rubric_system.

Tests that all modules import correctly, models are consistent,
rubric builders produce valid rubrics, and the scoring engine
computes correctly without any LLM calls.
"""

import pytest
import sys
from pathlib import Path

# Ensure the project root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


# ============================================================================
# 1. Import Chain Tests — every module resolves without error
# ============================================================================

class TestImports:
    def test_models_import(self):
        from rubric_system.models import (
            ScoringMethod, SubAttribute, ScoringRubric, SubScore,
            CriterionScore, Criterion, Rubric, Iteration, LoopResult,
            DocumentScore, ScoredRubricRecord, CriterionStats,
            FileScore, CIResult,
        )

    def test_init_reexports(self):
        from rubric_system import (
            ScoringMethod, Criterion, Rubric, LoopResult,
            CriterionScore, Iteration, DocumentScore,
        )

    def test_scoring_engine_import(self):
        from rubric_system.scoring_engine import ScoringEngine

    def test_sample_rubrics_import(self):
        from rubric_system.sample_rubrics import ALL_SAMPLE_RUBRICS, SAMPLE_TASKS, build_rubric_for_task

    def test_rubric_learning_import(self):
        from rubric_system.rubric_learning import RubricStore, RubricLearner

    def test_rubric_ci_import(self):
        from rubric_system.rubric_ci import CIRunner

    def test_harness_import(self):
        from rubric_harness import RubricLoop, build_knowledge_work_rubric, build_frontend_design_rubric, detect_domain

    def test_claude_code_import(self):
        from rubric_claude_code import ClaudeCodeRubricLoop


# ============================================================================
# 2. Model Consistency Tests
# ============================================================================

class TestModels:
    def test_scoring_method_values(self):
        from rubric_system.models import ScoringMethod
        expected = {"binary", "percentage", "weighted_components", "penalty_based", "threshold_tiers", "count_based"}
        actual = {m.value for m in ScoringMethod}
        assert actual == expected

    def test_criterion_defaults(self):
        from rubric_system.models import Criterion, ScoringMethod
        c = Criterion(id="test", category="test", description="test", pass_condition="test")
        assert c.scoring.method == ScoringMethod.BINARY
        assert c.scoring.max_points == 3
        assert c.source == "generated"
        assert c.pass_examples == []
        assert c.fail_examples == []

    def test_rubric_defaults(self):
        from rubric_system.models import Rubric
        r = Rubric(task="test", domain="test", criteria=[])
        assert r.total_points == 0
        assert r.pass_threshold == 0.85

    def test_criterion_score_defaults(self):
        from rubric_system.models import CriterionScore
        cs = CriterionScore(criterion_id="t", points_earned=5.0, max_points=10, percentage=0.5)
        assert cs.sub_scores == []
        assert cs.penalties_applied == []
        assert cs.improvement_hints == []
        assert cs.priority == 1

    def test_loop_result_fields(self):
        from rubric_system.models import LoopResult, Rubric
        r = Rubric(task="t", domain="d", criteria=[])
        lr = LoopResult(
            success=True, output="done", iterations=3,
            final_score=45.0, final_percentage=0.90,
            rubric=r, history=[]
        )
        assert lr.success is True
        assert lr.improvement_summary == []

    def test_criterion_stats_properties(self):
        from rubric_system.models import CriterionStats
        stats = CriterionStats(
            criterion_id="src_001", description="test",
            times_used=100, times_passed=80, times_failed=20,
            pass_then_bug=5, fail_then_bug=15,
            pass_then_success=75, fail_then_success=5
        )
        assert stats.pass_rate == 0.8
        assert stats.bug_prevention_rate == 0.75  # 15 / (5+15)
        assert stats.false_positive_rate == 0.25  # 5 / 20
        # predictive_value = (15 + 75) / (15 + 75 + 5 + 5) = 0.9
        assert stats.predictive_value == 0.9

    def test_criterion_stats_edge_cases(self):
        from rubric_system.models import CriterionStats
        # Zero usage
        stats = CriterionStats(
            criterion_id="t", description="t",
            times_used=0, times_passed=0, times_failed=0,
            pass_then_bug=0, fail_then_bug=0,
            pass_then_success=0, fail_then_success=0
        )
        assert stats.pass_rate == 0
        assert stats.bug_prevention_rate == 0
        assert stats.false_positive_rate == 0

        # Low usage → predictive_value defaults to 0.5
        stats2 = CriterionStats(
            criterion_id="t", description="t",
            times_used=5, times_passed=3, times_failed=2,
            pass_then_bug=0, fail_then_bug=0,
            pass_then_success=0, fail_then_success=0
        )
        assert stats2.predictive_value == 0.5


# ============================================================================
# 3. Sample Rubric Validation Tests
# ============================================================================

class TestSampleRubrics:
    def test_all_10_rubrics_build(self):
        from rubric_system.sample_rubrics import ALL_SAMPLE_RUBRICS
        assert len(ALL_SAMPLE_RUBRICS) == 10
        for builder in ALL_SAMPLE_RUBRICS:
            rubric = builder()
            assert rubric.task
            assert rubric.domain
            assert len(rubric.criteria) > 0
            assert rubric.total_points > 0
            assert 0 < rubric.pass_threshold <= 1.0

    def test_build_rubric_for_task(self):
        from rubric_system.sample_rubrics import build_rubric_for_task
        for i in range(1, 11):
            r = build_rubric_for_task(i)
            assert r.total_points > 0

    def test_build_rubric_for_task_out_of_range(self):
        from rubric_system.sample_rubrics import build_rubric_for_task
        with pytest.raises(ValueError):
            build_rubric_for_task(0)
        with pytest.raises(ValueError):
            build_rubric_for_task(11)

    def test_sample_tasks_dict_matches(self):
        from rubric_system.sample_rubrics import ALL_SAMPLE_RUBRICS, SAMPLE_TASKS
        assert len(SAMPLE_TASKS) == 10
        # Each value should be a callable that returns a Rubric
        for name, builder in SAMPLE_TASKS.items():
            r = builder()
            assert r.domain, f"Rubric for {name} has no domain"

    def test_total_points_consistency(self):
        """total_points should equal sum of criteria max_points."""
        from rubric_system.sample_rubrics import ALL_SAMPLE_RUBRICS
        for builder in ALL_SAMPLE_RUBRICS:
            rubric = builder()
            computed = sum(c.scoring.max_points for c in rubric.criteria)
            assert rubric.total_points == computed, (
                f"{rubric.domain}: total_points={rubric.total_points} != "
                f"sum(max_points)={computed}"
            )

    def test_criteria_ids_unique_per_rubric(self):
        from rubric_system.sample_rubrics import ALL_SAMPLE_RUBRICS
        for builder in ALL_SAMPLE_RUBRICS:
            rubric = builder()
            ids = [c.id for c in rubric.criteria]
            assert len(ids) == len(set(ids)), (
                f"{rubric.domain}: duplicate criterion IDs: {ids}"
            )

    def test_all_criteria_have_scoring(self):
        from rubric_system.sample_rubrics import ALL_SAMPLE_RUBRICS
        from rubric_system.models import ScoringMethod
        for builder in ALL_SAMPLE_RUBRICS:
            rubric = builder()
            for c in rubric.criteria:
                assert c.scoring is not None, f"{rubric.domain}/{c.id}: no scoring"
                assert c.scoring.method in ScoringMethod, f"{rubric.domain}/{c.id}: invalid method"
                assert c.scoring.max_points > 0, f"{rubric.domain}/{c.id}: max_points=0"

    def test_cold_outreach_email_specifics(self):
        from rubric_system.sample_rubrics import build_cold_outreach_email_rubric
        r = build_cold_outreach_email_rubric()
        assert r.domain == "cold_outreach_email"
        assert r.pass_threshold == 0.80
        assert len(r.criteria) == 7
        ids = {c.id for c in r.criteria}
        assert "email_subject" in ids
        assert "email_cta" in ids

    def test_investment_memo_specifics(self):
        from rubric_system.sample_rubrics import build_investment_memo_rubric
        r = build_investment_memo_rubric()
        assert r.domain == "investment_memo"
        assert len(r.criteria) == 5
        ids = {c.id for c in r.criteria}
        assert "memo_thesis" in ids
        assert "memo_risks" in ids


# ============================================================================
# 4. Harness Rubric Builder Tests
# ============================================================================

class TestHarnessRubrics:
    def test_knowledge_work_rubric(self):
        from rubric_harness import build_knowledge_work_rubric
        r = build_knowledge_work_rubric("Write a research brief on AI chips")
        assert r.domain == "knowledge_work_research"
        assert r.total_points > 0
        assert r.pass_threshold == 0.85
        # Should have criteria spanning source quality, evidence, viz, etc.
        categories = {c.category for c in r.criteria}
        assert "source_quality" in categories
        assert "evidence" in categories

    def test_frontend_design_rubric(self):
        from rubric_harness import build_frontend_design_rubric
        r = build_frontend_design_rubric("Design a dashboard for analytics app")
        assert r.domain == "frontend_design"
        assert r.total_points > 0
        assert len(r.criteria) == 17
        categories = {c.category for c in r.criteria}
        assert "accessibility" in categories
        assert "typography" in categories
        assert "layout" in categories

    def test_frontend_design_total_points_consistent(self):
        from rubric_harness import build_frontend_design_rubric
        r = build_frontend_design_rubric("test")
        computed = sum(c.scoring.max_points for c in r.criteria)
        assert r.total_points == computed

    def test_domain_detection_knowledge_work(self):
        from rubric_harness import detect_domain
        domain, conf = detect_domain("Write a research report on quantum computing with citations")
        assert domain == "knowledge_work_research"
        assert conf > 0

    def test_domain_detection_api(self):
        from rubric_harness import detect_domain
        domain, conf = detect_domain("Create a REST endpoint for user registration with POST")
        assert domain == "api_rest_endpoint"
        assert conf > 0

    def test_domain_detection_frontend(self):
        from rubric_harness import detect_domain
        domain, conf = detect_domain("Design a landing page UI with tailwind CSS")
        assert domain == "frontend_design"
        assert conf > 0

    def test_domain_detection_generic(self):
        from rubric_harness import detect_domain
        domain, conf = detect_domain("Do something completely unrelated to any domain")
        assert domain == "generic"
        assert conf == 0.0


# ============================================================================
# 5. Scoring Engine Tests — no LLM calls, pure computation
# ============================================================================

class TestScoringEngine:
    @pytest.fixture
    def engine(self):
        from rubric_system.scoring_engine import ScoringEngine
        return ScoringEngine()

    def test_binary_pass(self, engine):
        from rubric_system.models import Criterion, ScoringRubric, ScoringMethod
        c = Criterion(
            id="t", category="t", description="t", pass_condition="t",
            scoring=ScoringRubric(method=ScoringMethod.BINARY, max_points=5)
        )
        result = engine.score_criterion(c, {"passed": True})
        assert result.points_earned == 5
        assert result.percentage == 1.0

    def test_binary_fail(self, engine):
        from rubric_system.models import Criterion, ScoringRubric, ScoringMethod
        c = Criterion(
            id="t", category="t", description="t", pass_condition="t",
            scoring=ScoringRubric(method=ScoringMethod.BINARY, max_points=5)
        )
        result = engine.score_criterion(c, {"passed": False})
        assert result.points_earned == 0
        assert result.percentage == 0.0

    def test_percentage_scoring(self, engine):
        from rubric_system.models import Criterion, ScoringRubric, ScoringMethod
        c = Criterion(
            id="t", category="t", description="t", pass_condition="t",
            scoring=ScoringRubric(method=ScoringMethod.PERCENTAGE, max_points=10)
        )
        result = engine.score_criterion(c, {"percentage": 0.75})
        assert result.points_earned == 7.5
        assert result.percentage == 0.75

    def test_weighted_components_scoring(self, engine):
        from rubric_system.models import Criterion, ScoringRubric, ScoringMethod, SubAttribute
        c = Criterion(
            id="t", category="t", description="t", pass_condition="t",
            scoring=ScoringRubric(
                method=ScoringMethod.WEIGHTED_COMPONENTS,
                max_points=10,
                sub_attributes=[
                    SubAttribute(sub_id="a", description="A", weight=0.6, measurement="m"),
                    SubAttribute(sub_id="b", description="B", weight=0.4, measurement="m"),
                ]
            )
        )
        # a=1.0, b=0.5 → weighted = 0.6*1.0 + 0.4*0.5 = 0.8 → 8.0/10
        result = engine.score_criterion(c, {"a": 1.0, "b": 0.5})
        assert result.points_earned == 8.0
        assert abs(result.percentage - 0.8) < 0.01
        assert len(result.sub_scores) == 2

    def test_weighted_components_clamping(self, engine):
        """Values outside 0-1 should be clamped."""
        from rubric_system.models import Criterion, ScoringRubric, ScoringMethod, SubAttribute
        c = Criterion(
            id="t", category="t", description="t", pass_condition="t",
            scoring=ScoringRubric(
                method=ScoringMethod.WEIGHTED_COMPONENTS,
                max_points=10,
                sub_attributes=[
                    SubAttribute(sub_id="a", description="A", weight=1.0, measurement="m"),
                ]
            )
        )
        result = engine.score_criterion(c, {"a": 1.5})
        assert result.points_earned == 10.0  # clamped to 1.0

        result2 = engine.score_criterion(c, {"a": -0.5})
        assert result2.points_earned == 0.0  # clamped to 0.0

    def test_penalty_no_violations(self, engine):
        from rubric_system.models import Criterion, ScoringRubric, ScoringMethod
        c = Criterion(
            id="t", category="t", description="t", pass_condition="t",
            scoring=ScoringRubric(
                method=ScoringMethod.PENALTY_BASED,
                max_points=8,
                penalties={"bad_thing": -2.0, "worse_thing": -3.0}
            )
        )
        result = engine.score_criterion(c, {}, violations=[])
        assert result.points_earned == 8.0
        assert result.percentage == 1.0

    def test_penalty_with_violations(self, engine):
        from rubric_system.models import Criterion, ScoringRubric, ScoringMethod
        c = Criterion(
            id="t", category="t", description="t", pass_condition="t",
            scoring=ScoringRubric(
                method=ScoringMethod.PENALTY_BASED,
                max_points=8,
                penalties={"bad_thing": -2.0, "worse_thing": -3.0}
            )
        )
        result = engine.score_criterion(c, {}, violations=["bad_thing", "worse_thing"])
        assert result.points_earned == 3.0  # 8 - 2 - 3
        assert len(result.penalties_applied) == 2

    def test_penalty_floor_at_zero(self, engine):
        from rubric_system.models import Criterion, ScoringRubric, ScoringMethod
        c = Criterion(
            id="t", category="t", description="t", pass_condition="t",
            scoring=ScoringRubric(
                method=ScoringMethod.PENALTY_BASED,
                max_points=5,
                penalties={"a": -3.0, "b": -3.0, "c": -3.0}
            )
        )
        result = engine.score_criterion(c, {}, violations=["a", "b", "c"])
        assert result.points_earned == 0.0  # floored, not negative

    def test_count_based_scoring(self, engine):
        from rubric_system.models import Criterion, ScoringRubric, ScoringMethod
        c = Criterion(
            id="t", category="t", description="t", pass_condition="t",
            scoring=ScoringRubric(
                method=ScoringMethod.COUNT_BASED,
                max_points=10,
                points_per_instance=2.0,
                max_instances=10
            )
        )
        result = engine.score_criterion(c, {"count": 3})
        assert result.points_earned == 6.0  # 3 * 2.0

    def test_count_based_cap(self, engine):
        from rubric_system.models import Criterion, ScoringRubric, ScoringMethod
        c = Criterion(
            id="t", category="t", description="t", pass_condition="t",
            scoring=ScoringRubric(
                method=ScoringMethod.COUNT_BASED,
                max_points=10,
                points_per_instance=2.0,
                max_instances=10
            )
        )
        result = engine.score_criterion(c, {"count": 100})
        assert result.points_earned == 10.0  # capped at max_points

    def test_threshold_tiers_scoring(self, engine):
        from rubric_system.models import Criterion, ScoringRubric, ScoringMethod
        c = Criterion(
            id="t", category="t", description="t", pass_condition="t",
            scoring=ScoringRubric(
                method=ScoringMethod.THRESHOLD_TIERS,
                max_points=10,
                tiers={0.9: "excellent", 0.7: "good", 0.5: "acceptable", 0.3: "poor"}
            )
        )
        # Value 0.85 → falls in 0.7 tier
        result = engine.score_criterion(c, {"value": 0.85})
        assert result.points_earned == 7.0  # 10 * 0.7
        assert "good" in result.evidence

    def test_scoring_engine_against_sample_rubric(self, engine):
        """Score every criterion in a sample rubric with synthetic measurements."""
        from rubric_system.sample_rubrics import build_cold_outreach_email_rubric
        from rubric_system.models import ScoringMethod

        rubric = build_cold_outreach_email_rubric()
        total_earned = 0.0
        total_max = 0

        for c in rubric.criteria:
            if c.scoring.method == ScoringMethod.WEIGHTED_COMPONENTS:
                measurements = {sa.sub_id: 0.8 for sa in c.scoring.sub_attributes}
                result = engine.score_criterion(c, measurements)
            elif c.scoring.method == ScoringMethod.PENALTY_BASED:
                result = engine.score_criterion(c, {}, violations=[])
            elif c.scoring.method == ScoringMethod.BINARY:
                result = engine.score_criterion(c, {"passed": True})
            else:
                continue

            assert result.points_earned >= 0
            assert result.points_earned <= c.scoring.max_points
            assert result.max_points == c.scoring.max_points
            total_earned += result.points_earned
            total_max += c.scoring.max_points

        assert total_max == rubric.total_points
        assert total_earned > 0


# ============================================================================
# 6. End-to-End Rubric Scoring (all 10 sample rubrics)
# ============================================================================

class TestEndToEndScoring:
    def test_score_all_sample_rubrics_perfect(self):
        """Score all 10 sample rubrics with 'perfect' measurements — verify totals."""
        from rubric_system.sample_rubrics import ALL_SAMPLE_RUBRICS
        from rubric_system.scoring_engine import ScoringEngine
        from rubric_system.models import ScoringMethod

        engine = ScoringEngine()

        for builder in ALL_SAMPLE_RUBRICS:
            rubric = builder()
            total_earned = 0.0

            for c in rubric.criteria:
                if c.scoring.method == ScoringMethod.BINARY:
                    result = engine.score_criterion(c, {"passed": True})
                elif c.scoring.method == ScoringMethod.PERCENTAGE:
                    result = engine.score_criterion(c, {"percentage": 1.0})
                elif c.scoring.method == ScoringMethod.WEIGHTED_COMPONENTS:
                    m = {sa.sub_id: 1.0 for sa in c.scoring.sub_attributes}
                    result = engine.score_criterion(c, m)
                elif c.scoring.method == ScoringMethod.PENALTY_BASED:
                    result = engine.score_criterion(c, {}, violations=[])
                elif c.scoring.method == ScoringMethod.COUNT_BASED:
                    result = engine.score_criterion(c, {"count": c.scoring.max_instances})
                elif c.scoring.method == ScoringMethod.THRESHOLD_TIERS:
                    result = engine.score_criterion(c, {"value": 1.0})
                else:
                    continue

                total_earned += result.points_earned

            # Perfect score should equal total_points
            assert total_earned == rubric.total_points, (
                f"{rubric.domain}: perfect score {total_earned} != total_points {rubric.total_points}"
            )

    def test_score_all_sample_rubrics_zero(self):
        """Score all 10 sample rubrics with worst measurements — verify floors at 0."""
        from rubric_system.sample_rubrics import ALL_SAMPLE_RUBRICS
        from rubric_system.scoring_engine import ScoringEngine
        from rubric_system.models import ScoringMethod

        engine = ScoringEngine()

        for builder in ALL_SAMPLE_RUBRICS:
            rubric = builder()

            for c in rubric.criteria:
                if c.scoring.method == ScoringMethod.BINARY:
                    result = engine.score_criterion(c, {"passed": False})
                elif c.scoring.method == ScoringMethod.PERCENTAGE:
                    result = engine.score_criterion(c, {"percentage": 0.0})
                elif c.scoring.method == ScoringMethod.WEIGHTED_COMPONENTS:
                    m = {sa.sub_id: 0.0 for sa in c.scoring.sub_attributes}
                    result = engine.score_criterion(c, m)
                elif c.scoring.method == ScoringMethod.PENALTY_BASED:
                    violations = list(c.scoring.penalties.keys())
                    result = engine.score_criterion(c, {}, violations=violations)
                elif c.scoring.method == ScoringMethod.COUNT_BASED:
                    result = engine.score_criterion(c, {"count": 0})
                elif c.scoring.method == ScoringMethod.THRESHOLD_TIERS:
                    result = engine.score_criterion(c, {"value": 0.0})
                else:
                    continue

                assert result.points_earned >= 0, (
                    f"{rubric.domain}/{c.id}: score went negative ({result.points_earned})"
                )


# ============================================================================
# 7. Improvement Hints Tests
# ============================================================================

class TestImprovementHints:
    def test_weighted_generates_hints_for_low_scores(self):
        from rubric_system.scoring_engine import ScoringEngine
        from rubric_system.models import Criterion, ScoringRubric, ScoringMethod, SubAttribute

        engine = ScoringEngine()
        c = Criterion(
            id="t", category="t", description="t", pass_condition="t",
            scoring=ScoringRubric(
                method=ScoringMethod.WEIGHTED_COMPONENTS,
                max_points=10,
                sub_attributes=[
                    SubAttribute(sub_id="good", description="Good thing", weight=0.5, measurement="m"),
                    SubAttribute(sub_id="bad", description="Bad thing", weight=0.5, measurement="m"),
                ]
            )
        )
        result = engine.score_criterion(c, {"good": 0.95, "bad": 0.3})
        assert len(result.improvement_hints) >= 1
        assert "bad" in result.improvement_hints[0]

    def test_penalty_generates_hints(self):
        from rubric_system.scoring_engine import ScoringEngine
        from rubric_system.models import Criterion, ScoringRubric, ScoringMethod

        engine = ScoringEngine()
        c = Criterion(
            id="t", category="t", description="t", pass_condition="t",
            scoring=ScoringRubric(
                method=ScoringMethod.PENALTY_BASED,
                max_points=8,
                penalties={"issue_a": -2.0, "issue_b": -3.0}
            )
        )
        result = engine.score_criterion(c, {}, violations=["issue_a"])
        assert len(result.improvement_hints) >= 1
        assert "issue_a" in result.improvement_hints[0]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
