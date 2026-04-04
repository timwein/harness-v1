#!/usr/bin/env python3
"""
ACON (Adaptive Compression for Navigation) — Paired Trajectory System

Learns what context is safe to compress across runs by comparing generation
quality between full-context and compressed-context paths. Compression
tolerance is a property of the TASK DOMAIN, not the specific task.

Components:
  - HistoryCompressor: converts iteration history to compressed form
  - ObservationMasker: hides evidence details in compressed path
  - PairedResultRecorder: stores paired results keyed by domain
  - AconGuidelineLearner: aggregates results into compression guidelines

Usage:
    After the main iteration loop completes, run _collect_paired_trajectory()
    to generate content twice (full vs compressed history), score both, and
    record the per-criterion delta. After 5+ runs per domain, guidelines
    are generated automatically.
"""

import json
import os
import time
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Optional, List, Dict, Any
from statistics import mean, stdev


# ============================================================================
# Data Models
# ============================================================================

@dataclass
class PerCriterionDelta:
    """Delta for a single criterion between full and compressed paths."""
    criterion_id: str
    full_percentage: float
    compressed_percentage: float
    delta: float  # compressed - full (positive = compression helped)
    delta_points: float


@dataclass
class PairedPathMetrics:
    """Metrics for a single generation path (full or compressed)."""
    input_tokens_estimate: int
    output_tokens_estimate: int
    generation_time_sec: float
    criterion_scores: List[Dict[str, Any]]  # serialized CriterionScore dicts
    total_score: float
    total_max: int
    final_percentage: float


@dataclass
class CompressionEffectiveness:
    """Overall compression effectiveness metrics for a run."""
    time_saved_sec: float
    token_savings: int
    score_stability: str  # "HIGH" (<5pp), "MEDIUM" (<10pp), "LOW" (>=10pp)
    max_criterion_delta: float


@dataclass
class PairedResult:
    """Complete result of a paired trajectory run."""
    run_id: str
    timestamp: str  # ISO 8601
    task: str
    domain: str
    paired_iteration: int
    max_iterations: int
    criteria_count: int
    full_path: Dict[str, Any]  # serialized PairedPathMetrics
    compressed_path: Dict[str, Any]
    per_criterion_delta: List[Dict[str, Any]]  # serialized PerCriterionDelta
    overall_delta_pp: float  # percentage points: compressed - full
    compression_effectiveness: Dict[str, Any]


@dataclass
class AconGuideline:
    """Per-criterion compression guideline for a domain."""
    criterion_id: str
    domain: str
    compression_recommendation: str  # "SAFE", "CAUTION", "UNSAFE", "INSUFFICIENT_DATA"
    confidence: float  # 0.0-1.0
    mean_delta_pp: float
    stddev_delta_pp: float
    max_abs_delta: float
    min_delta: float
    run_count: int
    reasoning: str


@dataclass
class AconGuidelineSet:
    """Full guideline set for a domain."""
    version: str  # "1.0", "1.1", "2.0"
    domain: str
    generated_at: str
    run_count: int
    prior_version: Optional[str]
    guidelines: List[Dict[str, Any]]  # serialized AconGuideline dicts


# ============================================================================
# History Compressor
# ============================================================================

class HistoryCompressor:
    """Compress iteration history for Path B (compressed context)."""

    def compress_iteration(self, iteration) -> str:
        """Convert a full Iteration object to a 3-line summary.

        Line 1: Overall score + pass/fail status
        Line 2: Top 3 strengths and bottom 3 weaknesses by criterion
        Line 3: Focus areas for next iteration (top 3)
        """
        pct = iteration.percentage
        status = "PASS" if pct >= 0.85 else "NEEDS WORK"

        # Sort criteria by percentage
        sorted_scores = sorted(
            iteration.criterion_scores,
            key=lambda cs: cs.percentage,
            reverse=True,
        )
        top_3 = sorted_scores[:3]
        bottom_3 = sorted_scores[-3:] if len(sorted_scores) > 3 else []

        strengths = ", ".join(
            f"{cs.criterion_id} ({cs.percentage:.0%})" for cs in top_3
        )
        weaknesses = ", ".join(
            f"{cs.criterion_id} ({cs.percentage:.0%})" for cs in bottom_3
        ) if bottom_3 else "none"

        focus = ", ".join(iteration.focus_areas[:3]) if iteration.focus_areas else "none"

        return (
            f"Iteration {iteration.number} ({pct:.1%} — {status})\n"
            f"  Strengths: [{strengths}]. Weaknesses: [{weaknesses}]\n"
            f"  Focus: {focus}"
        )

    def compress_history(
        self,
        history: list,
        keep_recent: int = 2,
    ) -> list:
        """Compress all but the most recent `keep_recent` iterations.

        Returns a mixed list:
          - Older iterations: replaced with summary strings
          - Recent iterations: kept as-is (full Iteration objects)
        """
        if len(history) <= keep_recent:
            return list(history)  # nothing to compress

        compressed = []
        for iteration in history[:-keep_recent]:
            compressed.append(self.compress_iteration(iteration))
        # Keep recent iterations in full
        compressed.extend(history[-keep_recent:])
        return compressed


