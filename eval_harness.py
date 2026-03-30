#!/usr/bin/env python3
"""
Evaluation harness: measures quality lift of the rubric loop vs. vanilla Claude.

For each of the 10 sample task domains, runs:
  1. Baseline — single-shot Claude call (no rubric, no iteration)
  2. Harness  — full rubric gen-verify loop

Both outputs are then scored against the SAME rubric (the sample rubric for
that domain) using an isolated scorer, producing directly comparable numbers.

Usage:
    python3 eval_harness.py                              # all 10 tasks, unlimited iters
    python3 eval_harness.py --tasks cold_outreach_email,csv_parser
    python3 eval_harness.py --max-iter 3
    python3 eval_harness.py --output results/my_run.json
    python3 eval_harness.py --baseline-only
    python3 eval_harness.py --harness-only               # requires prior baseline run
    python3 eval_harness.py --resume                     # skip completed tasks
"""

from __future__ import annotations

import argparse
import asyncio
import atexit
import json
import signal
import statistics
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import anthropic
import httpx

# Ensure project root is importable
sys.path.insert(0, str(Path(__file__).parent))

from rubric_system.models import CriterionScore, Rubric
from rubric_system.sample_rubrics import SAMPLE_TASKS
from rubric_system.checkpoint_policy import DEFAULT_MAX_ITERATIONS
from rubric_harness import RubricLoop

# ──────────────────────────────────────────────────────────────────────────────
# Constants
# ──────────────────────────────────────────────────────────────────────────────

DEFAULT_MODEL = "claude-sonnet-4-20250514"
DEFAULT_MAX_ITER = DEFAULT_MAX_ITERATIONS  # single source of truth in checkpoint_policy
DEFAULT_OUTPUT = "eval_results.json"

# Pricing per 1M tokens (claude-sonnet-4 as of 2026-03)
PRICE_INPUT_PER_MTOK = 3.00    # $3.00 / MTok
PRICE_OUTPUT_PER_MTOK = 15.00  # $15.00 / MTok

# Rough per-iteration cost estimate for the harness (no exact tracking)
# Typical: rubric negotiation + generation + scoring + feedback ≈ these figures
HARNESS_EST_INPUT_PER_ITER = 8_000
HARNESS_EST_OUTPUT_PER_ITER = 1_500

ALL_TASK_KEYS: List[str] = list(SAMPLE_TASKS.keys())


# ──────────────────────────────────────────────────────────────────────────────
# Data classes
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class CriterionResult:
    criterion_id: str
    category: str
    points_earned: float
    max_points: int
    percentage: float
    evidence: str = ""


@dataclass
class RunResult:
    """Score and metadata for one run (baseline or harness)."""
    output: str
    score: float
    max_score: int
    percentage: float
    criterion_results: List[CriterionResult]
    wall_seconds: float
    # Baseline-only fields
    input_tokens: int = 0
    output_tokens: int = 0
    # Harness-only fields
    iterations: int = 0
    improvement_summary: List[str] = field(default_factory=list)


@dataclass
class TaskEvalResult:
    task_key: str
    task_prompt: str
    rubric_domain: str
    rubric_criteria_count: int
    rubric_max_points: int
    baseline: Optional[RunResult] = None
    harness: Optional[RunResult] = None
    error: Optional[str] = None

    @property
    def delta(self) -> Optional[float]:
        if self.baseline and self.harness:
            return self.harness.percentage - self.baseline.percentage
        return None


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def _cs_to_criterion_result(cs: CriterionScore, rubric: Rubric) -> CriterionResult:
    category = next(
        (c.category for c in rubric.criteria if c.id == cs.criterion_id), ""
    )
    return CriterionResult(
        criterion_id=cs.criterion_id,
        category=category,
        points_earned=cs.points_earned,
        max_points=cs.max_points,
        percentage=cs.percentage,
        evidence=cs.evidence,
    )


def cost_usd(input_tok: int, output_tok: int) -> float:
    return (input_tok / 1_000_000 * PRICE_INPUT_PER_MTOK
            + output_tok / 1_000_000 * PRICE_OUTPUT_PER_MTOK)


# ──────────────────────────────────────────────────────────────────────────────
# Serialization
# ──────────────────────────────────────────────────────────────────────────────

def _run_result_to_dict(r: RunResult) -> Dict[str, Any]:
    d = asdict(r)
    return d


