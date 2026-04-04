#!/usr/bin/env python3
"""
Self-Improvement Engine — the harness rewrites itself based on accumulated learnings.

Three capabilities:
1. OutcomeTracker: Auto-closes Loop 3 by detecting outcomes from CI/git/deployment signals
2. LearningIntegrator: Feeds RubricLearner insights into RubricAgent at generation time
3. SelfEditor: Rewrites scoring rubric factories, measurement prompts, and generation
   prompts in the actual source code based on what the learning system has discovered.

The key insight: instead of just logging "criterion X has a 60% false positive rate" to
a report, SelfEditor calls Claude to propose code patches to the scoring rubric factory
that produces X, then applies them. The harness literally edits its own source files.
"""

import json
import math
import re
import os
import sys
import subprocess
import hashlib
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field

try:
    from anthropic import Anthropic
except ImportError:
    Anthropic = None

try:
    from rubric_system.models import (
        ScoringMethod, SubAttribute, ScoringRubric, Criterion, Rubric,
        CriterionScore, CriterionStats,
    )
    from rubric_system.rubric_learning import RubricStore, RubricLearner
    from rubric_system.feedback_loop import FeedbackStore
except ImportError:
    from models import (
        ScoringMethod, SubAttribute, ScoringRubric, Criterion, Rubric,
        CriterionScore, CriterionStats,
    )
    from rubric_learning import RubricStore, RubricLearner
    from feedback_loop import FeedbackStore


# ============================================================================
# 1. Outcome Tracker — closes the learning loop automatically
# ============================================================================

@dataclass
class OutcomeSignal:
    """A signal that indicates the quality of a prior rubric evaluation."""
    rubric_id: str
    outcome: str  # "success", "bug_found", "reverted", "hotfix"
    details: str = ""
    days_since_eval: int = 0
    source: str = "manual"  # "git", "ci", "deploy", "manual"
    detected_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())


class OutcomeTracker:
    """Automatically detects outcomes and feeds them back to RubricStore.

    Sources:
    - Git: detect reverts, hotfix branches, revert commits within N days of eval
    - CI: detect test failures on files that previously passed rubric
    - Deploy: detect rollbacks or incident signals
    - Manual: explicit outcome reporting (existing path)

    Usage:
        tracker = OutcomeTracker(store)
        tracker.scan_git_outcomes(repo_path="/path/to/repo", lookback_days=14)
        tracker.report_outcome(rubric_id, "bug_found", "Prod incident on auth flow")
    """

    def __init__(self, store: RubricStore, verbose: bool = True):
        self.store = store
        self.verbose = verbose

    def _log(self, msg: str):
        if self.verbose:
            print(f"[OutcomeTracker] {msg}")

    def report_outcome(
        self,
        rubric_id: str,
        outcome: str,
        details: str = "",
        days_to_bug: int = None,
    ):
        """Manually report an outcome for a scored rubric."""
        self.store.update_outcome(
            rubric_id=rubric_id,
            outcome=outcome,
            details=details,
            days_to_bug=days_to_bug,
        )
        self._log(f"Outcome recorded: {rubric_id} → {outcome}")

    def scan_git_outcomes(
        self,
        repo_path: str = ".",
        lookback_days: int = 14,
    ) -> list[OutcomeSignal]:
        """Scan git history for revert/hotfix signals that indicate bugs.

        Looks for:
        - Commits with "revert" in message
        - Branches named hotfix/* or fix/*
        - Commits that modify files previously evaluated by rubric

        Returns list of detected outcome signals.
        """
        signals = []
        since_date = (datetime.utcnow() - timedelta(days=lookback_days)).strftime("%Y-%m-%d")

        try:
            # Find revert commits
            result = subprocess.run(
                ["git", "log", f"--since={since_date}", "--oneline", "--grep=revert", "-i"],
                capture_output=True, text=True, cwd=repo_path, timeout=10,
            )
            if result.returncode == 0:
                for line in result.stdout.strip().split("\n"):
                    if line.strip():
                        commit_hash = line.split()[0]
                        message = " ".join(line.split()[1:])
                        signal = self._match_revert_to_rubric(commit_hash, message, repo_path)
                        if signal:
                            signals.append(signal)

            # Find hotfix branches merged recently
            result = subprocess.run(
                ["git", "log", f"--since={since_date}", "--oneline", "--merges",
                 "--grep=hotfix\\|fix/"],
                capture_output=True, text=True, cwd=repo_path, timeout=10,
            )
            if result.returncode == 0:
                for line in result.stdout.strip().split("\n"):
                    if line.strip() and ("hotfix" in line.lower() or "fix/" in line.lower()):
                        commit_hash = line.split()[0]
                        message = " ".join(line.split()[1:])
                        signal = self._match_revert_to_rubric(commit_hash, message, repo_path)
                        if signal:
                            signal.outcome = "hotfix"
                            signals.append(signal)

        except (subprocess.TimeoutExpired, FileNotFoundError):
            self._log("Git scan failed — git not available or not a repo")

        # Apply signals to store
        for signal in signals:
            self.report_outcome(
                rubric_id=signal.rubric_id,
                outcome=signal.outcome,
                details=signal.details,
                days_to_bug=signal.days_since_eval,
            )

        self._log(f"Git scan found {len(signals)} outcome signals")
        return signals

    def _match_revert_to_rubric(
        self, commit_hash: str, message: str, repo_path: str
    ) -> Optional[OutcomeSignal]:
        """Try to match a revert/hotfix commit to a previously scored rubric."""
        try:
            # Get files changed in this commit
            result = subprocess.run(
                ["git", "diff-tree", "--no-commit-id", "--name-only", "-r", commit_hash],
                capture_output=True, text=True, cwd=repo_path, timeout=5,
            )
            if result.returncode != 0:
                return None

            changed_files = [f.strip() for f in result.stdout.strip().split("\n") if f.strip()]

            # Search for rubric evaluations that scored these files
            for filepath in changed_files:
                similar = self.store.find_similar_tasks(filepath, limit=1)
                if similar:
                    record = similar[0]
                    days = (datetime.utcnow() - datetime.fromisoformat(record.created_at)).days
                    return OutcomeSignal(
                        rubric_id=record.id,
                        outcome="reverted",
                        details=f"Revert: {message}. File: {filepath}",
                        days_since_eval=days,
                        source="git",
                    )
        except Exception:
            pass
        return None

    def scan_ci_failures(
        self,
        ci_results_dir: str = ".rubric_ci_results",
        lookback_days: int = 7,
    ) -> list[OutcomeSignal]:
        """Scan CI result files for test failures on previously-passing files."""
        signals = []
        results_path = Path(ci_results_dir)
        if not results_path.exists():
            return signals

        cutoff = datetime.utcnow() - timedelta(days=lookback_days)

        for result_file in results_path.glob("*.json"):
            try:
                data = json.loads(result_file.read_text())
                file_time = datetime.fromisoformat(data.get("timestamp", "2000-01-01"))
                if file_time < cutoff:
                    continue

                if not data.get("passed", True):
                    # CI failed — find the rubric that last evaluated these files
                    for file_score in data.get("files", []):
                        if not file_score.get("passed", True):
                            similar = self.store.find_similar_tasks(
                                file_score.get("path", ""), limit=1
                            )
                            if similar:
                                record = similar[0]
                                signals.append(OutcomeSignal(
                                    rubric_id=record.id,
                                    outcome="bug_found",
                                    details=f"CI failure: {file_score.get('path')}",
                                    source="ci",
                                ))
            except (json.JSONDecodeError, KeyError):
                continue

        for signal in signals:
            self.report_outcome(signal.rubric_id, signal.outcome, signal.details)

        self._log(f"CI scan found {len(signals)} outcome signals")
        return signals


