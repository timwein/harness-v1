"""
Preference-Label Consistency Filter (Phase 3 — OpenRubrics alignment).

Given a rubric and a set of held-out (preferred, rejected) pairs, the filter
scores both responses with the rubric and measures how often
``preferred_score > rejected_score``. A rubric that fails to reproduce the
preference label on a sufficient fraction of pairs is either regenerated
(bounded retry) or flagged low-confidence.

Per the locked plan:
  - threshold:           0.8
  - min pairs required:  5  (otherwise status="insufficient_pairs", skip)
  - aggregator:          explicit ScoringEngine path (passed in by harness)
  - granularity:         whole-rubric by default; per-criterion attribution
                         is computed on retry to help reseed generation.
  - bounded retry:       N=2 then warn-and-proceed ("failed_accepted").
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Optional, Awaitable, Literal

from rubric_system.models import Rubric, ReferencePair, PairSource


CONSISTENCY_THRESHOLD_DEFAULT = 0.8
MIN_PAIRS_DEFAULT = 5
MAX_RETRIES_DEFAULT = 2


Status = Literal["passed", "failed", "failed_accepted", "insufficient_pairs", "skipped", "errored"]


# score_fn: (rubric, response_text) -> (total_score, per_criterion_points: dict[criterion_id, float])
ScoreFn = Callable[[Rubric, str], Awaitable[tuple[float, dict[str, float]]]]


@dataclass
class PairResult:
    pair_index: int
    source: str
    preferred_score: float
    rejected_score: float
    ranked_correctly: bool
    # Per-criterion deltas (preferred - rejected). Only populated on retry.
    per_criterion_delta: Optional[dict[str, float]] = None


@dataclass
class ConsistencyResult:
    hit_rate: float
    n_pairs: int
    status: Status
    per_pair: list[PairResult] = field(default_factory=list)
    # Fraction of the overall misranking attributed to each criterion (0..1, sums ≤1).
    # Only populated when ``attribute`` was called (i.e. on retry).
    per_criterion_attribution: Optional[dict[str, float]] = None
    pair_sources: list[str] = field(default_factory=list)


@dataclass
class RubricConsistencyValidator:
    """Run the preference-label consistency check against a rubric."""

    score_fn: ScoreFn
    threshold: float = CONSISTENCY_THRESHOLD_DEFAULT
    min_pairs: int = MIN_PAIRS_DEFAULT

    async def validate(
        self,
        rubric: Rubric,
        held_out: list[ReferencePair],
        per_criterion: bool = False,
    ) -> ConsistencyResult:
        if len(held_out) < self.min_pairs:
            return ConsistencyResult(
                hit_rate=0.0,
                n_pairs=len(held_out),
                status="insufficient_pairs",
                pair_sources=sorted({self._source_of(p) for p in held_out}),
            )

        per_pair: list[PairResult] = []
        hits = 0
        for i, pair in enumerate(held_out):
            try:
                pref_total, pref_per_crit = await self.score_fn(rubric, pair.preferred)
                rej_total, rej_per_crit = await self.score_fn(rubric, pair.rejected)
            except Exception:
                # Any scoring error short-circuits to errored status.
                return ConsistencyResult(
                    hit_rate=0.0,
                    n_pairs=len(held_out),
                    status="errored",
                    per_pair=per_pair,
                    pair_sources=sorted({self._source_of(p) for p in held_out}),
                )

            ranked = pref_total > rej_total
            if ranked:
                hits += 1

            delta = None
            if per_criterion:
                delta = {
                    cid: pref_per_crit.get(cid, 0.0) - rej_per_crit.get(cid, 0.0)
                    for cid in set(pref_per_crit) | set(rej_per_crit)
                }

            per_pair.append(PairResult(
                pair_index=i,
                source=self._source_of(pair),
                preferred_score=pref_total,
                rejected_score=rej_total,
                ranked_correctly=ranked,
                per_criterion_delta=delta,
            ))

        hit_rate = hits / len(held_out)
        status: Status = "passed" if hit_rate >= self.threshold else "failed"

        result = ConsistencyResult(
            hit_rate=hit_rate,
            n_pairs=len(held_out),
            status=status,
            per_pair=per_pair,
            pair_sources=sorted({self._source_of(p) for p in held_out}),
        )

        if per_criterion:
            result.per_criterion_attribution = self._attribute(per_pair)

        return result

    def attribute(self, prior: ConsistencyResult) -> dict[str, float]:
        """Re-compute per-criterion attribution from an existing ConsistencyResult."""
        # If the caller ran the validation without per_criterion, attribution
        # cannot be derived retroactively — the per-criterion deltas were never
        # captured. Return an empty dict in that case.
        if not prior.per_pair or all(p.per_criterion_delta is None for p in prior.per_pair):
            return {}
        return self._attribute(prior.per_pair)

    @staticmethod
    def _attribute(per_pair: list[PairResult]) -> dict[str, float]:
        """Fraction of total misranking attributed to each criterion.

        For each failing pair, a criterion gets credit proportional to how much
        it pushed the ranking in the WRONG direction (rejected > preferred on
        that criterion). Scores are normalized across failing pairs and criteria
        so they sum to 1.0 when there is any misranking to attribute.
        """
        negatives: dict[str, float] = {}
        total = 0.0
        for pr in per_pair:
            if pr.ranked_correctly or pr.per_criterion_delta is None:
                continue
            for cid, delta in pr.per_criterion_delta.items():
                if delta < 0.0:
                    negatives[cid] = negatives.get(cid, 0.0) + (-delta)
                    total += -delta
        if total == 0.0:
            return {}
        return {cid: round(v / total, 6) for cid, v in negatives.items()}

    @staticmethod
    def _source_of(pair: ReferencePair) -> str:
        return pair.source.value if hasattr(pair.source, "value") else str(pair.source)


def apply_consistency_outcome(rubric: Rubric, result: ConsistencyResult) -> Rubric:
    """Write consistency outcome onto the Rubric's nullable columns."""
    rubric.consistency_hit_rate = result.hit_rate
    rubric.consistency_n_pairs = result.n_pairs
    rubric.consistency_status = result.status
    if result.pair_sources:
        rubric.consistency_pair_sources = ",".join(result.pair_sources)
    return rubric