def _run_result_from_dict(d: Dict[str, Any]) -> RunResult:
    return RunResult(
        output=d["output"],
        score=d["score"],
        max_score=d["max_score"],
        percentage=d["percentage"],
        criterion_results=[CriterionResult(**cr) for cr in d["criterion_results"]],
        wall_seconds=d["wall_seconds"],
        input_tokens=d.get("input_tokens", 0),
        output_tokens=d.get("output_tokens", 0),
        iterations=d.get("iterations", 0),
        improvement_summary=d.get("improvement_summary", []),
    )


def _task_result_to_dict(tr: TaskEvalResult) -> Dict[str, Any]:
    d: Dict[str, Any] = {
        "task_key": tr.task_key,
        "task_prompt": tr.task_prompt,
        "rubric_domain": tr.rubric_domain,
        "rubric_criteria_count": tr.rubric_criteria_count,
        "rubric_max_points": tr.rubric_max_points,
    }
    if tr.error:
        d["error"] = tr.error
    if tr.baseline:
        d["baseline"] = _run_result_to_dict(tr.baseline)
    if tr.harness:
        d["harness"] = _run_result_to_dict(tr.harness)
    if tr.delta is not None:
        d["delta"] = tr.delta
    return d


def _task_result_from_dict(d: Dict[str, Any]) -> TaskEvalResult:
    tr = TaskEvalResult(
        task_key=d["task_key"],
        task_prompt=d["task_prompt"],
        rubric_domain=d["rubric_domain"],
        rubric_criteria_count=d["rubric_criteria_count"],
        rubric_max_points=d["rubric_max_points"],
        error=d.get("error"),
    )
    if "baseline" in d:
        tr.baseline = _run_result_from_dict(d["baseline"])
    if "harness" in d:
        tr.harness = _run_result_from_dict(d["harness"])
    return tr


def load_results(path: Path) -> Dict[str, TaskEvalResult]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text())
        task_data = data.get("task_results", data)
        return {k: _task_result_from_dict(v) for k, v in task_data.items()}
    except Exception as exc:
        print(f"[warn] Could not load existing results from {path}: {exc}")
        return {}


