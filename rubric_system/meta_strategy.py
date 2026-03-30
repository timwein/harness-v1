"""Meta-level proposal strategy — the hyperagent upgrade.

Makes SelfEditor's proposal generation strategy editable rather than hardcoded.
MetaStrategyEditor updates signal weights based on which proposal types
historically improve scores.  MetaStrategyStore enables cross-domain transfer
of improvement strategies.

Based on DGM-H (Zhang et al., 2026) — the meta-level modification procedure
is itself part of the editable program.
"""

from dataclasses import dataclass, field
from datetime import datetime
import json
from pathlib import Path

META_STRATEGY_PATH = ".rubric_feedback/meta_strategy.json"
META_STRATEGY_OUTCOMES_PATH = ".rubric_feedback/meta_strategy_outcomes.json"


# ---------------------------------------------------------------------------
# Upgrade 1 — Editable proposal strategy
# ---------------------------------------------------------------------------

@dataclass
class MetaProposalStrategy:
    """The strategy SelfEditor uses to generate proposals.

    This object is itself editable — MetaStrategyEditor updates it based on
    which proposal types have historically produced score improvements.
    """

    # Weight for each proposal trigger signal (0.0–1.0).
    # Higher → more likely to generate a proposal for this signal type.
    signal_weights: dict = field(default_factory=lambda: {
        "high_false_positive": 0.8,
        "always_passes": 0.6,
        "high_value_low_pass": 0.9,
        "non_discriminating": 0.7,
        "stuck_criteria": 0.5,
        "prompt_pattern": 0.4,
    })

    # Minimum feedback entries before generating a proposal
    min_evidence_threshold: int = 2

    # How to rank competing proposals before applying
    proposal_ranking_prompt: str = (
        "Rank these edit proposals by expected score improvement. "
        "Prioritize proposals that address criteria with the highest score variance "
        "and most feedback entries. De-prioritize proposals that have been attempted "
        "before without measurable improvement."
    )

    # Which files/functions SelfEditor is allowed to modify
    edit_scope: list = field(default_factory=lambda: [
        "rubric_harness.py",
        "rubric_system/scoring_engine.py",
        "rubric_system/self_improve.py",
    ])

    version: int = 1
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def save(self, path: str = META_STRATEGY_PATH):
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(self.__dict__, indent=2))

    @classmethod
    def load(cls, path: str = META_STRATEGY_PATH) -> "MetaProposalStrategy":
        p = Path(path)
        if p.exists():
            try:
                data = json.loads(p.read_text())
                return cls(**data)
            except (json.JSONDecodeError, TypeError):
                pass
        return cls()  # defaults


class MetaStrategyEditor:
    """Updates MetaProposalStrategy based on which proposal types historically work.

    This is the hyperagent move: the system that rewrites scoring logic
    is itself subject to rewriting based on whether its rewrites improve scores.

    Call after every N SelfEditor runs (recommended: N=3).
    """

    def __init__(self, strategy: MetaProposalStrategy, edit_history_path: str):
        self.strategy = strategy
        self.edit_history_path = Path(edit_history_path)

    def update_signal_weights(self):
        """Adjust signal_weights based on edit history.

        For each proposal type: compute win_rate = accepted proposals that
        improved score / total proposals of that type.  Update weight toward
        win_rate with exponential moving average decay.
        """
        if not self.edit_history_path.exists():
            return

        try:
            history = json.loads(self.edit_history_path.read_text())
        except (json.JSONDecodeError, IOError):
            return

        outcomes_by_type: dict[str, list[bool]] = {}

        for entry in history:
            ptype = entry.get("edit_type", "unknown")
            if ptype == "unknown":
                # Try nested location for older entries
                ptype = (entry.get("proposal", {})
                         .get("performance_data", {})
                         .get("reason_for_edit", "unknown"))
            improved = (
                entry.get("score_delta", 0) > 0
                and entry.get("accepted", False)
            )
            outcomes_by_type.setdefault(ptype, []).append(improved)

        for ptype, outcomes in outcomes_by_type.items():
            if len(outcomes) < 3:
                continue  # not enough data
            win_rate = sum(outcomes) / len(outcomes)
            current = self.strategy.signal_weights.get(ptype, 0.5)
            # Exponential moving average: decay toward observed win_rate
            self.strategy.signal_weights[ptype] = round(
                0.7 * current + 0.3 * win_rate, 3
            )

        self.strategy.version += 1
        self.strategy.updated_at = datetime.utcnow().isoformat()
        self.strategy.save()


# ---------------------------------------------------------------------------
# Upgrade 4 — Cross-domain meta-strategy transfer
# ---------------------------------------------------------------------------

@dataclass
class MetaStrategyOutcome:
    """Records whether a strategy type improved scores in a given domain."""

    strategy_type: str          # e.g. "feedback-pattern-edit:non_discriminating"
    source_domain: str          # domain where this was learned
    imp_at_k: float             # improvement achieved
    transferred_to: list = field(default_factory=list)
    recorded_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())


class MetaStrategyStore:
    """Persists strategy outcomes for cross-domain transfer.

    Usage in LearningIntegrator.build_learning_context():
        store = MetaStrategyStore()
        hints = store.get_transfer_hints(target_domain="exec_summary")
        # → "In similar domains …, these strategies were effective: [...]"
    """

    def __init__(self, path: str = META_STRATEGY_OUTCOMES_PATH):
        self.path = Path(path)
        self.outcomes: list[MetaStrategyOutcome] = self._load()

    def _load(self) -> list:
        if self.path.exists():
            try:
                return [
                    MetaStrategyOutcome(**r)
                    for r in json.loads(self.path.read_text())
                ]
            except (json.JSONDecodeError, TypeError):
                pass
        return []

    def _save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps([r.__dict__ for r in self.outcomes], indent=2)
        )

    def record(self, strategy_type: str, domain: str, imp_at_k: float):
        self.outcomes.append(MetaStrategyOutcome(
            strategy_type=strategy_type,
            source_domain=domain,
            imp_at_k=imp_at_k,
        ))
        self._save()

    def get_transfer_hints(self, target_domain: str, top_n: int = 3) -> str:
        """Return a prompt string summarizing which strategies worked in similar domains.

        Injects into LearningIntegrator.build_learning_context() so the meta agent
        starts with inherited strategies rather than from scratch.
        """
        # Filter to outcomes that actually improved scores
        effective = [
            o for o in self.outcomes
            if o.imp_at_k > 0.05 and o.source_domain != target_domain
        ]

        if not effective:
            return ""

        # Sort by imp_at_k descending, take top N
        top = sorted(effective, key=lambda o: o.imp_at_k, reverse=True)[:top_n]

        lines = [
            "Cross-domain strategy transfer (from prior self-improvement runs):",
            "The following improvement strategies have worked in similar domains",
            f"and should be prioritized when generating proposals for '{target_domain}':\n",
        ]
        for o in top:
            lines.append(
                f"  - [{o.source_domain}] {o.strategy_type}: "
                f"+{o.imp_at_k:.1%} improvement"
            )
        return "\n".join(lines)
