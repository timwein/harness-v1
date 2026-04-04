#!/usr/bin/env python3
"""
Checkpoint Policy — When to Stop and Ask for Human Verification

Teaches the system when to pause during a task and request human verification,
rather than running to completion and dumping everything at once.

The policy learns from:
1. Historical feedback patterns (which checkpoints got useful feedback)
2. Task complexity signals (more criteria → more checkpoints)
3. Risk profile (critical criteria failing → stop early)
4. Score volatility (big swings between iterations → stabilize first)

Checkpoint types:
  - rubric_review: After rubric generation, before any work starts
  - first_attempt: After first iteration, to verify direction
  - critical_gate: When all critical criteria pass for the first time
  - plateau_check: When score stops improving between iterations
  - mid_loop: Halfway through max iterations
  - pre_final: One iteration before max, to decide whether to continue

Usage:
    from rubric_system.checkpoint_policy import CheckpointPolicy, Checkpoint

    policy = CheckpointPolicy()
    policy.configure(task_complexity="high", has_critical_criteria=True)

    # In the loop:
    checkpoint = policy.should_checkpoint(iteration=2, scores=..., history=...)
    if checkpoint:
        # Present checkpoint to human
        response = get_human_input(checkpoint.format_prompt())
        policy.record_checkpoint_outcome(checkpoint, response)
"""

import json
from datetime import datetime
from dataclasses import dataclass, field
from typing import Optional, Callable
from pathlib import Path
from enum import Enum

from rubric_system.models import CriterionScore, Iteration

# Single source of truth for the default iteration limit.
# eval_harness.py and rubric_harness.py both import this so the CLI default
# and the policy default stay in sync automatically.
# 0 = unlimited (run until pass threshold or convergence).
DEFAULT_MAX_ITERATIONS: int = 0


class CheckpointType(Enum):
    RUBRIC_REVIEW = "rubric_review"
    FIRST_ATTEMPT = "first_attempt"
    CRITICAL_GATE = "critical_gate"
    PLATEAU_CHECK = "plateau_check"
    MID_LOOP = "mid_loop"
    PRE_FINAL = "pre_final"


@dataclass
class Checkpoint:
    """A specific checkpoint request."""
    checkpoint_type: str
    iteration: int
    reason: str
    summary: str  # What to show the human
    questions: list[str]  # Specific things to verify
    current_score: float = 0.0
    critical_status: dict = field(default_factory=dict)  # criterion_id -> pass/fail
    priority: str = "normal"  # "low", "normal", "high", "critical"
    skippable: bool = True  # Can the human skip this checkpoint?

    def format_prompt(self) -> str:
        """Format this checkpoint for human presentation."""
        lines = [
            f"{'='*60}",
            f"CHECKPOINT: {self.checkpoint_type.replace('_', ' ').title()}",
            f"Iteration: {self.iteration} | Score: {self.current_score:.0%}",
            f"{'='*60}",
            "",
            f"Reason: {self.reason}",
            "",
            self.summary,
            "",
        ]

        if self.critical_status:
            lines.append("Critical criteria status:")
            for crit_id, status in self.critical_status.items():
                indicator = "PASS" if status else "FAIL"
                lines.append(f"  [{indicator}] {crit_id}")
            lines.append("")

        if self.questions:
            lines.append("Please verify:")
            for i, q in enumerate(self.questions, 1):
                lines.append(f"  {i}. {q}")

        lines.append("")
        if self.skippable:
            lines.append("Options: [continue] [adjust rubric] [provide feedback] [stop]")
        else:
            lines.append("Options: [approve to continue] [adjust rubric] [provide feedback] [stop]")

        return "\n".join(lines)


@dataclass
class CheckpointOutcome:
    """Record of what happened at a checkpoint."""
    checkpoint_type: str
    iteration: int
    human_action: str  # "continue", "adjust", "feedback", "stop"
    feedback_given: str = ""
    adjustments_made: list[str] = field(default_factory=list)
    time_spent_seconds: float = 0
    was_useful: Optional[bool] = None  # Did the human find this checkpoint useful?
    timestamp: str = ""