def save_results(task_results: Dict[str, TaskEvalResult], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    out: Dict[str, Any] = {
        "task_results": {k: _task_result_to_dict(v) for k, v in task_results.items()}
    }
    path.write_text(json.dumps(out, indent=2))


# ──────────────────────────────────────────────────────────────────────────────
# Scoring helper
# ──────────────────────────────────────────────────────────────────────────────

async def score_against_rubric(
    scorer: RubricLoop,
    output: str,
    rubric: Rubric,
) -> Tuple[float, int, List[CriterionResult]]:
    """Score `output` against `rubric` using the shared scorer and return
    (total, max_total, criterion_results)."""
    total, max_total, criterion_scores, _ = await scorer.score_content(output, rubric)
    cr_list = [_cs_to_criterion_result(cs, rubric) for cs in criterion_scores]
    return float(total), int(max_total), cr_list


# ──────────────────────────────────────────────────────────────────────────────
# Baseline generation
# ──────────────────────────────────────────────────────────────────────────────

async def generate_baseline(
    client: anthropic.Anthropic,
    scorer: RubricLoop,
    rubric: Rubric,
    model: str,
    verbose: bool,
) -> RunResult:
    """Single-shot generation with no rubric context, then score."""
    task_prompt = rubric.task

    if verbose:
        print(f"  [baseline] generating…")

    t0 = time.monotonic()
    response = client.messages.create(
        model=model,
        max_tokens=4096,
        temperature=0,
        messages=[{"role": "user", "content": task_prompt}],
    )
    gen_secs = time.monotonic() - t0

    output = response.content[0].text
    input_tok = response.usage.input_tokens
    output_tok = response.usage.output_tokens

    if verbose:
        print(f"  [baseline] {len(output)} chars | {input_tok} in / {output_tok} out | {gen_secs:.1f}s")
        print(f"  [baseline] scoring…")

    t1 = time.monotonic()
    total, max_total, cr_list = await score_against_rubric(scorer, output, rubric)
    score_secs = time.monotonic() - t1
    pct = total / max_total if max_total > 0 else 0.0

    if verbose:
        print(f"  [baseline] {total:.1f}/{max_total} ({pct:.1%}) | scoring {score_secs:.1f}s")

    return RunResult(
        output=output,
        score=total,
        max_score=max_total,
        percentage=pct,
        criterion_results=cr_list,
        wall_seconds=gen_secs + score_secs,
        input_tokens=input_tok,
        output_tokens=output_tok,
    )


# ──────────────────────────────────────────────────────────────────────────────
# Harness run
# ──────────────────────────────────────────────────────────────────────────────

async def run_harness(
    scorer: RubricLoop,
    rubric: Rubric,
    max_iter: int,
    model: str,
    verbose: bool,
) -> RunResult:
    """Full rubric loop run, then re-score final output against sample rubric."""
    task_prompt = rubric.task

    if verbose:
        print(f"  [harness] starting loop (max_iter={max_iter})…")

    loop = RubricLoop(
        model=model,
        max_iterations=max_iter,
        verbose=verbose,
        enable_self_improve=False,   # don't rewrite harness code during eval
        enable_checkpoints=False,    # no human pauses during eval
        enable_research=False,       # rubric already provided; skip research step
        skip_negotiation=True,               # eval: use sample rubric as-is
        enable_tradeoff_detection=False,     # eval: don't drop/merge criteria
        enable_quality_gate=False,           # eval: don't drop/merge criteria
        feedback_dir=".eval_feedback",
        iterations_dir=".eval_iterations",
    )

    t0 = time.monotonic()
    loop_result = await loop.run(
        task=task_prompt,
        rubric=rubric,
        generate_rubric=False,  # use the sample rubric directly
    )
    harness_secs = time.monotonic() - t0

    if verbose:
        print(f"  [harness] loop done: {loop_result.final_percentage:.1%} "
              f"in {loop_result.iterations} iter / {harness_secs:.1f}s")
        print(f"  [harness] re-scoring final output for fair comparison…")

    # Re-score against the ORIGINAL sample rubric — since we now disable negotiation,
    # tradeoff detection, and quality gate, the loop rubric should be identical to the
    # sample rubric. Always use the caller's rubric for a fair apples-to-apples comparison.
    t1 = time.monotonic()
    total, max_total, cr_list = await score_against_rubric(scorer, loop_result.output, rubric)
    rescore_secs = time.monotonic() - t1
    pct = total / max_total if max_total > 0 else 0.0

    if verbose:
        print(f"  [harness] re-scored: {total:.1f}/{max_total} ({pct:.1%}) | {rescore_secs:.1f}s")

    return RunResult(
        output=loop_result.output,
        score=total,
        max_score=max_total,
        percentage=pct,
        criterion_results=cr_list,
        wall_seconds=harness_secs + rescore_secs,
        iterations=loop_result.iterations,
        improvement_summary=loop_result.improvement_summary,
    )


# ──────────────────────────────────────────────────────────────────────────────
# Markdown report
# ──────────────────────────────────────────────────────────────────────────────

def generate_markdown_report(
    task_results: Dict[str, TaskEvalResult],
    max_iter: int,
    model: str,
) -> str:
    lines: List[str] = []
    ts = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime())
    lines += [
        "# Eval Results: Rubric Harness vs. Vanilla Claude",
        "",
        f"**Generated:** {ts}  ",
        f"**Model:** `{model}`  ",
        f"**Max harness iterations:** {max_iter}",
        "",
    ]

    # ── Per-task table ──
    lines += [
        "## Per-Task Results",
        "",
        "| Task | Domain | Baseline % | Harness % | Delta | Iters | Base Time | Harness Time |",
        "|------|--------|:----------:|:---------:|:-----:|:-----:|:---------:|:------------:|",
    ]
    deltas: List[float] = []
    for key, tr in task_results.items():
        base_pct = f"{tr.baseline.percentage:.1%}" if tr.baseline else "—"
        harn_pct = f"{tr.harness.percentage:.1%}" if tr.harness else "—"
        delta_str = f"{tr.delta:+.1%}" if tr.delta is not None else "—"
        iters = str(tr.harness.iterations) if tr.harness else "—"
        base_t = f"{tr.baseline.wall_seconds:.0f}s" if tr.baseline else "—"
        harn_t = f"{tr.harness.wall_seconds:.0f}s" if tr.harness else "—"
        lines.append(
            f"| {key} | {tr.rubric_domain} | {base_pct} | {harn_pct} | {delta_str} "
            f"| {iters} | {base_t} | {harn_t} |"
        )
        if tr.delta is not None:
            deltas.append(tr.delta)

    # ── Aggregate stats ──
    if deltas:
        mean_lift = statistics.mean(deltas)
        median_lift = statistics.median(deltas)
        stdev_lift = statistics.stdev(deltas) if len(deltas) > 1 else 0.0
        improved = sum(1 for d in deltas if d > 0.01)
        neutral = sum(1 for d in deltas if -0.01 <= d <= 0.01)
        regressed = sum(1 for d in deltas if d < -0.01)

        lines += [
            "",
            "## Aggregate Statistics",
            "",
            "| Metric | Value |",
            "|--------|-------|",
            f"| Tasks evaluated | {len(deltas)} |",
            f"| Mean lift | **{mean_lift:+.1%}** |",
            f"| Median lift | {median_lift:+.1%} |",
            f"| Std dev | {stdev_lift:.1%} |",
            f"| Improved (>1%) | {improved}/{len(deltas)} |",
            f"| Neutral (±1%) | {neutral}/{len(deltas)} |",
            f"| Regressed (<-1%) | {regressed}/{len(deltas)} |",
        ]

    # ── Per-criterion lift (top 15 by avg lift) ──
    crit_lifts: Dict[str, List[float]] = {}
    crit_cats: Dict[str, str] = {}
    for tr in task_results.values():
        if not tr.baseline or not tr.harness:
            continue
        base_map = {cr.criterion_id: cr for cr in tr.baseline.criterion_results}
        for hcr in tr.harness.criterion_results:
            bcr = base_map.get(hcr.criterion_id)
            if bcr is None:
                continue
            lift = hcr.percentage - bcr.percentage
            if hcr.criterion_id not in crit_lifts:
                crit_lifts[hcr.criterion_id] = []
                crit_cats[hcr.criterion_id] = hcr.category
            crit_lifts[hcr.criterion_id].append(lift)

    if crit_lifts:
        sorted_crits = sorted(
            crit_lifts.items(),
            key=lambda kv: statistics.mean(kv[1]),
            reverse=True,
        )
        lines += [
            "",
            "## Per-Criterion Lift (top 15 by avg lift across tasks)",
            "",
            "| Criterion | Category | Avg Lift | Appearances |",
            "|-----------|----------|:--------:|:-----------:|",
        ]
        for crit_id, lifts in sorted_crits[:15]:
            cat = crit_cats.get(crit_id, "")
            avg = statistics.mean(lifts)
            lines.append(f"| {crit_id} | {cat} | {avg:+.1%} | {len(lifts)} |")

    # ── Cost & token comparison ──
    completed = [tr for tr in task_results.values() if tr.baseline and tr.harness]
    n_base = sum(1 for tr in task_results.values() if tr.baseline)
    n_harn = sum(1 for tr in task_results.values() if tr.harness)

    base_in = sum(tr.baseline.input_tokens for tr in task_results.values() if tr.baseline)
    base_out = sum(tr.baseline.output_tokens for tr in task_results.values() if tr.baseline)
    base_cost = cost_usd(base_in, base_out)
    base_secs = sum(tr.baseline.wall_seconds for tr in task_results.values() if tr.baseline)
    harn_secs = sum(tr.harness.wall_seconds for tr in task_results.values() if tr.harness)

    avg_iters = (
        statistics.mean([tr.harness.iterations for tr in task_results.values() if tr.harness])
        if n_harn else 0.0
    )
    # Estimated harness token totals
    est_harn_in = int(sum(
        tr.harness.iterations * HARNESS_EST_INPUT_PER_ITER
        for tr in task_results.values() if tr.harness
    ))
    est_harn_out = int(sum(
        tr.harness.iterations * HARNESS_EST_OUTPUT_PER_ITER
        for tr in task_results.values() if tr.harness
    ))
    est_harn_cost = cost_usd(est_harn_in, est_harn_out)

    lines += [
        "",
        "## Cost & Token Comparison",
        "",
        "| Metric | Baseline | Harness |",
        "|--------|----------|---------|",
        f"| Tasks with data | {n_base} | {n_harn} |",
        f"| Total wall time | {base_secs:.0f}s | {harn_secs:.0f}s |",
        f"| Avg time / task | {base_secs/n_base:.0f}s | {harn_secs/n_harn:.0f}s |"
        if n_base and n_harn else "| Avg time / task | — | — |",
        f"| Input tokens (total) | {base_in:,} | ~{est_harn_in:,} (est.) |",
        f"| Output tokens (total) | {base_out:,} | ~{est_harn_out:,} (est.) |",
        f"| Est. cost (USD) | ${base_cost:.4f} | ~${est_harn_cost:.4f} (est.) |",
        f"| Avg iterations | 1 | {avg_iters:.1f} |",
        "",
        "> Harness token/cost figures are estimates based on "
        f"{HARNESS_EST_INPUT_PER_ITER:,} input + {HARNESS_EST_OUTPUT_PER_ITER:,} output "
        "tokens per iteration. Actual usage varies.",
    ]

    return "\n".join(lines)