# ============================================================================
# Observation Masker
# ============================================================================

class ObservationMasker:
    """Hide evidence details in the compressed path."""

    def mask_criterion_scores(self, scores: list) -> list:
        """Replace evidence strings with '[MASKED]' while keeping
        numerical scores intact. Returns new list (non-destructive)."""
        masked = []
        for cs in scores:
            # Create a shallow copy-like dict
            masked_cs = type(cs)(
                criterion_id=cs.criterion_id,
                points_earned=cs.points_earned,
                max_points=cs.max_points,
                percentage=cs.percentage,
                sub_scores=[],  # drop sub-score details
                penalties_applied=[],  # drop penalty details
                evidence="[MASKED]",
                methodology=cs.methodology,
                improvement_hints=cs.improvement_hints[:1],  # keep top hint only
                priority=cs.priority,
                critique="[MASKED]",
            )
            masked.append(masked_cs)
        return masked


# ============================================================================
# Paired Result Recorder
# ============================================================================

class PairedResultRecorder:
    """Store and retrieve paired trajectory results, keyed by domain."""

    def __init__(self, storage_dir: Optional[str] = None):
        if storage_dir is None:
            storage_dir = str(Path.home() / ".auto-verifier-data" / "acon")
        self.storage_dir = Path(storage_dir)
        self.results_file = self.storage_dir / "acon_paired_results.json"
        self.guidelines_dir = self.storage_dir / "acon_guidelines"
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.guidelines_dir.mkdir(parents=True, exist_ok=True)

    def _load_all_results(self) -> Dict[str, Any]:
        if self.results_file.exists():
            with open(self.results_file) as f:
                return json.load(f)
        return {"schema_version": "1.0", "paired_results": [], "domain_index": {}}

    def _save_all_results(self, data: Dict[str, Any]):
        with open(self.results_file, "w") as f:
            json.dump(data, f, indent=2)

    def record_paired_run(self, result: PairedResult):
        """Append a paired result to storage."""
        data = self._load_all_results()
        data["paired_results"].append(asdict(result))

        # Update domain index
        domain = result.domain
        if domain not in data["domain_index"]:
            data["domain_index"][domain] = {"run_count": 0, "runs": []}
        data["domain_index"][domain]["run_count"] += 1
        data["domain_index"][domain]["runs"].append(result.run_id)

        self._save_all_results(data)

    def load_paired_results(self, domain: str) -> List[Dict[str, Any]]:
        """Load all paired results for a domain."""
        data = self._load_all_results()
        return [
            r for r in data["paired_results"]
            if r.get("domain") == domain
        ]

    def get_domain_run_count(self, domain: str) -> int:
        data = self._load_all_results()
        return data.get("domain_index", {}).get(domain, {}).get("run_count", 0)

    def save_guideline(self, domain: str, guideline_set: AconGuidelineSet):
        """Write a guideline set for a domain."""
        domain_dir = self.guidelines_dir / domain
        domain_dir.mkdir(parents=True, exist_ok=True)
        filepath = domain_dir / f"guideline_v{guideline_set.version}.json"
        with open(filepath, "w") as f:
            json.dump(asdict(guideline_set), f, indent=2)

    def load_latest_guideline(self, domain: str) -> Optional[AconGuidelineSet]:
        """Load the latest guideline set for a domain."""
        domain_dir = self.guidelines_dir / domain
        if not domain_dir.exists():
            return None
        files = sorted(domain_dir.glob("guideline_v*.json"))
        if not files:
            return None
        with open(files[-1]) as f:
            data = json.load(f)
        return AconGuidelineSet(**data)


# ============================================================================
# Guideline Learner
# ============================================================================