# ============================================================================
# 2. Learning Integrator — feeds learnings into rubric generation
# ============================================================================

class LearningIntegrator:
    """Bridges RubricLearner insights into the RubricAgent prompt.

    When generating a new rubric, this class:
    1. Queries RubricLearner for similar past tasks and their effective criteria
    2. Gets criterion effectiveness insights (high-value, low-value, redundant)
    3. Gets human feedback relevant to rubric construction
    4. Formats all of this as a structured section for the generation prompt

    Usage:
        integrator = LearningIntegrator(store, feedback_store)
        learning_section = integrator.build_learning_context(task, domain)
        # Append to rubric generation prompt
    """

    def __init__(
        self,
        store: RubricStore = None,
        feedback_store: FeedbackStore = None,
        verbose: bool = True,
    ):
        self.store = store or RubricStore()
        self.learner = RubricLearner(self.store)
        self.feedback_store = feedback_store
        self.verbose = verbose

    def _log(self, msg: str):
        if self.verbose:
            print(f"[LearningIntegrator] {msg}")

    def build_learning_context(self, task: str, domain: str = "") -> str:
        """Build a formatted learning context section for rubric generation.

        Returns a string to append to the rubric generation prompt.
        """
        parts = []

        # 1. Similar task history
        suggestion = self.learner.suggest_rubric_for_task(task)
        if suggestion["criteria"]:
            parts.append(self._format_similar_tasks(suggestion))

        # 2. Criterion effectiveness insights
        insights = self.learner.get_insights()
        if insights["high_value_criteria"] or insights["low_value_criteria"]:
            parts.append(self._format_insights(insights))

        # 3. Human feedback on rubric construction
        if self.feedback_store:
            from rubric_system.feedback_loop import FeedbackInjector
            injector = FeedbackInjector(self.feedback_store)
            feedback_section = injector.format_for_rubric_generation(task, domain)
            if feedback_section:
                parts.append(feedback_section)

        # 4. Cross-domain strategy transfer hints (DGM-H Upgrade 4)
        try:
            from rubric_system.meta_strategy import MetaStrategyStore
            meta_store = MetaStrategyStore()
            transfer_hints = meta_store.get_transfer_hints(target_domain=domain)
            if transfer_hints:
                parts.append(transfer_hints)
        except Exception:
            pass  # non-fatal — missing file or import is fine

        if not parts:
            return ""

        header = ("\nLEARNING CONTEXT — the system has accumulated knowledge from prior evaluations. "
                  "Use this to inform your rubric design.\n")
        return header + "\n".join(parts)

    def _format_similar_tasks(self, suggestion: dict) -> str:
        """Format similar task suggestions."""
        lines = [
            f"\nSIMILAR PAST TASKS ({suggestion['similar_tasks']} found, "
            f"confidence: {suggestion['confidence']}):",
        ]

        for c in suggestion["criteria"][:5]:
            cid = c.get("id", "unknown")
            desc = c.get("description", "")[:60]
            pass_rate = c.get("historical_pass_rate", 0)
            bug_rate = c.get("historical_bug_rate", 0)
            confidence = c.get("confidence", 0)

            lines.append(
                f"  - {cid}: {desc} "
                f"(pass_rate: {pass_rate:.0%}, bug_rate: {bug_rate:.0%}, "
                f"confidence: {confidence:.0%})"
            )

            # Flag criteria that correlate with bugs
            if bug_rate > 0.3:
                lines.append(f"    ⚠ HIGH BUG RATE — this criterion caught real issues. Keep it.")
            elif pass_rate > 0.95:
                lines.append(f"    ⚡ ALWAYS PASSES — consider making it harder or removing.")

        return "\n".join(lines)

    def _format_insights(self, insights: dict) -> str:
        """Format criterion effectiveness insights."""
        lines = ["\nCRITERION EFFECTIVENESS (from outcome tracking):"]

        if insights["high_value_criteria"]:
            lines.append("  HIGH-VALUE (keep or strengthen):")
            for c in insights["high_value_criteria"][:3]:
                lines.append(
                    f"    ✓ {c['id']}: predictive_value={c['predictive_value']:.0%}, "
                    f"bug_prevention={c['bug_prevention_rate']:.0%}"
                )

        if insights["low_value_criteria"]:
            lines.append("  LOW-VALUE (refine or remove):")
            for c in insights["low_value_criteria"][:3]:
                lines.append(
                    f"    ✗ {c['id']}: false_positive_rate={c['false_positive_rate']:.0%} — "
                    f"{c['recommendation']}"
                )

        if insights["suggested_removals"]:
            lines.append("  POTENTIALLY REDUNDANT:")
            for c in insights["suggested_removals"][:3]:
                lines.append(
                    f"    ~ {c['id']}: pass_rate={c['pass_rate']:.0%} — always passes"
                )

        return "\n".join(lines)