# ──────────────────────────────────────────────────────────────────────────────
# Artifact recovery: reconstruct harness result from iteration files
# ──────────────────────────────────────────────────────────────────────────────

def recover_harness_from_artifacts(
    task_key: str,
    iterations_dir: str = ".eval_iterations",
) -> Optional[RunResult]:
    """Scan iteration artifacts for the best completed iteration and reconstruct a RunResult.

    Used on resume when the harness ran but the result was never captured (e.g. process killed).
    Returns None if no usable artifacts are found.
    """
    idir = Path(iterations_dir)
    if not idir.exists():
        return None

    # Find all run directories, pick the most recent one that has iteration artifacts
    best_result: Optional[RunResult] = None
    best_pct = -1.0

    for run_dir in sorted(idir.iterdir(), reverse=True):
        if not run_dir.is_dir():
            continue

        # Read all iter_NNN_meta.json files in this directory
        meta_files = sorted(run_dir.glob("iter_*_meta.json"))
        if not meta_files:
            continue

        # Check if the rubric.json in this dir matches the task (by reading it)
        rubric_file = run_dir / "rubric.json"
        if rubric_file.exists():
            try:
                rubric_data = json.loads(rubric_file.read_text())
                rubric_task = rubric_data.get("task", "")
                # Match by checking if the task_key appears in the rubric's task or domain
                rubric_domain = rubric_data.get("domain", "")
                if task_key not in rubric_domain and task_key.replace("_", " ") not in rubric_task.lower():
                    continue
            except Exception:
                continue
        else:
            continue

        # Find the best-scoring iteration in this run
        for meta_path in meta_files:
            try:
                meta = json.loads(meta_path.read_text())
                pct = meta.get("percentage", 0.0)
                if pct <= best_pct:
                    continue

                # Read the content file
                content_path = meta.get("content_path", "")
                if content_path:
                    content_file = Path(content_path)
                else:
                    content_file = meta_path.with_name(
                        meta_path.name.replace("_meta.json", "_content.md")
                    )

                if not content_file.exists():
                    continue

                content = content_file.read_text()
                if not content.strip():
                    continue

                # Build criterion results from meta
                cr_list = []
                for cs in meta.get("criterion_scores", []):
                    cr_list.append(CriterionResult(
                        criterion_id=cs["criterion_id"],
                        category="",
                        points_earned=cs["points_earned"],
                        max_points=cs["max_points"],
                        percentage=cs.get("percentage", 0.0),
                        evidence="(recovered from iteration artifacts)",
                    ))

                iteration_num = meta.get("iteration", 0)
                best_result = RunResult(
                    output=content,
                    score=meta.get("total_score", 0.0),
                    max_score=meta.get("max_score", 0),
                    percentage=pct,
                    criterion_results=cr_list,
                    wall_seconds=0.0,  # unknown from artifacts
                    iterations=iteration_num,
                    improvement_summary=[f"(recovered from artifacts, iter {iteration_num})"],
                )
                best_pct = pct
            except Exception:
                continue

        # Only check the most recent matching run directory
        if best_result is not None:
            break

    return best_result