class AconGuidelineLearner:
    """Aggregate paired results into compression guidelines per domain."""

    MIN_RUNS = 5  # minimum runs before generating guidelines

    def __init__(self, recorder: PairedResultRecorder):
        self.recorder = recorder

    def _collect_criterion_deltas(
        self, results: List[Dict[str, Any]]
    ) -> Dict[str, List[float]]:
        """Group per-criterion deltas across all paired runs."""
        deltas_by_crit = {}  # type: Dict[str, List[float]]
        for result in results:
            for delta_rec in result.get("per_criterion_delta", []):
                crit_id = delta_rec["criterion_id"]
                if crit_id not in deltas_by_crit:
                    deltas_by_crit[crit_id] = []
                deltas_by_crit[crit_id].append(delta_rec["delta"])
        return deltas_by_crit

    def _classify_criterion(
        self,
        crit_id: str,
        deltas: List[float],
        domain: str,
    ) -> AconGuideline:
        """Classify a single criterion as SAFE/CAUTION/UNSAFE."""
        n = len(deltas)

        if n < self.MIN_RUNS:
            return AconGuideline(
                criterion_id=crit_id,
                domain=domain,
                compression_recommendation="INSUFFICIENT_DATA",
                confidence=0.0,
                mean_delta_pp=mean(deltas) if deltas else 0.0,
                stddev_delta_pp=stdev(deltas) if n >= 2 else 0.0,
                max_abs_delta=max(abs(d) for d in deltas) if deltas else 0.0,
                min_delta=min(deltas) if deltas else 0.0,
                run_count=n,
                reasoning=f"Only {n} runs. Need {self.MIN_RUNS} for reliable guidelines.",
            )

        avg = mean(deltas)
        sd = stdev(deltas) if n >= 2 else 0.0
        max_abs = max(abs(d) for d in deltas)
        min_d = min(deltas)
        confidence = min(1.0, 0.5 + (n / 10) * 0.5)

        # Classification logic (deltas are compressed - full, so negative = compression hurt)
        if max_abs < 0.02:
            # All deltas under 2 percentage points — very stable
            rec = "SAFE"
            reasoning = (
                f"All {n} runs had <2pp absolute delta. "
                f"Mean {avg:+.3f}pp, max |delta| {max_abs:.3f}pp. "
                f"Safe to compress this criterion's evidence."
            )
        elif avg > -0.03 and sd < 0.04 and max_abs < 0.10:
            # Moderate: mean within 3pp, low variance, no blowups
            rec = "CAUTION"
            reasoning = (
                f"Mean delta {avg:+.3f}pp (within 3pp), stddev {sd:.3f}pp, "
                f"but max |delta| {max_abs:.3f}pp shows occasional instability. "
                f"Compress with monitoring."
            )
        else:
            # Unsafe: consistent regressions or high variance
            rec = "UNSAFE"
            reasoning = (
                f"Compression causes regressions. Mean delta {avg:+.3f}pp, "
                f"stddev {sd:.3f}pp, max |delta| {max_abs:.3f}pp over {n} runs. "
                f"Do NOT compress this criterion's evidence."
            )

        return AconGuideline(
            criterion_id=crit_id,
            domain=domain,
            compression_recommendation=rec,
            confidence=confidence,
            mean_delta_pp=avg,
            stddev_delta_pp=sd,
            max_abs_delta=max_abs,
            min_delta=min_d,
            run_count=n,
            reasoning=reasoning,
        )

    def generate_guideline_set(self, domain: str) -> Optional[AconGuidelineSet]:
        """Generate a full guideline set for a domain from paired results."""
        results = self.recorder.load_paired_results(domain)
        if len(results) < self.MIN_RUNS:
            return None

        deltas_by_crit = self._collect_criterion_deltas(results)
        guidelines = []
        for crit_id, deltas in deltas_by_crit.items():
            guideline = self._classify_criterion(crit_id, deltas, domain)
            guidelines.append(asdict(guideline))

        # Determine version
        existing = self.recorder.load_latest_guideline(domain)
        if existing is None:
            version = "1.0"
            prior = None
        else:
            # Check if any recommendations changed
            old_recs = {
                g["criterion_id"]: g["compression_recommendation"]
                for g in existing.guidelines
            }
            new_recs = {
                g["criterion_id"]: g["compression_recommendation"]
                for g in guidelines
            }
            if old_recs != new_recs:
                # Recommendation changed — minor bump
                major, minor = existing.version.split(".")
                version = f"{int(major) + 1}.0"
            else:
                # Just more data — patch bump
                major, minor = existing.version.split(".")
                version = f"{major}.{int(minor) + 1}"
            prior = existing.version

        guideline_set = AconGuidelineSet(
            version=version,
            domain=domain,
            generated_at=datetime.utcnow().isoformat() + "Z",
            run_count=len(results),
            prior_version=prior,
            guidelines=guidelines,
        )

        self.recorder.save_guideline(domain, guideline_set)
        return guideline_set

    def get_compression_hints(self, domain: str) -> str:
        """Format active guidelines as a prompt injection string."""
        guideline_set = self.recorder.load_latest_guideline(domain)
        if guideline_set is None:
            return ""

        lines = ["\nCONTEXT PRESERVATION (learned from prior runs):"]
        safe_count = 0
        unsafe_count = 0

        for g in sorted(guideline_set.guidelines, key=lambda x: x.get("max_abs_delta", 0), reverse=True):
            rec = g.get("compression_recommendation", "INSUFFICIENT_DATA")
            crit_id = g.get("criterion_id", "unknown")
            if rec == "UNSAFE":
                lines.append(f"  - PRESERVE {crit_id}: compression hurts quality ({g.get('reasoning', '')})")
                unsafe_count += 1
            elif rec == "SAFE":
                safe_count += 1
            elif rec == "CAUTION":
                lines.append(f"  - MONITOR {crit_id}: compression sometimes hurts ({g.get('reasoning', '')})")

        if safe_count > 0:
            lines.append(f"  - {safe_count} criteria are SAFE to compress (evidence can be summarized)")

        if len(lines) <= 1:
            return ""  # nothing useful to say
        return "\n".join(lines)