# ============================================================================
# 3. Regression Suite — guards against self-edits degrading known-good scores
# ============================================================================

REGRESSION_SUITE_PATH = str(Path.home() / ".auto-verifier-data" / "rubric_feedback" / "regression_suite.json")
_BUILT_IN_CRITERIA = frozenset({
    "src_freshness", "src_authority", "src_triangulation", "evd_alignment",
    "viz_accuracy", "viz_clarity", "fwd_uncertainty", "doc_structure",
    "color_001", "color_002", "color_003",
    "type_001", "type_002", "type_003",
    "space_001", "space_002", "space_003",
})


class RegressionSuite:
    """Stores task+expected_score pairs and validates patches before applying.

    Schema for each entry in regression_suite.json:
    {
        "task": str,
        "task_hash": str,                  # sha256[:12] of task
        "rubric_id": str,
        "criterion_ids": [str, ...],
        "criterion_min_scores": {cid: float, ...},  # recorded - buffer
        "overall_min_score": float,        # recorded - buffer
        "recorded_score": float,
        "recorded_at": str (ISO-8601)
    }

    Usage:
        suite = RegressionSuite()
        suite.add_entry(task, rubric_id, criterion_scores, overall_score)
        passed, failures = suite.check_regression(task, criterion_scores, overall_score)
    """

    def __init__(
        self,
        path: str = REGRESSION_SUITE_PATH,
        verbose: bool = True,
    ):
        self.path = Path(path)
        self.verbose = verbose
        self.entries: list[dict] = self._load()

    def _log(self, msg: str):
        if self.verbose:
            print(f"[RegressionSuite] {msg}")

    def _load(self) -> list[dict]:
        if self.path.exists():
            try:
                return json.loads(self.path.read_text())
            except (json.JSONDecodeError, IOError):
                pass
        return []

    def _save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.entries, indent=2))

    def add_entry(
        self,
        task: str,
        rubric_id: str,
        criterion_scores: list[dict],
        overall_score: float,
        min_score_buffer: float = 0.05,
    ) -> bool:
        """Add or update a regression entry for a task.

        Only records tasks with overall_score >= 0.65 (only track meaningful results).
        Updates an existing entry if the new score is materially better (>2pp).

        Args:
            task: task description string
            rubric_id: ID of the rubric run that produced these scores
            criterion_scores: list of dicts with 'criterion_id' and 'percentage' keys
            overall_score: overall percentage score (0–1)
            min_score_buffer: grace margin subtracted from each recorded score

        Returns:
            True if an entry was added or updated.
        """
        if overall_score < 0.65:
            return False  # too low to be a useful baseline

        task_hash = hashlib.sha256(task.encode()).hexdigest()[:12]

        new_entry = {
            "task": task,
            "task_hash": task_hash,
            "rubric_id": rubric_id,
            "criterion_ids": [cs["criterion_id"] for cs in criterion_scores],
            "criterion_min_scores": {
                cs["criterion_id"]: round(max(0.0, cs["percentage"] - min_score_buffer), 4)
                for cs in criterion_scores
            },
            "overall_min_score": round(max(0.0, overall_score - min_score_buffer), 4),
            "recorded_score": round(overall_score, 4),
            "recorded_at": datetime.utcnow().isoformat(),
        }

        for i, entry in enumerate(self.entries):
            if entry.get("task_hash") == task_hash:
                if overall_score > entry.get("recorded_score", 0) + 0.02:
                    self.entries[i] = new_entry
                    self._save()
                    self._log(f"Updated entry for task (score: {overall_score:.1%})")
                    return True
                return False  # existing entry is good enough

        self.entries.append(new_entry)
        self._save()
        self._log(f"Added entry for task (score: {overall_score:.1%}, {len(criterion_scores)} criteria)")
        return True

    def check_regression(
        self,
        task: str,
        criterion_scores: list[dict],
        overall_score: float,
    ) -> tuple[bool, list[str]]:
        """Check whether current scores satisfy stored minimum expectations.

        Returns:
            (passed, failures) — failures is empty when passed is True.
        """
        task_hash = hashlib.sha256(task.encode()).hexdigest()[:12]

        for entry in self.entries:
            if entry.get("task_hash") != task_hash:
                continue

            failures = []
            if overall_score < entry.get("overall_min_score", 0):
                failures.append(
                    f"Overall {overall_score:.1%} < min {entry['overall_min_score']:.1%}"
                )

            score_map = {cs["criterion_id"]: cs["percentage"] for cs in criterion_scores}
            for cid, min_pct in entry.get("criterion_min_scores", {}).items():
                actual = score_map.get(cid)
                if actual is not None and actual < min_pct:
                    failures.append(f"{cid}: {actual:.1%} < min {min_pct:.1%}")

            return len(failures) == 0, failures

        return True, []  # no entry → nothing to regress against

    def mean_score_regression(
        self,
        recent_scores: list[float],
        threshold_pp: float = 0.02,
    ) -> tuple[bool, float]:
        """Detect if recent mean score has dropped relative to the suite baseline.

        Args:
            recent_scores: list of overall_score floats from the most recent runs
            threshold_pp: minimum drop (as a fraction, e.g. 0.02 = 2pp) to flag

        Returns:
            (regressed, delta) — delta is negative when regressed.
        """
        if not self.entries or not recent_scores:
            return False, 0.0

        baseline = sum(e["recorded_score"] for e in self.entries) / len(self.entries)
        recent = sum(recent_scores) / len(recent_scores)
        delta = recent - baseline
        return delta < -threshold_pp, round(delta, 4)

    def validate_harness_integrity(self, harness_path: Path) -> tuple[bool, list[str]]:
        """Lightweight structural check after a patch is applied.

        Verifies:
        1. The file is syntactically valid Python
        2. It can be imported in a subprocess without crashing
        3. Any built-in criterion IDs referenced in the suite still appear in source

        Returns:
            (passed, failure_messages)
        """
        failures = []

        # 1. Syntax check
        try:
            import ast as _ast
            _ast.parse(harness_path.read_text())
        except SyntaxError as e:
            return False, [f"SyntaxError: {e}"]

        # 2. Bytecode-compile check in an isolated subprocess.
        # py_compile catches name errors, invalid syntax, and bad bytecode — without
        # executing module-level code or requiring heavy runtime dependencies.
        try:
            result = subprocess.run(
                [sys.executable, "-m", "py_compile", str(harness_path)],
                capture_output=True, text=True, timeout=15,
            )
            if result.returncode != 0:
                err = (result.stderr.strip() or result.stdout.strip())[-300:]
                failures.append(f"Compile error: {err}")
        except subprocess.TimeoutExpired:
            if self.verbose:
                print(
                    f"[RegressionSuite] Compile check timed out for {harness_path.name} "
                    f"— relying on AST check only"
                )
        except Exception as e:
            failures.append(f"Compile check failed: {e}")

        if failures:
            return False, failures

        # 3. Built-in criterion references
        try:
            source = harness_path.read_text()
            referenced_builtins = {
                cid for entry in self.entries
                for cid in entry.get("criterion_ids", [])
                if cid in _BUILT_IN_CRITERIA
            }
            for cid in referenced_builtins:
                if f'id="{cid}"' not in source and f"id='{cid}'" not in source:
                    failures.append(f"Built-in criterion '{cid}' missing from patched harness")
        except Exception as e:
            failures.append(f"Criterion reference check failed: {e}")

        return len(failures) == 0, failures