# ──────────────────────────────────────────────────────────────────────────────
# Main eval loop
# ──────────────────────────────────────────────────────────────────────────────

async def run_eval(
    task_keys: List[str],
    max_iter: int,
    output_path: Path,
    baseline_only: bool,
    harness_only: bool,
    resume: bool,
    model: str,
    verbose: bool,
) -> Dict[str, TaskEvalResult]:
    client = anthropic.Anthropic(timeout=httpx.Timeout(600.0, connect=30.0))

    # Shared scorer: used ONLY for score_content() calls (no loop runs).
    # Isolated feedback dir so eval scoring doesn't bleed into production feedback.
    scorer = RubricLoop(
        model=model,
        verbose=False,
        enable_self_improve=False,
        enable_checkpoints=False,
        enable_research=False,
        feedback_dir=".eval_scorer_feedback",
        iterations_dir=".eval_scorer_iterations",
    )

    # Load existing results when resuming
    task_results: Dict[str, TaskEvalResult] = {}
    if resume:
        task_results = load_results(output_path)
        if task_results:
            print(f"[resume] loaded {len(task_results)} existing results from {output_path}")

    # Safety net: persist results on SIGTERM / atexit so interrupted runs don't lose data
    def _save_on_exit():
        try:
            if task_results:
                save_results(task_results, output_path)
                print(f"\n[atexit] saved {len(task_results)} results to {output_path}")
        except Exception:
            pass  # best-effort; don't raise during shutdown

    atexit.register(_save_on_exit)

    def _sigterm_handler(signum, frame):
        print(f"\n[signal] received signal {signum}, saving results…")
        _save_on_exit()
        sys.exit(1)

    signal.signal(signal.SIGTERM, _sigterm_handler)

    total_tasks = len(task_keys)
    for idx, task_key in enumerate(task_keys, 1):
        print(f"\n{'='*60}")
        print(f"[{idx}/{total_tasks}] {task_key}")
        print(f"{'='*60}")

        existing = task_results.get(task_key)

        # Build the canonical sample rubric for this task
        rubric: Rubric = SAMPLE_TASKS[task_key]()

        # Determine what to run
        do_base = not harness_only
        do_harn = not baseline_only

        if resume and existing:
            if existing.baseline and do_base:
                print(f"  [skip] baseline already done ({existing.baseline.percentage:.1%})")
                do_base = False
            if existing.harness and do_harn:
                print(f"  [skip] harness already done ({existing.harness.percentage:.1%})")
                do_harn = False
            # Recover harness from iteration artifacts if missing (e.g. process was killed)
            if not existing.harness and do_harn and not existing.error:
                recovered = recover_harness_from_artifacts(task_key, ".eval_iterations")
                if recovered:
                    print(f"  [recovered] harness from iteration artifacts: {recovered.percentage:.1%}")
                    existing.harness = recovered
                    existing.error = None
                    save_results(task_results, output_path)
                    do_harn = False
            if not do_base and not do_harn:
                continue

        if existing is None:
            existing = TaskEvalResult(
                task_key=task_key,
                task_prompt=rubric.task,
                rubric_domain=rubric.domain,
                rubric_criteria_count=len(rubric.criteria),
                rubric_max_points=rubric.total_points,
            )
            task_results[task_key] = existing

        try:
            if do_base:
                existing.baseline = await generate_baseline(
                    client=client,
                    scorer=scorer,
                    rubric=rubric,
                    model=model,
                    verbose=verbose,
                )
                save_results(task_results, output_path)

            if do_harn:
                existing.harness = await run_harness(
                    scorer=scorer,
                    rubric=rubric,
                    max_iter=max_iter,
                    model=model,
                    verbose=verbose,
                )
                save_results(task_results, output_path)

            # In harness-only mode with existing baseline: re-score the stored
            # baseline output against the same rubric for a fair comparison.
            if harness_only and existing.baseline and existing.harness:
                print(f"  [harness-only] re-scoring stored baseline output…")
                total, max_total, cr_list = await score_against_rubric(
                    scorer, existing.baseline.output, rubric
                )
                pct = total / max_total if max_total > 0 else 0.0
                existing.baseline.score = total
                existing.baseline.max_score = max_total
                existing.baseline.percentage = pct
                existing.baseline.criterion_results = cr_list
                save_results(task_results, output_path)

            delta_str = f"{existing.delta:+.1%}" if existing.delta is not None else "N/A"
            print(f"  → delta: {delta_str}")

        except Exception as exc:
            print(f"  [ERROR] {task_key}: {exc}")
            existing.error = str(exc)
            save_results(task_results, output_path)

    return task_results