# ============================================================================
# Paired Trajectory Collector (integrates into RubricLoop)
# ============================================================================

class PairedTrajectoryCollector:
    """Runs paired trajectories and records results.

    Designed to be called from RubricLoop after the main iteration loop.
    Requires access to the loop's generate_content and score_content methods.
    """

    def __init__(
        self,
        storage_dir: Optional[str] = None,
        paired_iteration: int = 2,
        verbose: bool = True,
    ):
        self.recorder = PairedResultRecorder(storage_dir)
        self.learner = AconGuidelineLearner(self.recorder)
        self.compressor = HistoryCompressor()
        self.masker = ObservationMasker()
        self.paired_iteration = paired_iteration
        self.verbose = verbose

    def _log(self, msg: str):
        if self.verbose:
            print(msg)

    async def collect(
        self,
        task: str,
        domain: str,
        rubric,  # Rubric object
        history: list,  # list of Iteration objects
        generate_fn,  # async fn(rubric, history, focus_areas, ...) -> str
        score_fn,  # async fn(content, rubric) -> (score, max, criterion_scores)
        max_iterations: int,
    ) -> Optional[PairedResult]:
        """Run paired trajectory on the selected iteration.

        Args:
            task: Original task string
            domain: Rubric domain
            rubric: The Rubric object used for scoring
            history: Full iteration history from the main loop
            generate_fn: Async function matching RubricLoop.generate_content signature:
                (rubric, history, focus_areas, current_iter, max_iterations, ...) -> str
            score_fn: Async function matching RubricLoop.score_content signature:
                (content, rubric) -> (score, max, criterion_scores, checklist)
            max_iterations: Max iterations setting from the loop

        Returns:
            PairedResult if collected, None if skipped
        """
        iter_num = self.paired_iteration
        if len(history) < iter_num:
            self._log(
                f"[ACON] Skipping paired trajectory: need {iter_num} iterations, "
                f"have {len(history)}"
            )
            return None

        self._log(f"\n[ACON] Collecting paired trajectories on iteration {iter_num}...")

        # Get history up to (but not including) the paired iteration
        prior_history = history[:iter_num - 1]

        # Extract focus areas from prior iteration
        focus_areas = []
        if prior_history and hasattr(prior_history[-1], 'focus_areas'):
            focus_areas = prior_history[-1].focus_areas or []

        # PATH A: Full history (uncompressed)
        self._log(f"[ACON] Path A: generating with full history...")
        t0 = time.time()
        try:
            content_full = await generate_fn(
                rubric=rubric,
                history=prior_history,
                focus_areas=focus_areas,
                current_iter=iter_num,
                max_iterations=max_iterations,
            )
            time_full = time.time() - t0
            # score_content returns (score, max, criterion_scores, checklist)
            score_full, max_full, scores_full, _ = await score_fn(content_full, rubric)
        except Exception as e:
            self._log(f"[ACON] Path A failed: {e}")
            return None

        # PATH B: Compressed history
        self._log(f"[ACON] Path B: generating with compressed history...")
        compressed_history = self.compressor.compress_history(prior_history, keep_recent=1)
        t0 = time.time()
        try:
            content_compressed = await generate_fn(
                rubric=rubric,
                history=compressed_history,
                focus_areas=focus_areas,
                current_iter=iter_num,
                max_iterations=max_iterations,
            )
            time_compressed = time.time() - t0
            # score_content returns (score, max, criterion_scores, checklist)
            score_compressed, max_compressed, scores_compressed, _ = await score_fn(
                content_compressed, rubric
            )
        except Exception as e:
            self._log(f"[ACON] Path B failed: {e}")
            return None

        # Compute deltas
        pct_full = score_full / max_full if max_full > 0 else 0
        pct_compressed = score_compressed / max_compressed if max_compressed > 0 else 0

        per_crit_deltas = []
        for fs, cs in zip(scores_full, scores_compressed):
            delta = cs.percentage - fs.percentage
            per_crit_deltas.append(PerCriterionDelta(
                criterion_id=fs.criterion_id,
                full_percentage=fs.percentage,
                compressed_percentage=cs.percentage,
                delta=delta,
                delta_points=cs.points_earned - fs.points_earned,
            ))

        overall_delta = pct_compressed - pct_full
        max_crit_delta = max(abs(d.delta) for d in per_crit_deltas) if per_crit_deltas else 0

        if max_crit_delta < 0.05:
            stability = "HIGH"
        elif max_crit_delta < 0.10:
            stability = "MEDIUM"
        else:
            stability = "LOW"

        # Estimate tokens (rough: ~1.3 tokens per word)
        full_input_tokens = int(len(str(prior_history)) / 4)
        compressed_input_tokens = int(len(str(compressed_history)) / 4)

        result = PairedResult(
            run_id=f"task_{datetime.utcnow().strftime('%Y%m%dT%H%M%S')}_{domain}",
            timestamp=datetime.utcnow().isoformat() + "Z",
            task=task[:200],  # truncate long tasks
            domain=domain,
            paired_iteration=iter_num,
            max_iterations=max_iterations,
            criteria_count=len(rubric.criteria),
            full_path={
                "input_tokens_estimate": full_input_tokens,
                "output_tokens_estimate": int(len(content_full) / 4),
                "generation_time_sec": round(time_full, 2),
                "total_score": score_full,
                "total_max": max_full,
                "final_percentage": round(pct_full, 4),
            },
            compressed_path={
                "input_tokens_estimate": compressed_input_tokens,
                "output_tokens_estimate": int(len(content_compressed) / 4),
                "generation_time_sec": round(time_compressed, 2),
                "total_score": score_compressed,
                "total_max": max_compressed,
                "final_percentage": round(pct_compressed, 4),
            },
            per_criterion_delta=[asdict(d) for d in per_crit_deltas],
            overall_delta_pp=round(overall_delta, 4),
            compression_effectiveness={
                "time_saved_sec": round(time_full - time_compressed, 2),
                "token_savings": full_input_tokens - compressed_input_tokens,
                "score_stability": stability,
                "max_criterion_delta": round(max_crit_delta, 4),
            },
        )

        # Record
        self.recorder.record_paired_run(result)
        self._log(
            f"[ACON] Paired result recorded. "
            f"Full: {pct_full:.1%}, Compressed: {pct_compressed:.1%}, "
            f"Delta: {overall_delta:+.1%}pp, Stability: {stability}"
        )

        # Auto-generate guidelines if enough runs
        run_count = self.recorder.get_domain_run_count(domain)
        if run_count >= AconGuidelineLearner.MIN_RUNS:
            self._log(
                f"[ACON] {run_count} runs for domain '{domain}'. "
                f"Updating compression guidelines..."
            )
            guideline_set = self.learner.generate_guideline_set(domain)
            if guideline_set:
                safe = sum(
                    1 for g in guideline_set.guidelines
                    if g.get("compression_recommendation") == "SAFE"
                )
                unsafe = sum(
                    1 for g in guideline_set.guidelines
                    if g.get("compression_recommendation") == "UNSAFE"
                )
                self._log(
                    f"[ACON] Guidelines v{guideline_set.version}: "
                    f"{safe} SAFE, {unsafe} UNSAFE, "
                    f"{len(guideline_set.guidelines) - safe - unsafe} CAUTION/INSUFFICIENT"
                )
        else:
            remaining = AconGuidelineLearner.MIN_RUNS - run_count
            self._log(
                f"[ACON] {run_count}/{AconGuidelineLearner.MIN_RUNS} runs for "
                f"'{domain}'. {remaining} more needed for guidelines."
            )

        return result