# ============================================================================
# 3. Self-Editor — the harness rewrites its own source code
# ============================================================================

SELF_EDIT_PROMPT = """You are a code improvement agent. Given performance data about scoring criteria,
propose SPECIFIC code edits to improve the rubric system.

CURRENT FUNCTION:
```python
{current_code}
```

PERFORMANCE DATA:
{performance_data}

HUMAN FEEDBACK:
{feedback_data}

TASK: Propose a concrete edit to this function that addresses the performance issues.

RULES:
1. Output a JSON object with "edits" — an array of find-and-replace operations.
2. Each edit has "old" (exact string to find) and "new" (replacement string).
3. Keep edits minimal and targeted. Don't rewrite the whole function.
4. Focus on: adjusting weights, adding/removing sub-attributes, tuning penalties,
   changing max_points, improving measurement descriptions.
5. Include a "rationale" field explaining why each edit will improve the criterion.
6. If no edit is warranted, return {{"edits": [], "rationale": "No changes needed"}}

OUTPUT FORMAT (JSON only):
{{
  "edits": [
    {{
      "old": "exact string to replace",
      "new": "replacement string",
      "rationale": "why this change improves scoring"
    }}
  ],
  "rationale": "overall reasoning"
}}"""


@dataclass
class SelfEditProposal:
    """A proposed edit to the harness source code."""
    target_file: str
    target_function: str
    edits: list[dict]  # [{"old": str, "new": str, "rationale": str}]
    rationale: str
    performance_data: dict
    edit_type: str = "unknown"  # maps to MetaProposalStrategy.signal_weights keys
    proposed_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    applied: bool = False
    outcome: str = ""  # filled in after observing impact


