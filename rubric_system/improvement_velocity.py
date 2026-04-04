"""Improvement velocity tracking — imp@k metric from DGM-H.

Tracks performance gain achieved by a fixed MetaProposalStrategy version
over k modification steps.  Used to rigorously compare strategy versions
independent of task-level exploration noise.

Key result from DGM-H: human-customized DGM imp@50 = 0.0 on transfer tasks;
DGM-H imp@50 = 0.630.
"""

from dataclasses import dataclass, field
from datetime import datetime
import json
from pathlib import Path

VELOCITY_LOG_PATH = str(Path.home() / ".auto-verifier-data" / "rubric_feedback" / "improvement_velocity.json")


@dataclass
class ImprovementVelocityRecord:
    """imp@k for a fixed meta strategy version over k rubric iterations."""

    meta_strategy_version: int
    domain: str
    task_hash: str
    k_iterations: int
    baseline_score: float       # score before this SelfEditor run
    final_score: float          # score after k iterations
    imp_at_k: float             # final_score - baseline_score
    edit_proposals_applied: list
    edit_proposals_rejected: list
    recorded_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())


class ImprovementVelocityTracker:
    """Tracks imp@k across meta strategy versions and domains.

    Usage:
        tracker = ImprovementVelocityTracker()

        # Before a SelfEditor run:
        tracker.start_run(strategy_version=2, domain="investment_memo",
                         task_hash="abc123", baseline_score=0.68)

        # After k iterations:
        tracker.finish_run(task_hash="abc123", final_score=0.81,
                          proposals_applied=["fix:src_authority"],
                          proposals_rejected=["fix:always_passes"])

        # Compare strategy versions:
        tracker.compare_versions(domain="investment_memo")
    """

    def __init__(self, path: str = VELOCITY_LOG_PATH):
        self.path = Path(path)
        self._pending: dict = {}  # task_hash → partial record
        self.records: list[ImprovementVelocityRecord] = self._load()

    def _load(self) -> list:
        if self.path.exists():
            try:
                return [
                    ImprovementVelocityRecord(**r)
                    for r in json.loads(self.path.read_text())
                ]
            except (json.JSONDecodeError, TypeError):
                pass
        return []

    def _save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps([r.__dict__ for r in self.records], indent=2)
        )

    def start_run(
        self,
        strategy_version: int,
        domain: str,
        task_hash: str,
        baseline_score: float,
        k_iterations: int = 10,
    ):
        self._pending[task_hash] = {
            "meta_strategy_version": strategy_version,
            "domain": domain,
            "task_hash": task_hash,
            "k_iterations": k_iterations,
            "baseline_score": baseline_score,
        }

    def finish_run(
        self,
        task_hash: str,
        final_score: float,
        proposals_applied: list,
        proposals_rejected: list,
    ):
        pending = self._pending.pop(task_hash, None)
        if not pending:
            return
        record = ImprovementVelocityRecord(
            **pending,
            final_score=final_score,
            imp_at_k=round(final_score - pending["baseline_score"], 4),
            edit_proposals_applied=proposals_applied,
            edit_proposals_rejected=proposals_rejected,
        )
        self.records.append(record)
        self._save()

    def compare_versions(self, domain: str = None) -> dict:
        """Return mean imp@k grouped by meta_strategy_version.

        Use this to decide whether MetaProposalStrategy v(n+1) is better than v(n).
        """
        filtered = [
            r for r in self.records
            if domain is None or r.domain == domain
        ]
        by_version: dict[int, list[float]] = {}
        for r in filtered:
            by_version.setdefault(r.meta_strategy_version, []).append(r.imp_at_k)
        return {
            v: {
                "mean_imp_at_k": round(sum(vals) / len(vals), 4),
                "n": len(vals),
                "vals": vals,
            }
            for v, vals in sorted(by_version.items())
        }

    def print_report(self, domain: str = None):
        comparison = self.compare_versions(domain)
        domain_label = f" ({domain})" if domain else ""
        print(f"\n=== imp@k by MetaProposalStrategy version{domain_label} ===")
        for version, stats in comparison.items():
            print(
                f"  v{version}: mean imp@k = {stats['mean_imp_at_k']:+.1%}  "
                f"(n={stats['n']})"
            )


def backfill_score_delta(
    edit_history_path: str = str(Path.home() / ".auto-verifier-data" / "rubric_feedback" / "self_edits.json"),
    rubric_store=None,
):
    """Backfill score_delta on edit history entries that lack it.

    Called at the start of the next auto_improve() run.  Compares the
    overall_score of the most recent rubric against the score recorded
    at the time each edit was applied.

    Args:
        edit_history_path: path to self_edits.json
        rubric_store: RubricStore instance to read scores from
    """
    path = Path(edit_history_path)
    if not path.exists() or rubric_store is None:
        return

    try:
        history = json.loads(path.read_text())
    except (json.JSONDecodeError, IOError):
        return

    rubrics = rubric_store.list_all()
    if not rubrics:
        return

    changed = False
    for entry in history:
        if "score_delta" in entry:
            continue  # already filled

        applied_at = entry.get("applied_at", "")
        if not applied_at:
            continue

        # Find the first rubric scored *after* this edit was applied
        post_scores = [
            r.overall_score for r in rubrics
            if r.created_at > applied_at
        ]
        if not post_scores:
            continue  # no runs since this edit — leave for next time

        # Find the last rubric scored *before* this edit
        pre_scores = [
            r.overall_score for r in rubrics
            if r.created_at <= applied_at
        ]
        pre = pre_scores[-1] if pre_scores else 0.0
        post = post_scores[0]

        entry["score_delta"] = round(post - pre, 4)
        changed = True

    if changed:
        path.write_text(json.dumps(history, indent=2))