# ──────────────────────────────────────────────────────────────────────────────
# JSON summary (aggregate metrics for machine consumption)
# ──────────────────────────────────────────────────────────────────────────────

def build_json_summary(
    task_results: Dict[str, TaskEvalResult],
    max_iter: int,
    model: str,
) -> Dict[str, Any]:
    deltas = [tr.delta for tr in task_results.values() if tr.delta is not None]
    base_pcts = [tr.baseline.percentage for tr in task_results.values() if tr.baseline]
    harn_pcts = [tr.harness.percentage for tr in task_results.values() if tr.harness]

    base_in = sum(tr.baseline.input_tokens for tr in task_results.values() if tr.baseline)
    base_out = sum(tr.baseline.output_tokens for tr in task_results.values() if tr.baseline)
    avg_iters = statistics.mean(
        [tr.harness.iterations for tr in task_results.values() if tr.harness]
    ) if any(tr.harness for tr in task_results.values()) else 0.0
    est_harn_in = int(avg_iters * len([t for t in task_results.values() if t.harness])
                      * HARNESS_EST_INPUT_PER_ITER)
    est_harn_out = int(avg_iters * len([t for t in task_results.values() if t.harness])
                       * HARNESS_EST_OUTPUT_PER_ITER)

    return {
        "meta": {
            "model": model,
            "max_harness_iter": max_iter,
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        },
        "aggregate": {
            "tasks_evaluated": len(deltas),
            "mean_lift": statistics.mean(deltas) if deltas else None,
            "median_lift": statistics.median(deltas) if deltas else None,
            "stdev_lift": statistics.stdev(deltas) if len(deltas) > 1 else 0.0,
            "min_lift": min(deltas) if deltas else None,
            "max_lift": max(deltas) if deltas else None,
            "tasks_improved": sum(1 for d in deltas if d > 0.01),
            "tasks_neutral": sum(1 for d in deltas if -0.01 <= d <= 0.01),
            "tasks_regressed": sum(1 for d in deltas if d < -0.01),
            "mean_baseline_pct": statistics.mean(base_pcts) if base_pcts else None,
            "mean_harness_pct": statistics.mean(harn_pcts) if harn_pcts else None,
        },
        "cost": {
            "baseline_input_tokens": base_in,
            "baseline_output_tokens": base_out,
            "baseline_cost_usd": cost_usd(base_in, base_out),
            "harness_est_input_tokens": est_harn_in,
            "harness_est_output_tokens": est_harn_out,
            "harness_est_cost_usd": cost_usd(est_harn_in, est_harn_out),
            "avg_harness_iterations": avg_iters,
        },
        "per_task": {
            key: {
                "delta": tr.delta,
                "baseline_pct": tr.baseline.percentage if tr.baseline else None,
                "harness_pct": tr.harness.percentage if tr.harness else None,
                "harness_iterations": tr.harness.iterations if tr.harness else None,
                "baseline_wall_secs": tr.baseline.wall_seconds if tr.baseline else None,
                "harness_wall_secs": tr.harness.wall_seconds if tr.harness else None,
                "baseline_tokens_in": tr.baseline.input_tokens if tr.baseline else None,
                "baseline_tokens_out": tr.baseline.output_tokens if tr.baseline else None,
                "error": tr.error,
            }
            for key, tr in task_results.items()
        },
        "per_criterion": _build_per_criterion_summary(task_results),
    }