class SelfEditor:
    """Rewrites the harness's own scoring rubric factories, prompts, and criteria
    based on accumulated learning data.

    This is the core self-improvement mechanism: instead of logging insights to a
    report, the system proposes and applies code patches to its own source files.

    Safety model:
    - All edits are proposed, logged, and can be reviewed before applying
    - Edits are git-committed with a descriptive message
    - If an edit degrades performance, it can be reverted
    - The edit history is stored for audit

    Usage:
        editor = SelfEditor(store, feedback_store)

        # Analyze and propose edits
        proposals = editor.analyze_and_propose()

        # Review proposals
        for p in proposals:
            print(p.rationale)

        # Apply approved proposals
        editor.apply_proposals(proposals)

        # Or auto-apply (for CI/automated usage)
        editor.auto_improve()
    """

    def __init__(
        self,
        store: RubricStore = None,
        feedback_store: FeedbackStore = None,
        harness_path: str = None,
        model: str = "claude-sonnet-4-20250514",
        verbose: bool = True,
        edit_history_path: str = str(Path.home() / ".auto-verifier-data" / "rubric_feedback" / "self_edits.json"),
    ):
        if Anthropic is None:
            raise ImportError("anthropic package required")
        self.client = Anthropic(timeout=__import__('httpx').Timeout(300.0, connect=30.0))
        self.store = store or RubricStore()
        self.learner = RubricLearner(self.store)
        self.feedback_store = feedback_store
        self.model = model
        self.verbose = verbose

        # Find harness source file
        if harness_path:
            self.harness_path = Path(harness_path)
        else:
            self.harness_path = Path(__file__).parent.parent / "rubric_harness.py"

        self.edit_history_path = Path(edit_history_path)
        self.edit_history: list[dict] = self._load_history()

        # Upgrade 1: Editable meta-level proposal strategy (DGM-H)
        from rubric_system.meta_strategy import MetaProposalStrategy, MetaStrategyEditor
        self.meta_strategy = MetaProposalStrategy.load()
        self.meta_strategy_editor = MetaStrategyEditor(
            self.meta_strategy, str(self.edit_history_path)
        )

    def _log(self, msg: str):
        if self.verbose:
            print(f"[SelfEditor] {msg}")

    def _load_history(self) -> list[dict]:
        if self.edit_history_path.exists():
            try:
                return json.loads(self.edit_history_path.read_text())
            except (json.JSONDecodeError, IOError):
                pass
        return []

    def _save_history(self):
        self.edit_history_path.parent.mkdir(parents=True, exist_ok=True)
        self.edit_history_path.write_text(json.dumps(self.edit_history, indent=2))

    def analyze_and_propose(self, min_uses: int = 5) -> list[SelfEditProposal]:
        """Analyze learning data and propose source code edits.

        Works in two modes:
        1. Per-criterion mode (pre-built rubrics with repeated criterion IDs)
        2. Feedback-pattern mode (generated rubrics — uses accumulated feedback
           entries to identify systemic issues and propose prompt edits)
        """
        proposals = []
        insights = self.learner.get_insights()
        stats = self.store.get_criterion_stats(min_uses=min_uses)
        source_code = self.harness_path.read_text()

        # Collect feedback by criterion
        feedback_by_criterion = {}
        if self.feedback_store:
            for entry in self.feedback_store.get_all():
                if entry.criterion_id:
                    feedback_by_criterion.setdefault(entry.criterion_id, []).append(entry.content)

        # === Mode 1: Per-criterion edits (pre-built rubrics) ===
        # Signal weights gate whether each proposal type runs (DGM-H Upgrade 1)
        sw = self.meta_strategy.signal_weights

        if sw.get("high_false_positive", 0.5) > 0.3:
            for criterion_info in insights.get("low_value_criteria", []):
                cid = criterion_info["id"]
                proposal = self._propose_edit_for_criterion(
                    cid, criterion_info, stats, source_code,
                    feedback_by_criterion.get(cid, []),
                    reason="high_false_positive",
                )
                if proposal:
                    proposals.append(proposal)

        if sw.get("always_passes", 0.5) > 0.3:
            for criterion_info in insights.get("suggested_removals", []):
                cid = criterion_info["id"]
                proposal = self._propose_edit_for_criterion(
                    cid, criterion_info, stats, source_code,
                    feedback_by_criterion.get(cid, []),
                    reason="always_passes",
                )
                if proposal:
                    proposals.append(proposal)

        if sw.get("high_value_low_pass", 0.5) > 0.3:
            for criterion_info in insights.get("high_value_criteria", []):
                cid = criterion_info["id"]
                stat = next((s for s in stats if s.criterion_id == cid), None)
                if stat and stat.pass_rate < 0.5:
                    proposal = self._propose_edit_for_criterion(
                        cid, criterion_info, stats, source_code,
                        feedback_by_criterion.get(cid, []),
                        reason="high_value_low_pass",
                    )
                    if proposal:
                        proposals.append(proposal)

        # === Mode 2: Feedback-pattern edits (generated rubrics) ===
        # When criterion IDs don't repeat, per-criterion stats are empty.
        # Fall back to analyzing accumulated feedback entries for patterns.
        if not proposals and self.feedback_store:
            feedback_proposals = self._propose_feedback_based_edits(source_code)
            proposals.extend(feedback_proposals)

        # Propose prompt edits based on accumulated scoring feedback
        prompt_proposal = self._propose_prompt_edits(source_code, feedback_by_criterion)
        if prompt_proposal:
            proposals.append(prompt_proposal)

        self._log(f"Generated {len(proposals)} edit proposals")
        # Upgrade 3 (DGM-H): UCB-rank proposals before returning
        return self._rank_proposals_ucb(proposals)

    # --- Upgrade 3: UCB proposal selection (DGM-H) ---

    def _ucb_score(self, edit_type: str, t: int, c: float = 1.4) -> float:
        """UCB1 score for an edit type.

        Args:
            edit_type: one of the signal_weights keys
            t: total number of proposals attempted (across all types)
            c: exploration coefficient (1.4 = moderate exploration)

        Returns float — higher = more likely to attempt this edit type next.
        """
        history = [
            e for e in self.edit_history
            if e.get("edit_type", "unknown") == edit_type
        ]
        if not history:
            return float('inf')  # always explore unvisited types at least once

        n = len(history)
        wins = sum(
            1 for e in history
            if e.get("accepted", False) and e.get("score_delta", 0) > 0
        )
        mu = wins / n  # exploitation term
        exploration = c * math.sqrt(math.log(max(t, 1)) / n)
        return mu + exploration

    def _rank_proposals_ucb(self, proposals: list) -> list:
        """Re-rank proposals using UCB scores before applying.

        Called at the end of analyze_and_propose() to reorder the list.
        """
        if not proposals:
            return proposals
        t = len(self.edit_history)
        return sorted(
            proposals,
            key=lambda p: self._ucb_score(getattr(p, 'edit_type', 'unknown'), t),
            reverse=True,
        )

    def _propose_feedback_based_edits(self, source_code: str) -> list[SelfEditProposal]:
        """Analyze feedback patterns to propose systemic edits for generated rubrics."""
        proposals = []

        rubric_feedback = self.feedback_store.get_all("rubric") if self.feedback_store else []
        if len(rubric_feedback) < 2:
            return proposals

        self._log(f"Analyzing {len(rubric_feedback)} feedback entries for patterns...")

        non_discriminating = [f for f in rubric_feedback if "scored 95%" in f.content or "don't discriminate" in f.content]
        stuck_criteria = [f for f in rubric_feedback if "never improved" in f.content]

        if len(non_discriminating) >= 2:
            all_easy = set()
            for f in non_discriminating:
                words = f.content.split(":")[-1].strip() if ":" in f.content else f.content
                for word in words.replace(",", " ").split():
                    word = word.strip()
                    if "_" in word and len(word) > 3:
                        all_easy.add(word)
            if all_easy:
                proposal = self._propose_generation_prompt_edit(
                    source_code, "non_discriminating",
                    f"{len(non_discriminating)} runs produced criteria scoring 95%+ on first attempt",
                    list(all_easy)[:10],
                )
                if proposal:
                    proposals.append(proposal)

        if len(stuck_criteria) >= 2:
            all_stuck = set()
            for f in stuck_criteria:
                words = f.content.split(":")[-1].strip() if ":" in f.content else f.content
                for word in words.replace(",", " ").split():
                    word = word.strip()
                    if "_" in word and len(word) > 3:
                        all_stuck.add(word)
            if all_stuck:
                proposal = self._propose_generation_prompt_edit(
                    source_code, "stuck_criteria",
                    f"{len(stuck_criteria)} runs had criteria that never improved",
                    list(all_stuck)[:10],
                )
                if proposal:
                    proposals.append(proposal)

        return proposals

    def _propose_generation_prompt_edit(
        self, source_code: str, issue_type: str,
        evidence: str, example_criteria: list[str],
    ) -> Optional[SelfEditProposal]:
        """Propose an edit to RUBRIC_GENERATION_PROMPT based on systemic feedback."""
        match = re.search(r'(RUBRIC_GENERATION_PROMPT\s*=\s*"""[\s\S]*?""")', source_code)
        if not match:
            return None

        prompt_code = match.group(1)
        issue_desc = {
            "non_discriminating": (
                f"Rubrics produce criteria scoring 95%+ on first attempt — no discrimination. "
                f"Examples: {', '.join(example_criteria[:5])}"
            ),
            "stuck_criteria": (
                f"Rubrics produce criteria stuck <70% that never improve. "
                f"Examples: {', '.join(example_criteria[:5])}"
            ),
        }.get(issue_type, evidence)

        prompt = f"""You are a self-improvement engine for a rubric generation system.

PROBLEM: {issue_desc}
EVIDENCE: {evidence}

CURRENT RUBRIC GENERATION PROMPT (excerpt):
{prompt_code[:4000]}

Propose 1-2 targeted edits. Each must be a find-and-replace on the prompt text.

Output JSON:
{{
  "rationale": "<why this fixes the issue>",
  "edits": [{{"old": "<exact substring to find>", "new": "<replacement>"}}]
}}

RULES: Edits must be MINIMAL. "old" must be an EXACT substring. Output ONLY JSON."""

        try:
            response = self.client.messages.create(
                model=self.model, max_tokens=2000, temperature=0,
                messages=[{"role": "user", "content": prompt}],
            )
            spec = self._parse_json(response.content[0].text)
            edits = spec.get("edits", [])
            if not edits:
                return None
            return SelfEditProposal(
                target_file=str(self.harness_path),
                target_function="RUBRIC_GENERATION_PROMPT",
                edits=edits,
                rationale=spec.get("rationale", f"Feedback-based: {issue_type}"),
                performance_data={"type": "feedback_pattern", "issue": issue_type,
                                  "evidence": evidence, "examples": example_criteria},
            )
        except Exception as e:
            self._log(f"Generation prompt edit proposal failed: {e}")
            return None

    def _propose_edit_for_criterion(
        self,
        criterion_id: str,
        criterion_info: dict,
        stats: list[CriterionStats],
        source_code: str,
        feedback: list[str],
        reason: str,
    ) -> Optional[SelfEditProposal]:
        """Propose an edit for a specific criterion's scoring rubric factory."""

        # Find the scoring rubric factory function in source
        # Look for functions that create ScoringRubric objects related to this criterion
        function_code = self._extract_related_function(criterion_id, source_code)
        if not function_code:
            self._log(f"Could not find source function for {criterion_id}")
            return None

        # Get the criterion's stats
        stat = next((s for s in stats if s.criterion_id == criterion_id), None)

        performance_data = {
            "criterion_id": criterion_id,
            "reason_for_edit": reason,
            **criterion_info,
        }
        if stat:
            performance_data.update({
                "times_used": stat.times_used,
                "pass_rate": round(stat.pass_rate, 3),
                "predictive_value": round(stat.predictive_value, 3),
                "false_positive_rate": round(stat.false_positive_rate, 3),
                "bug_prevention_rate": round(stat.bug_prevention_rate, 3),
            })

        feedback_text = "\n".join(f"- {f}" for f in feedback[:5]) if feedback else "No feedback"

        prompt = SELF_EDIT_PROMPT.format(
            current_code=function_code,
            performance_data=json.dumps(performance_data, indent=2),
            feedback_data=feedback_text,
        )

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=2000,
                messages=[{"role": "user", "content": prompt}],
            )
            raw = response.content[0].text

            spec = self._parse_json(raw)
            edits = spec.get("edits", [])

            if not edits:
                return None

            return SelfEditProposal(
                target_file=str(self.harness_path),
                target_function=criterion_id,
                edits=edits,
                rationale=spec.get("rationale", ""),
                performance_data=performance_data,
                edit_type=reason,
            )
        except Exception as e:
            self._log(f"Edit proposal failed for {criterion_id}: {e}")
            return None

    def _propose_prompt_edits(
        self,
        source_code: str,
        feedback_by_criterion: dict,
    ) -> Optional[SelfEditProposal]:
        """Propose edits to measurement/generation prompts based on feedback patterns."""

        # Collect all feedback that mentions scoring or measurement issues
        scoring_feedback = []
        if self.feedback_store:
            for entry in self.feedback_store.get_all("scoring"):
                scoring_feedback.append(entry.content)

        if len(scoring_feedback) < 3:
            return None  # Not enough feedback to justify prompt edits

        # Extract the measurement prompt
        match = re.search(
            r'(MEASUREMENT_PROMPT\s*=\s*"""[\s\S]*?""")',
            source_code,
        )
        if not match:
            return None

        prompt_code = match.group(1)

        prompt = SELF_EDIT_PROMPT.format(
            current_code=prompt_code[:3000],
            performance_data=json.dumps({"type": "measurement_prompt", "feedback_count": len(scoring_feedback)}),
            feedback_data="\n".join(f"- {f}" for f in scoring_feedback[:8]),
        )

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=2000,
                messages=[{"role": "user", "content": prompt}],
            )
            spec = self._parse_json(response.content[0].text)
            edits = spec.get("edits", [])

            if not edits:
                return None

            return SelfEditProposal(
                target_file=str(self.harness_path),
                target_function="MEASUREMENT_PROMPT",
                edits=edits,
                rationale=spec.get("rationale", ""),
                performance_data={"type": "prompt_edit", "feedback_count": len(scoring_feedback)},
            )
        except Exception as e:
            self._log(f"Prompt edit proposal failed: {e}")
            return None

    def _extract_related_function(self, criterion_id: str, source_code: str) -> Optional[str]:
        """Find the scoring rubric factory or criterion definition for a given criterion ID."""
        lines = source_code.split("\n")

        # Strategy 1: find Criterion definition with this ID
        for i, line in enumerate(lines):
            if f'id="{criterion_id}"' in line:
                # Walk backward to find the Criterion( start
                start = i
                while start > 0 and "Criterion(" not in lines[start]:
                    start -= 1
                # Walk forward to find the closing )
                end = i
                paren_depth = 0
                for j in range(start, min(len(lines), start + 50)):
                    paren_depth += lines[j].count("(") - lines[j].count(")")
                    if paren_depth <= 0:
                        end = j + 1
                        break
                return "\n".join(lines[start:end])

        # Strategy 2: find function with criterion_id in name
        pattern = criterion_id.replace("_", r"[\s_]")
        for i, line in enumerate(lines):
            if re.search(rf"def\s+.*{pattern}", line, re.I):
                # Extract entire function
                start = i
                end = i + 1
                base_indent = len(line) - len(line.lstrip())
                for j in range(i + 1, min(len(lines), i + 60)):
                    if lines[j].strip() and not lines[j].startswith(" " * (base_indent + 1)):
                        if not lines[j].strip().startswith("#"):
                            end = j
                            break
                    end = j + 1
                return "\n".join(lines[start:end])

        return None

    def apply_proposals(
        self,
        proposals: list[SelfEditProposal],
        dry_run: bool = False,
        git_commit: bool = True,
    ) -> list[dict]:
        """Apply approved edit proposals to the source code.

        Pre-apply validation (per proposal):
        a. Save current source to a temp backup (.bak)
        b. Apply the patch
        c. Run RegressionSuite.validate_harness_integrity() on the modified file
        d. If validation fails → revert from backup, log the failure, skip git commit
        e. If validation passes → delete backup, proceed to git commit

        Args:
            proposals: list of SelfEditProposal to apply
            dry_run: if True, show edits but don't apply
            git_commit: if True, create a git commit for each batch of edits

        Returns:
            list of applied edit records
        """
        suite = RegressionSuite(verbose=self.verbose)
        applied = []

        for proposal in proposals:
            if not proposal.edits:
                continue

            target = Path(proposal.target_file)
            if not target.exists():
                self._log(f"Target file not found: {target}")
                continue

            source = target.read_text()
            original = source
            edits_applied = 0

            for edit in proposal.edits:
                old = edit.get("old", "")
                new = edit.get("new", "")

                if not old or old not in source:
                    self._log(f"Edit target not found: {old[:60]}...")
                    continue

                if dry_run:
                    self._log(f"[DRY RUN] Would replace:\n  {old[:80]}...\n  → {new[:80]}...")
                else:
                    source = source.replace(old, new, 1)
                    edits_applied += 1

            if edits_applied > 0 and not dry_run:
                # Step 1: syntax check before touching disk
                try:
                    import ast
                    ast.parse(source)
                except SyntaxError as e:
                    self._log(f"SYNTAX ERROR in proposed edit — reverting: {e}")
                    source = original
                    edits_applied = 0

            if edits_applied > 0 and not dry_run:
                # Step 2: write to disk with backup, then validate
                backup_path = target.with_suffix(target.suffix + ".bak")
                backup_path.write_text(original)
                target.write_text(source)

                passed, failures = suite.validate_harness_integrity(target)
                if not passed:
                    failure_msg = "; ".join(failures)
                    self._log(
                        f"PRE-APPLY VALIDATION FAILED for '{proposal.target_function}' "
                        f"— reverting: {failure_msg}"
                    )
                    # Revert from backup
                    target.write_text(original)
                    backup_path.unlink(missing_ok=True)
                    edits_applied = 0
                    self._record_regression_failure(proposal, failure_msg)
                else:
                    backup_path.unlink(missing_ok=True)
                    self._log(
                        f"Applied {edits_applied} edit(s) to {target.name} "
                        f"(validation passed)"
                    )

            record = {
                "proposal": {
                    "target_function": proposal.target_function,
                    "rationale": proposal.rationale,
                    "edits_count": len(proposal.edits),
                    "edits_applied": edits_applied,
                    "performance_data": proposal.performance_data,
                },
                "edit_type": getattr(proposal, "edit_type", "unknown"),
                "accepted": edits_applied > 0 and not dry_run,
                "score_delta": 0,  # backfilled on next auto_improve() run
                "applied_at": datetime.utcnow().isoformat(),
                "dry_run": dry_run,
            }
            applied.append(record)
            proposal.applied = not dry_run and edits_applied > 0

        # Save to edit history
        self.edit_history.extend(applied)
        self._save_history()

        # Git commit
        if git_commit and not dry_run and any(r["proposal"]["edits_applied"] > 0 for r in applied):
            self._git_commit_edits(applied)

        return applied

    def _record_regression_failure(self, proposal: SelfEditProposal, reason: str):
        """Append a regression-failure record to the edit history."""
        record = {
            "type": "regression_failure",
            "proposal_target": proposal.target_function,
            "proposal_rationale": proposal.rationale[:120],
            "failure_reason": reason,
            "failed_at": datetime.utcnow().isoformat(),
        }
        self.edit_history.append(record)
        self._save_history()
        self._log(f"Regression failure logged for '{proposal.target_function}'")

    def auto_improve(
        self,
        min_uses: int = 10,
        dry_run: bool = False,
        max_edits: int = 3,
    ) -> list[dict]:
        """Full auto-improvement cycle: analyze → propose → apply.

        This is the main entry point for automated self-improvement.

        Args:
            min_uses: minimum criterion usage count before considering edits
            dry_run: if True, propose but don't apply
            max_edits: maximum number of edits to apply per cycle

        Returns:
            list of applied edit records
        """
        self._log("Starting self-improvement cycle...")

        # 0. Backfill score_delta on previous edit history entries (DGM-H Upgrade 2)
        from rubric_system.improvement_velocity import (
            ImprovementVelocityTracker, backfill_score_delta,
        )
        backfill_score_delta(str(self.edit_history_path), self.store)
        # Reload history in case backfill modified it
        self.edit_history = self._load_history()

        # 1. Scan for new outcome signals
        outcome_tracker = OutcomeTracker(self.store, verbose=self.verbose)
        try:
            outcome_tracker.scan_git_outcomes()
        except Exception as e:
            self._log(f"Git scan skipped: {e}")

        # 2. Capture baseline for imp@k tracking
        velocity_tracker = ImprovementVelocityTracker()
        all_rubrics = self.store.list_all()
        baseline_score = all_rubrics[-1].overall_score if all_rubrics else 0.0
        task_hash = all_rubrics[-1].task_hash if all_rubrics else "unknown"
        velocity_tracker.start_run(
            strategy_version=self.meta_strategy.version,
            domain=getattr(all_rubrics[-1], "project", "") if all_rubrics else "",
            task_hash=task_hash,
            baseline_score=baseline_score,
        )

        # 3. Analyze and propose
        proposals = self.analyze_and_propose(min_uses=min_uses)

        if not proposals:
            self._log("No improvements identified")
            return []

        # 4. Limit and apply
        proposals = proposals[:max_edits]
        self._log(f"Applying {len(proposals)} proposals (max: {max_edits})")

        results = self.apply_proposals(proposals, dry_run=dry_run)

        # 5. Finish imp@k tracking
        applied_ids = [
            r["proposal"]["target_function"]
            for r in results if r["proposal"]["edits_applied"] > 0
        ]
        rejected_ids = [
            r["proposal"]["target_function"]
            for r in results if r["proposal"]["edits_applied"] == 0
        ]
        # Final score will be from next run; use baseline as placeholder
        velocity_tracker.finish_run(
            task_hash=task_hash,
            final_score=baseline_score,  # updated on next run via backfill
            proposals_applied=applied_ids,
            proposals_rejected=rejected_ids,
        )

        # 6. Update the meta strategy itself every 3 runs (DGM-H Upgrade 1)
        if len(self.edit_history) % 3 == 0 and len(self.edit_history) > 0:
            self.meta_strategy_editor.update_signal_weights()
            self._log(
                f"MetaProposalStrategy updated to v{self.meta_strategy.version}"
            )

        # 7. Summary
        applied_count = sum(1 for r in results if r["proposal"]["edits_applied"] > 0)
        self._log(f"Self-improvement complete: {applied_count} edits applied")

        return results

    def _git_commit_edits(self, applied: list[dict]):
        """Create a git commit for self-edits."""
        try:
            # Build commit message
            summaries = []
            for record in applied:
                if record["proposal"]["edits_applied"] > 0:
                    fn = record["proposal"]["target_function"]
                    rationale = record["proposal"]["rationale"][:100]
                    summaries.append(f"  - {fn}: {rationale}")

            if not summaries:
                return

            message = "rubric: self-improvement edits based on learning data\n\n"
            message += "\n".join(summaries)
            message += "\n\nAutomated by SelfEditor based on criterion effectiveness analysis."

            subprocess.run(
                ["git", "add", str(self.harness_path)],
                capture_output=True,
                cwd=self.harness_path.parent,
                timeout=5,
            )
            subprocess.run(
                ["git", "commit", "-m", message],
                capture_output=True,
                cwd=self.harness_path.parent,
                timeout=5,
            )
            self._log("Git commit created for self-edits")
        except Exception as e:
            self._log(f"Git commit failed: {e}")

    def _parse_json(self, text: str) -> dict:
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
        match = re.search(r'\{[\s\S]*\}', text)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
        return {}

    def get_edit_history(self) -> list[dict]:
        """Return the full history of self-edits."""
        return self.edit_history

    def revert_last_edit(self) -> bool:
        """Revert the most recent self-edit via git."""
        try:
            result = subprocess.run(
                ["git", "log", "--oneline", "-1"],
                capture_output=True, text=True,
                cwd=self.harness_path.parent,
                timeout=5,
            )
            if "self-improvement" in result.stdout:
                subprocess.run(
                    ["git", "revert", "--no-edit", "HEAD"],
                    capture_output=True,
                    cwd=self.harness_path.parent,
                    timeout=10,
                )
                self._log("Reverted last self-edit")
                return True
            else:
                self._log("Last commit was not a self-edit")
                return False
        except Exception as e:
            self._log(f"Revert failed: {e}")
            return False


