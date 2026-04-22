"""
Unit tests for Phase 3 — Preference-label consistency filter.
"""
import asyncio

import pytest

from rubric_system.models import (
    Rubric, Criterion, ScoringRubric, ScoringMethod,
    ReferencePair, PairSource,
)
from rubric_system.consistency import (
    RubricConsistencyValidator,
    ConsistencyResult,
    apply_consistency_outcome,
    CONSISTENCY_THRESHOLD_DEFAULT,
    MIN_PAIRS_DEFAULT,
)


def _make_rubric() -> Rubric:
    c = Criterion(
        id="c1", category="cat", description="desc", pass_condition="",
        scoring=ScoringRubric(method=ScoringMethod.BINARY, max_points=5),
    )
    return Rubric(task="t", domain="d", criteria=[c], total_points=5)


def _pairs(n: int) -> list[ReferencePair]:
    return [
        ReferencePair(preferred=f"PREF-{i}", rejected=f"REJ-{i}", source=PairSource.SYNTHETIC)
        for i in range(n)
    ]


# ---------------------------------------------------------------------------
# Insufficient pairs
# ---------------------------------------------------------------------------

def test_insufficient_pairs_returns_status_and_skips_scoring():
    called = {"n": 0}

    async def score_fn(r, resp):
        called["n"] += 1
        return 1.0, {}

    async def _run():
        v = RubricConsistencyValidator(score_fn=score_fn, min_pairs=5)
        return await v.validate(_make_rubric(), _pairs(3))

    result = asyncio.run(_run())
    assert result.status == "insufficient_pairs"
    assert result.n_pairs == 3
    assert called["n"] == 0, "score_fn must not be called when pairs are insufficient"


# ---------------------------------------------------------------------------
# Ranking pass / fail / threshold
# ---------------------------------------------------------------------------

def test_all_correctly_ranked_returns_passed():
    async def score_fn(r, resp):
        # Preferred responses start with "PREF-"; assign higher score to those.
        return (1.0, {"c1": 1.0}) if resp.startswith("PREF") else (0.0, {"c1": 0.0})

    async def _run():
        v = RubricConsistencyValidator(score_fn=score_fn, threshold=0.8, min_pairs=5)
        return await v.validate(_make_rubric(), _pairs(5))

    result = asyncio.run(_run())
    assert result.status == "passed"
    assert result.hit_rate == 1.0
    assert result.n_pairs == 5


def test_below_threshold_returns_failed():
    # Reverse the ranking on 3/5 pairs.
    async def score_fn(r, resp):
        # Pair index is embedded in response suffix: PREF-0..4, REJ-0..4
        idx = int(resp.split("-")[-1])
        # Correct ranking on pair 0, 1; backwards on pair 2, 3, 4
        if idx < 2:
            return (1.0, {}) if resp.startswith("PREF") else (0.0, {})
        else:
            return (0.0, {}) if resp.startswith("PREF") else (1.0, {})

    async def _run():
        v = RubricConsistencyValidator(score_fn=score_fn, threshold=0.8, min_pairs=5)
        return await v.validate(_make_rubric(), _pairs(5))

    result = asyncio.run(_run())
    assert result.status == "failed"
    assert result.hit_rate == pytest.approx(0.4, abs=1e-6)
    # Failing pairs should be marked
    failing = [p for p in result.per_pair if not p.ranked_correctly]
    assert len(failing) == 3


def test_at_threshold_passes():
    # 4/5 = 0.8, exactly at threshold
    async def score_fn(r, resp):
        idx = int(resp.split("-")[-1])
        # Backwards on pair 4 only
        if idx == 4:
            return (0.0, {}) if resp.startswith("PREF") else (1.0, {})
        return (1.0, {}) if resp.startswith("PREF") else (0.0, {})

    async def _run():
        v = RubricConsistencyValidator(score_fn=score_fn, threshold=0.8, min_pairs=5)
        return await v.validate(_make_rubric(), _pairs(5))

    result = asyncio.run(_run())
    assert result.status == "passed"
    assert result.hit_rate == pytest.approx(0.8, abs=1e-6)


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------