class CheckpointPolicy:
    """
    Determines when to pause for human verification.
    Learns from outcomes to become more/less aggressive about checkpointing.
    """

    def __init__(self, history_path: str = str(Path.home() / ".auto-verifier-data" / "rubric_feedback" / "checkpoint_history.json")):
        self.history_path = Path(history_path)
        self.outcomes: list[CheckpointOutcome] = []
        self._load_history()

        # Configuration
        self.task_complexity: str = "medium"  # low, medium, high
        self.has_critical_criteria: bool = False
        self.max_iterations: int = DEFAULT_MAX_ITERATIONS
        self.pass_threshold: float = 0.85

        # Learned thresholds (adjusted from history)
        self.plateau_threshold: float = 0.02  # Score improvement < 2% = plateau
        self.critical_gate_enabled: bool = True
        self.first_attempt_enabled: bool = True
        self.mid_loop_enabled: bool = True

        # Track what's been triggered this run
        self._triggered: set[str] = set()
        self._apply_learned_preferences()

    def configure(
        self,
        task_complexity: str = "medium",
        has_critical_criteria: bool = False,
        max_iterations: int = DEFAULT_MAX_ITERATIONS,
        pass_threshold: float = 0.85,
    ):
        """Configure policy for a specific run."""
        self.task_complexity = task_complexity
        self.has_critical_criteria = has_critical_criteria
        self.max_iterations = max_iterations
        self.pass_threshold = pass_threshold
        self._triggered = set()

    def should_checkpoint(
        self,
        iteration: int,
        current_score: float,
        criterion_scores: list[CriterionScore],
        history: list[Iteration],
    ) -> Optional[Checkpoint]:
        """
        Determine if we should pause for human verification.
        Returns a Checkpoint if yes, None if no.
        """
        # Check each checkpoint type in priority order
        checks = [
            self._check_first_attempt,
            self._check_critical_gate,
            self._check_plateau,
            self._check_mid_loop,
            self._check_pre_final,
        ]

        for check_fn in checks:
            checkpoint = check_fn(iteration, current_score, criterion_scores, history)
            if checkpoint and checkpoint.checkpoint_type not in self._triggered:
                self._triggered.add(checkpoint.checkpoint_type)
                return checkpoint

        return None

    def should_checkpoint_rubric(self, rubric_summary: str) -> Checkpoint:
        """Always checkpoint after rubric generation (before any work starts)."""
        return Checkpoint(
            checkpoint_type=CheckpointType.RUBRIC_REVIEW.value,
            iteration=0,
            reason="Rubric generated — verify criteria before starting work",
            summary=rubric_summary,
            questions=[
                "Are these the right criteria for this task?",
                "Any criteria missing that matter to you?",
                "Any criteria too strict or too lenient?",
                "Is the pass threshold appropriate?",
            ],
            priority="high",
            skippable=False,
        )

    def record_outcome(self, checkpoint: Checkpoint, action: str, feedback: str = ""):
        """Record what happened at a checkpoint for future learning."""
        outcome = CheckpointOutcome(
            checkpoint_type=checkpoint.checkpoint_type,
            iteration=checkpoint.iteration,
            human_action=action,
            feedback_given=feedback,
            timestamp=datetime.utcnow().isoformat(),
            was_useful=action != "continue",  # If they just continued, it wasn't useful
        )
        self.outcomes.append(outcome)
        self._save_history()

    # ---- Checkpoint checks ----

    def _check_first_attempt(
        self, iteration: int, score: float, criterion_scores: list[CriterionScore],
        history: list[Iteration],
    ) -> Optional[Checkpoint]:
        """After first iteration — verify we're headed in the right direction."""
        if not self.first_attempt_enabled or iteration != 1:
            return None

        failing = [(cs.criterion_id, cs.percentage) for cs in criterion_scores if cs.percentage < 0.5]
        passing = [(cs.criterion_id, cs.percentage) for cs in criterion_scores if cs.percentage >= 0.8]

        summary_lines = [
            f"First attempt complete. Score: {score:.0%}",
            f"Passing: {len(passing)}/{len(criterion_scores)} criteria",
        ]
        if failing:
            summary_lines.append(f"Significantly failing ({len(failing)}):")
            for crit_id, pct in sorted(failing, key=lambda x: x[1]):
                summary_lines.append(f"  - {crit_id}: {pct:.0%}")

        questions = ["Is the output heading in the right direction?"]
        if failing:
            questions.append("Should we adjust the rubric for any failing criteria?")
        if score < 0.5:
            questions.append("Score is quite low — should we reconsider the approach?")

        return Checkpoint(
            checkpoint_type=CheckpointType.FIRST_ATTEMPT.value,
            iteration=iteration,
            reason="First attempt — verify direction before investing more iterations",
            summary="\n".join(summary_lines),
            questions=questions,
            current_score=score,
            priority="high" if score < 0.5 else "normal",
        )

    def _check_critical_gate(
        self, iteration: int, score: float, criterion_scores: list[CriterionScore],
        history: list[Iteration],
    ) -> Optional[Checkpoint]:
        """When all critical criteria pass for the first time."""
        if not self.critical_gate_enabled or not self.has_critical_criteria:
            return None

        # Find criteria with high max_points (likely critical)
        critical_scores = [cs for cs in criterion_scores if cs.max_points >= 10]
        if not critical_scores:
            return None

        all_critical_pass = all(cs.percentage >= 0.8 for cs in critical_scores)
        if not all_critical_pass:
            return None

        # Check if this is the FIRST time all critical pass
        if history:
            for prev in history[:-1]:  # Exclude current (not in history yet at check time)
                prev_critical = [cs for cs in prev.criterion_scores if cs.max_points >= 10]
                if prev_critical and all(cs.percentage >= 0.8 for cs in prev_critical):
                    return None  # Already passed before

        critical_status = {cs.criterion_id: cs.percentage >= 0.8 for cs in critical_scores}

        return Checkpoint(
            checkpoint_type=CheckpointType.CRITICAL_GATE.value,
            iteration=iteration,
            reason="All critical criteria now passing — good time to verify quality",
            summary=f"Critical criteria all pass. Overall score: {score:.0%}. "
                    f"Remaining gap is in non-critical criteria.",
            questions=[
                "Does the output meet your quality bar for critical requirements?",
                "Should we continue optimizing non-critical criteria, or ship this?",
            ],
            current_score=score,
            critical_status=critical_status,
            priority="normal",
        )

    def _check_plateau(
        self, iteration: int, score: float, criterion_scores: list[CriterionScore],
        history: list[Iteration],
    ) -> Optional[Checkpoint]:
        """When score stops improving between iterations."""
        if iteration < 3 or len(history) < 2:
            return None

        recent_scores = [h.percentage for h in history[-2:]] + [score]
        improvement = recent_scores[-1] - recent_scores[-2]
        prev_improvement = recent_scores[-2] - recent_scores[-3] if len(recent_scores) >= 3 else 0.1

        if abs(improvement) < self.plateau_threshold and abs(prev_improvement) < self.plateau_threshold:
            stuck_criteria = [(cs.criterion_id, cs.percentage)
                             for cs in criterion_scores if cs.percentage < 0.8]
            stuck_criteria.sort(key=lambda x: x[1])

            summary = f"Score plateau detected: {recent_scores[-3]:.0%} → {recent_scores[-2]:.0%} → {score:.0%}"
            if stuck_criteria:
                summary += f"\n\nStuck criteria ({len(stuck_criteria)}):"
                for crit_id, pct in stuck_criteria[:5]:
                    summary += f"\n  - {crit_id}: {pct:.0%}"

            return Checkpoint(
                checkpoint_type=CheckpointType.PLATEAU_CHECK.value,
                iteration=iteration,
                reason=f"Score plateau — improvement < {self.plateau_threshold:.0%} for 2 consecutive iterations",
                summary=summary,
                questions=[
                    "The system is stuck — should we adjust the rubric for the stuck criteria?",
                    "Are the stuck criteria actually important, or can we accept this score?",
                    "Would different approach or context help break through?",
                ],
                current_score=score,
                priority="high" if score < self.pass_threshold else "normal",
            )

        return None

    def _check_mid_loop(
        self, iteration: int, score: float, criterion_scores: list[CriterionScore],
        history: list[Iteration],
    ) -> Optional[Checkpoint]:
        """Halfway through max iterations."""
        if not self.mid_loop_enabled:
            return None

        mid_point = self.max_iterations // 2
        if iteration != mid_point or self.max_iterations < 4:
            return None

        gap = self.pass_threshold - score
        if gap <= 0:
            return None  # Already passing, no need

        return Checkpoint(
            checkpoint_type=CheckpointType.MID_LOOP.value,
            iteration=iteration,
            reason=f"Halfway point ({iteration}/{self.max_iterations}) — {gap:.0%} gap to pass threshold",
            summary=f"Score: {score:.0%}, need {self.pass_threshold:.0%} to pass. "
                    f"{self.max_iterations - iteration} iterations remaining.",
            questions=[
                f"We need +{gap:.0%} in {self.max_iterations - iteration} iterations — realistic?",
                "Any guidance on what to prioritize for remaining iterations?",
            ],
            current_score=score,
            priority="normal",
        )

    def _check_pre_final(
        self, iteration: int, score: float, criterion_scores: list[CriterionScore],
        history: list[Iteration],
    ) -> Optional[Checkpoint]:
        """One iteration before max — last chance to adjust."""
        if iteration != self.max_iterations - 1:
            return None

        if score >= self.pass_threshold:
            return None  # Already passing

        return Checkpoint(
            checkpoint_type=CheckpointType.PRE_FINAL.value,
            iteration=iteration,
            reason="One iteration remaining before max — last chance to adjust",
            summary=f"Score: {score:.0%}, threshold: {self.pass_threshold:.0%}. "
                    f"One iteration left. Consider adjusting threshold or rubric.",
            questions=[
                "Accept current output, or try one more iteration?",
                "Should we lower the pass threshold?",
                "Any specific feedback for the final attempt?",
            ],
            current_score=score,
            priority="high",
            skippable=False,
        )

    # ---- Learning ----

    def _apply_learned_preferences(self):
        """Adjust checkpoint aggressiveness based on historical outcomes."""
        if not self.outcomes:
            return

        # Count how often each checkpoint type was useful
        type_stats: dict[str, dict] = {}
        for outcome in self.outcomes:
            if outcome.checkpoint_type not in type_stats:
                type_stats[outcome.checkpoint_type] = {"useful": 0, "total": 0}
            type_stats[outcome.checkpoint_type]["total"] += 1
            if outcome.was_useful:
                type_stats[outcome.checkpoint_type]["useful"] += 1

        # Disable checkpoints that are consistently skipped (>80% just-continue)
        for cp_type, stats in type_stats.items():
            if stats["total"] >= 5:
                usefulness = stats["useful"] / stats["total"]
                if cp_type == CheckpointType.FIRST_ATTEMPT.value:
                    self.first_attempt_enabled = usefulness > 0.2
                elif cp_type == CheckpointType.CRITICAL_GATE.value:
                    self.critical_gate_enabled = usefulness > 0.2
                elif cp_type == CheckpointType.MID_LOOP.value:
                    self.mid_loop_enabled = usefulness > 0.2

    def _load_history(self):
        """Load checkpoint history from disk."""
        if self.history_path.exists():
            try:
                data = json.loads(self.history_path.read_text())
                self.outcomes = [CheckpointOutcome(**o) for o in data]
            except (json.JSONDecodeError, TypeError):
                self.outcomes = []

    def _save_history(self):
        """Save checkpoint history to disk."""
        self.history_path.parent.mkdir(parents=True, exist_ok=True)
        from dataclasses import asdict
        data = [asdict(o) for o in self.outcomes]
        self.history_path.write_text(json.dumps(data, indent=2))

    def get_stats(self) -> dict:
        """Get checkpoint effectiveness stats."""
        stats: dict[str, dict] = {}
        for outcome in self.outcomes:
            if outcome.checkpoint_type not in stats:
                stats[outcome.checkpoint_type] = {
                    "total": 0, "useful": 0, "feedback_given": 0,
                    "actions": {}
                }
            s = stats[outcome.checkpoint_type]
            s["total"] += 1
            if outcome.was_useful:
                s["useful"] += 1
            if outcome.feedback_given:
                s["feedback_given"] += 1
            s["actions"][outcome.human_action] = s["actions"].get(outcome.human_action, 0) + 1

        return stats