def _build_per_criterion_summary(
    task_results: Dict[str, TaskEvalResult],
) -> List[Dict[str, Any]]:
    crit_data: Dict[str, Dict[str, Any]] = {}
    for tr in task_results.values():
        if not tr.baseline or not tr.harness:
            continue
        base_map = {cr.criterion_id: cr for cr in tr.baseline.criterion_results}
        for hcr in tr.harness.criterion_results:
            bcr = base_map.get(hcr.criterion_id)
            if bcr is None:
                continue
            if hcr.criterion_id not in crit_data:
                crit_data[hcr.criterion_id] = {
                    "criterion_id": hcr.criterion_id,
                    "category": hcr.category,
                    "task": tr.task_key,
                    "lifts": [],
                    "baseline_pcts": [],
                    "harness_pcts": [],
                }
            crit_data[hcr.criterion_id]["lifts"].append(hcr.percentage - bcr.percentage)
            crit_data[hcr.criterion_id]["baseline_pcts"].append(bcr.percentage)
            crit_data[hcr.criterion_id]["harness_pcts"].append(hcr.percentage)

    result = []
    for entry in crit_data.values():
        lifts = entry["lifts"]
        result.append({
            "criterion_id": entry["criterion_id"],
            "category": entry["category"],
            "task": entry["task"],
            "avg_lift": statistics.mean(lifts),
            "avg_baseline_pct": statistics.mean(entry["baseline_pcts"]),
            "avg_harness_pct": statistics.mean(entry["harness_pcts"]),
            "appearances": len(lifts),
        })

    return sorted(result, key=lambda x: x["avg_lift"], reverse=True)