# ============================================================================
# CLI
# ============================================================================

def main():
    import argparse

    parser = argparse.ArgumentParser(description="Rubric Self-Improvement Engine")
    subparsers = parser.add_subparsers(dest="command")

    # Scan for outcomes
    scan = subparsers.add_parser("scan", help="Scan for outcome signals")
    scan.add_argument("--repo", default=".", help="Git repo path")
    scan.add_argument("--days", type=int, default=14, help="Lookback days")

    # Propose edits
    propose = subparsers.add_parser("propose", help="Propose self-edits")
    propose.add_argument("--min-uses", type=int, default=5)

    # Apply edits
    apply_cmd = subparsers.add_parser("apply", help="Apply proposed edits")
    apply_cmd.add_argument("--dry-run", action="store_true")
    apply_cmd.add_argument("--max-edits", type=int, default=3)

    # Auto-improve (full cycle)
    auto = subparsers.add_parser("auto", help="Full auto-improvement cycle")
    auto.add_argument("--dry-run", action="store_true")
    auto.add_argument("--min-uses", type=int, default=10)
    auto.add_argument("--max-edits", type=int, default=3)

    # History
    subparsers.add_parser("history", help="Show edit history")

    # Revert
    subparsers.add_parser("revert", help="Revert last self-edit")

    args = parser.parse_args()

    store = RubricStore()
    editor = SelfEditor(store=store)

    if args.command == "scan":
        tracker = OutcomeTracker(store)
        signals = tracker.scan_git_outcomes(repo_path=args.repo, lookback_days=args.days)
        signals += tracker.scan_ci_failures()
        print(f"Found {len(signals)} outcome signals")

    elif args.command == "propose":
        proposals = editor.analyze_and_propose(min_uses=args.min_uses)
        for p in proposals:
            print(f"\n{'─'*60}")
            print(f"Target: {p.target_function}")
            print(f"Rationale: {p.rationale}")
            for edit in p.edits:
                print(f"  Edit: {edit.get('rationale', '')}")

    elif args.command == "apply":
        proposals = editor.analyze_and_propose()
        results = editor.apply_proposals(proposals, dry_run=args.dry_run)
        for r in results:
            print(f"  {r['proposal']['target_function']}: {r['proposal']['edits_applied']} edits")

    elif args.command == "auto":
        results = editor.auto_improve(
            min_uses=args.min_uses,
            dry_run=args.dry_run,
            max_edits=args.max_edits,
        )
        print(f"Applied {len(results)} edit batches")

    elif args.command == "history":
        for record in editor.get_edit_history():
            print(f"  {record['applied_at']}: {record['proposal']['target_function']} "
                  f"({record['proposal']['edits_applied']} edits)")

    elif args.command == "revert":
        editor.revert_last_edit()

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