def test_score_fn_exception_returns_errored():
    async def score_fn(r, resp):
        raise RuntimeError("scorer boom")

    async def _run():
        v = RubricConsistencyValidator(score_fn=score_fn, min_pairs=5)
        return await v.validate(_make_rubric(), _pairs(5))

    result = asyncio.run(_run())
    assert result.status == "errored"
    assert result.hit_rate == 0.0


# ---------------------------------------------------------------------------
# Per-criterion attribution (retry path)
# ---------------------------------------------------------------------------

def test_per_criterion_attribution_only_on_retry():
    async def score_fn(r, resp):
        # Backwards on all: rejected beats preferred on criterion c1
        if resp.startswith("REJ"):
            return (5.0, {"c1": 5.0})
        return (1.0, {"c1": 1.0})

    async def _run():
        v = RubricConsistencyValidator(score_fn=score_fn, threshold=0.8, min_pairs=5)
        return await v.validate(_make_rubric(), _pairs(5), per_criterion=True)

    result = asyncio.run(_run())
    assert result.status == "failed"
    assert result.per_criterion_attribution is not None
    assert result.per_criterion_attribution.get("c1", 0.0) == pytest.approx(1.0)


def test_attribute_empty_when_no_deltas_captured():
    async def score_fn(r, resp):
        return (0.0, {}) if resp.startswith("REJ") else (1.0, {})

    async def _run():
        v = RubricConsistencyValidator(score_fn=score_fn, min_pairs=5)
        result = await v.validate(_make_rubric(), _pairs(5), per_criterion=False)
        # No per-criterion data captured; retroactive attribute should be empty.
        return result, v.attribute(result)

    result, attribution = asyncio.run(_run())
    assert result.status == "passed"
    assert attribution == {}


# ---------------------------------------------------------------------------
# apply_consistency_outcome
# ---------------------------------------------------------------------------

def test_apply_consistency_outcome_populates_nullable_fields():
    r = _make_rubric()
    assert r.consistency_hit_rate is None
    result = ConsistencyResult(
        hit_rate=0.75, n_pairs=5, status="failed", pair_sources=["synthetic", "store"],
    )
    apply_consistency_outcome(r, result)
    assert r.consistency_hit_rate == 0.75
    assert r.consistency_n_pairs == 5
    assert r.consistency_status == "failed"
    assert r.consistency_pair_sources == "synthetic,store"


# ---------------------------------------------------------------------------
# Bounded retry is tested via an integration-style stub
# ---------------------------------------------------------------------------

def test_retry_progression_scaffolding_minimal():
    """Smoke-test the validator + attribute loop the harness will drive."""
    rubric = _make_rubric()

    # Fixture: first pass misranks 3/5; second pass misranks 1/5 (passes).
    state = {"calls": 0}

    async def score_fn(r, resp):
        idx = int(resp.split("-")[-1])
        # Flip behavior every 5 calls (one validate() pass = 10 calls: 5 pairs × 2 responses)
        pass_num = state["calls"] // 10
        state["calls"] += 1
        if pass_num == 0:
            if idx < 2:
                return (1.0, {}) if resp.startswith("PREF") else (0.0, {})
            return (0.0, {}) if resp.startswith("PREF") else (1.0, {})
        return (1.0, {}) if resp.startswith("PREF") else (0.0, {})

    async def _run():
        v = RubricConsistencyValidator(score_fn=score_fn, threshold=0.8, min_pairs=5)
        pairs = _pairs(5)
        r1 = await v.validate(rubric, pairs)
        assert r1.status == "failed"
        r2 = await v.validate(rubric, pairs)
        assert r2.status == "passed"

    asyncio.run(_run())