# ──────────────────────────────────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Measure quality lift of the rubric harness vs. vanilla Claude.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument(
        "--tasks",
        default=",".join(ALL_TASK_KEYS),
        help=f"Comma-separated task keys to evaluate. Defaults to all 10. "
             f"Available: {', '.join(ALL_TASK_KEYS)}",
    )
    p.add_argument(
        "--max-iter",
        type=int,
        default=DEFAULT_MAX_ITER,
        dest="max_iter",
        help=f"Max harness iterations per task (0 = unlimited, default: {DEFAULT_MAX_ITER})",
    )
    p.add_argument(
        "--output",
        default=DEFAULT_OUTPUT,
        help=f"Path for JSON results file (default: {DEFAULT_OUTPUT}). "
             "A .md summary is written alongside it.",
    )
    p.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help=f"Claude model to use (default: {DEFAULT_MODEL})",
    )
    p.add_argument(
        "--baseline-only",
        action="store_true",
        dest="baseline_only",
        help="Only run baseline generation (skip harness). Saves outputs for later --harness-only.",
    )
    p.add_argument(
        "--harness-only",
        action="store_true",
        dest="harness_only",
        help="Only run harness. Re-scores any existing baseline from the output file.",
    )
    p.add_argument(
        "--resume",
        action="store_true",
        help="Resume a previous run — skip tasks already present in the output file.",
    )
    p.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress per-step progress output.",
    )
    return p.parse_args()


async def main() -> None:
    args = parse_args()

    if args.baseline_only and args.harness_only:
        print("Error: --baseline-only and --harness-only are mutually exclusive.")
        sys.exit(1)

    task_keys = [k.strip() for k in args.tasks.split(",") if k.strip()]
    unknown = [k for k in task_keys if k not in SAMPLE_TASKS]
    if unknown:
        print(f"Error: unknown task key(s): {', '.join(unknown)}")
        print(f"Available: {', '.join(ALL_TASK_KEYS)}")
        sys.exit(1)

    output_path = Path(args.output)
    verbose = not args.quiet

    print(f"Eval harness — rubric loop vs. vanilla Claude")
    print(f"  Model:    {args.model}")
    print(f"  Tasks:    {len(task_keys)} ({', '.join(task_keys)})")
    print(f"  Max iter: {args.max_iter}")
    print(f"  Output:   {output_path}")
    mode = ("baseline-only" if args.baseline_only
            else "harness-only" if args.harness_only
            else "full")
    print(f"  Mode:     {mode}")
    if args.resume:
        print(f"  Resume:   yes")

    task_results = await run_eval(
        task_keys=task_keys,
        max_iter=args.max_iter,
        output_path=output_path,
        baseline_only=args.baseline_only,
        harness_only=args.harness_only,
        resume=args.resume,
        model=args.model,
        verbose=verbose,
    )

    # Write full results JSON (task_results already saved incrementally; this adds summary)
    summary = build_json_summary(task_results, args.max_iter, args.model)
    final_json: Dict[str, Any] = {
        "summary": summary,
        "task_results": {k: _task_result_to_dict(v) for k, v in task_results.items()},
    }
    output_path.write_text(json.dumps(final_json, indent=2))
    print(f"\n[done] JSON results → {output_path}")

    # Write markdown report
    md = generate_markdown_report(task_results, args.max_iter, args.model)
    md_path = output_path.with_suffix(".md")
    md_path.write_text(md)
    print(f"[done] Markdown report → {md_path}")

    # Print aggregate summary to stdout
    agg = summary["aggregate"]
    if agg["tasks_evaluated"] > 0:
        print(f"\n── Aggregate Results ──────────────────────")
        print(f"  Tasks evaluated : {agg['tasks_evaluated']}")
        print(f"  Mean lift       : {agg['mean_lift']:+.1%}")
        print(f"  Median lift     : {agg['median_lift']:+.1%}")
        print(f"  Std dev         : {agg['stdev_lift']:.1%}")
        print(f"  Improved / total: {agg['tasks_improved']}/{agg['tasks_evaluated']}")
        print(f"  Baseline avg %  : {agg['mean_baseline_pct']:.1%}")
        print(f"  Harness avg %   : {agg['mean_harness_pct']:.1%}")
        print(f"──────────────────────────────────────────")


if __name__ == "__main__":
    asyncio.run(main())
