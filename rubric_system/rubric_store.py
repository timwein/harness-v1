from __future__ import annotations
"""
RubricRAG Store — JSONL-based persistent store for RubricRAG-style retrieval.

Stores lightweight rubric records from completed runs so future rubric
generation can retrieve similar prior rubrics as seed criteria, grounding
new rubric generation in proven patterns rather than generic intuition.

Two stores:
- rubrics.jsonl: whole-rubric records (task + all criteria + final score)
- criteria.jsonl: per-criterion records with effectiveness metadata (discriminative
  power, score contribution, stuck/discriminating flags) extracted from iteration history

Usage:
    store = RubricStore()
    store.save(task, rubric, final_score=0.91)
    store.save_criterion_effectiveness(task, rubric, iterations)
    section = store.format_retrieval_section(task)  # inject into generation prompt
"""

import json
import re
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any


DEFAULT_STORE_PATH = str(Path.home() / ".auto-verifier-data" / "rag_rubrics.jsonl")
DEFAULT_CRITERIA_STORE_PATH = str(Path.home() / ".auto-verifier-data" / "rag_criteria.jsonl")

# Quality gate thresholds for seed selection
_MIN_DISCRIMINATIVE_POWER = 0.05   # criteria that never moved score are not useful
_MAX_SCORE_CONTRIBUTION = 0.95     # always-passing criteria are trivial — skip
_MIN_SCORE_CONTRIBUTION = 0.05     # always-failing criteria are broken — skip
_MAX_STUCK_RATE = 0.70             # skip criteria that were stuck in >70% of their uses


def _tokenize(text: str) -> set:
    """Extract lowercase word tokens (len >= 3) from text."""
    return set(re.findall(r'\b[a-z]{3,}\b', text.lower()))


def _jaccard(a: set, b: set) -> float:
    """Jaccard similarity coefficient between two token sets."""
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


class RubricStore:
    """JSONL-based persistent store for RubricRAG-style rubric retrieval.

    Stores one record per line (JSONL) in a local file. Each record captures
    the task description, domain, criteria list, final score, and timestamp
    from a completed rubric run.

    Also maintains a per-criterion effectiveness store that tracks discriminative
    power, score contribution, and stuck/discriminating flags for each criterion
    observed across runs. This powers non-binary rubric seeding: future rubric
    generation retrieves individual criteria that proved effective on similar tasks,
    injecting them as "prior art seeds" rather than copying whole rubrics wholesale.

    Retrieval uses Jaccard similarity over task word tokens — no external
    dependencies, no embeddings, no pip installs required.
    """

    def __init__(self, store_path: str = DEFAULT_STORE_PATH,
                 criteria_path: str = DEFAULT_CRITERIA_STORE_PATH):
        self.store_path = Path(store_path).expanduser()
        self.store_path.parent.mkdir(parents=True, exist_ok=True)
        self.criteria_path = Path(criteria_path).expanduser()
        self.criteria_path.parent.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Write — whole rubric
    # ------------------------------------------------------------------

    def save(self, task: str, rubric: Any, final_score: float) -> None:
        """Persist a completed rubric to the JSONL store.

        Args:
            task: the task description string
            rubric: Rubric object with .domain and .criteria attributes
            final_score: final score as a percentage (0.0 – 1.0)
        """
        criteria_list = []
        for c in getattr(rubric, "criteria", []):
            scoring = getattr(c, "scoring", None)
            method_val = None
            max_pts = 1
            if scoring is not None:
                method_obj = getattr(scoring, "method", None)
                if method_obj is not None:
                    method_val = getattr(method_obj, "value", str(method_obj))
                max_pts = getattr(scoring, "max_points", 1)

            criteria_list.append({
                "id": getattr(c, "id", ""),
                "category": getattr(c, "category", ""),
                "description": getattr(c, "description", ""),
                "pass_condition": getattr(c, "pass_condition", ""),
                "scoring_method": method_val,
                "max_points": max_pts,
                "research_basis": getattr(c, "research_basis", "") or "",
            })

        record: Dict[str, Any] = {
            "task": task,
            "domain": getattr(rubric, "domain", "") or "",
            "criteria": criteria_list,
            "final_score": final_score,
            "timestamp": datetime.utcnow().isoformat(),
        }
        with self.store_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")

    # ------------------------------------------------------------------
    # Write — per-criterion effectiveness
    # ------------------------------------------------------------------

    def save_criterion_effectiveness(
        self, task: str, rubric: Any, iterations: list
    ) -> None:
        """Extract per-criterion effectiveness metadata and persist to criteria store.

        For each criterion in the rubric, computes effectiveness stats from the
        iteration history:
        - discriminative_power: range of scores across iterations (max - min).
          High value means the criterion reliably separated good from bad outputs.
        - score_contribution: final iteration percentage (how well it was satisfied
          at the end of the run).
        - is_stuck: True if discriminative_power < 0.05 (score never moved — the
          criterion either always passed or always failed, providing no signal).
        - is_discriminating: True if discriminative_power > 0.20 (the criterion
          produced meaningful variance across iterations).

        These metrics are used as a quality gate during retrieval: only criteria
        with proven discriminative power are surfaced as seeds for new rubrics.

        Args:
            task: the task description string
            rubric: Rubric object with .domain and .criteria attributes
            iterations: list of Iteration objects (each has .criterion_scores)
        """
        domain = getattr(rubric, "domain", "") or ""

        # Build criterion_id -> [percentage at each iteration] map
        criterion_percentages: Dict[str, List[float]] = {}
        for iteration in iterations:
            for cs in getattr(iteration, "criterion_scores", []):
                cid = getattr(cs, "criterion_id", "")
                pct = float(getattr(cs, "percentage", 0.0))
                if cid not in criterion_percentages:
                    criterion_percentages[cid] = []
                criterion_percentages[cid].append(pct)

        records_to_write = []
        for criterion in getattr(rubric, "criteria", []):
            cid = getattr(criterion, "id", "")
            percentages = criterion_percentages.get(cid, [])
            if not percentages:
                continue

            min_pct = min(percentages)
            max_pct = max(percentages)
            discriminative_power = round(max_pct - min_pct, 4)
            score_contribution = round(percentages[-1], 4)  # final iteration score
            is_stuck = discriminative_power < 0.05
            is_discriminating = discriminative_power > 0.20

            scoring = getattr(criterion, "scoring", None)
            method_val = None
            max_pts = 3
            if scoring is not None:
                method_obj = getattr(scoring, "method", None)
                if method_obj is not None:
                    method_val = getattr(method_obj, "value", str(method_obj))
                max_pts = getattr(scoring, "max_points", 3)

            records_to_write.append({
                "criterion_id": cid,
                "description": getattr(criterion, "description", ""),
                "category": getattr(criterion, "category", ""),
                "pass_condition": getattr(criterion, "pass_condition", ""),
                "scoring_method": method_val,
                "max_points": max_pts,
                "research_basis": getattr(criterion, "research_basis", "") or "",
                "task": task,
                "domain": domain,
                "discriminative_power": discriminative_power,
                "score_contribution": score_contribution,
                "is_stuck": is_stuck,
                "is_discriminating": is_discriminating,
                "iterations_count": len(percentages),
                "timestamp": datetime.utcnow().isoformat(),
            })

        if records_to_write:
            with self.criteria_path.open("a", encoding="utf-8") as fh:
                for rec in records_to_write:
                    fh.write(json.dumps(rec, ensure_ascii=False) + "\n")

    # ------------------------------------------------------------------
    # Read — whole rubric
    # ------------------------------------------------------------------

    def _load_all(self) -> List[Dict[str, Any]]:
        """Load all records from the JSONL store. Silently skips bad lines."""
        if not self.store_path.exists():
            return []
        records: List[Dict[str, Any]] = []
        with self.store_path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        return records

    def retrieve(self, task: str, top_k: int = 3) -> List[Dict[str, Any]]:
        """Return the top_k most similar prior rubrics using Jaccard similarity.

        Similarity is computed over word tokens in the task descriptions.
        Records with zero overlap are excluded.

        Args:
            task: current task description
            top_k: maximum number of records to return

        Returns:
            List of record dicts sorted by similarity descending.
        """
        records = self._load_all()
        if not records:
            return []

        query_tokens = _tokenize(task)
        if not query_tokens:
            # No tokens → return most recent records as a fallback
            return records[-top_k:]

        scored: List[tuple] = []
        for record in records:
            rec_tokens = _tokenize(record.get("task", ""))
            sim = _jaccard(query_tokens, rec_tokens)
            if sim > 0.0:
                scored.append((sim, record))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [r for _, r in scored[:top_k]]

    def count(self) -> int:
        """Return total number of stored rubric records."""
        return len(self._load_all())

    # ------------------------------------------------------------------
    # Read — per-criterion
    # ------------------------------------------------------------------

    def _load_all_criteria(self) -> List[Dict[str, Any]]:
        """Load all per-criterion effectiveness records. Silently skips bad lines."""
        if not self.criteria_path.exists():
            return []
        records: List[Dict[str, Any]] = []
        with self.criteria_path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        return records

    def retrieve_criteria(
        self,
        task: str,
        top_k: int = 12,
        min_discriminative_power: float = _MIN_DISCRIMINATIVE_POWER,
    ) -> List[Dict[str, Any]]:
        """Retrieve individual criteria relevant to the task, filtered by quality.

        Algorithm:
        1. Load all per-criterion effectiveness records.
        2. Group by criterion_id to aggregate stats across multiple runs
           (a criterion that appeared in 5 runs gets averaged stats).
        3. Apply quality gate: exclude always-passing, always-failing, and
           mostly-stuck criteria.
        4. Score each criterion by relevance to the task:
               score = (0.6 * task_sim + 0.4 * desc_sim) * quality_boost
           where quality_boost = 1.0 + avg_discriminative_power, rewarding
           criteria that proved most useful at separating quality levels.
        5. Return top_k by score.

        Degrades gracefully to empty list when the criteria store is empty.

        Args:
            task: current task description
            top_k: maximum number of criteria to return
            min_discriminative_power: minimum avg discriminative power to pass gate

        Returns:
            List of criterion dicts with effectiveness metadata, sorted by relevance.
        """
        raw_records = self._load_all_criteria()
        if not raw_records:
            return []

        # Aggregate by criterion_id
        groups: Dict[str, Dict[str, Any]] = {}
        for rec in raw_records:
            cid = rec.get("criterion_id", "")
            if not cid:
                continue
            if cid not in groups:
                groups[cid] = {
                    "criterion_id": cid,
                    "description": rec.get("description", ""),
                    "category": rec.get("category", ""),
                    "pass_condition": rec.get("pass_condition", ""),
                    "scoring_method": rec.get("scoring_method", ""),
                    "max_points": rec.get("max_points", 3),
                    "research_basis": rec.get("research_basis", ""),
                    "domain": rec.get("domain", ""),
                    # Aggregation lists
                    "_disc_powers": [],
                    "_score_contribs": [],
                    "_stuck_flags": [],
                    "_task_tokens": set(),
                }
            g = groups[cid]
            g["_disc_powers"].append(rec.get("discriminative_power", 0.0))
            g["_score_contribs"].append(rec.get("score_contribution", 0.5))
            g["_stuck_flags"].append(bool(rec.get("is_stuck", False)))
            g["_task_tokens"] |= _tokenize(rec.get("task", ""))

        query_tokens = _tokenize(task)
        scored: List[tuple] = []

        for cid, g in groups.items():
            disc_list = g["_disc_powers"]
            contrib_list = g["_score_contribs"]
            stuck_list = g["_stuck_flags"]
            times_used = len(disc_list)

            avg_disc = sum(disc_list) / times_used
            avg_contrib = sum(contrib_list) / times_used
            stuck_rate = sum(1 for f in stuck_list if f) / times_used

            # Quality gate
            if avg_disc < min_discriminative_power and stuck_rate > _MAX_STUCK_RATE:
                continue  # mostly stuck — provides no signal
            if avg_contrib > _MAX_SCORE_CONTRIBUTION:
                continue  # always-passing — too easy to be useful as a seed
            if avg_contrib < _MIN_SCORE_CONTRIBUTION:
                continue  # always-failing — broken or mis-calibrated

            # Relevance scoring
            task_sim = _jaccard(query_tokens, g["_task_tokens"])
            desc_tokens = _tokenize(g["description"] + " " + g["category"])
            desc_sim = _jaccard(query_tokens, desc_tokens)
            relevance = 0.6 * task_sim + 0.4 * desc_sim

            if relevance <= 0.0:
                continue  # no overlap with query — skip

            # Quality boost: more discriminating criteria ranked higher
            quality_boost = 1.0 + avg_disc
            final_score = relevance * quality_boost

            scored.append((final_score, {
                "criterion_id": cid,
                "description": g["description"],
                "category": g["category"],
                "pass_condition": g["pass_condition"],
                "scoring_method": g["scoring_method"],
                "max_points": g["max_points"],
                "research_basis": g["research_basis"],
                "avg_discriminative_power": round(avg_disc, 3),
                "avg_score_contribution": round(avg_contrib, 3),
                "times_used": times_used,
            }))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [c for _, c in scored[:top_k]]

    def count_criteria(self) -> int:
        """Return total number of per-criterion effectiveness records."""
        return len(self._load_all_criteria())

    # ------------------------------------------------------------------
    # Format for prompt injection
    # ------------------------------------------------------------------

    def format_retrieval_section(self, task: str, top_k: int = 3) -> str:
        """Retrieve similar rubric criteria and format them as a generation-prompt section.

        Prefers per-criterion retrieval (criteria store) over whole-rubric retrieval
        when criteria effectiveness data is available. Per-criterion retrieval is more
        targeted: it selects individual criteria that proved discriminating on similar
        tasks, filters out always-passing/stuck criteria, and surfaces them as "prior
        art seeds" with effectiveness metadata.

        Falls back to whole-rubric retrieval when the criteria store is empty (e.g.,
        before any runs have been completed and effectiveness data accumulated).

        Returns empty string when neither store has relevant data.

        Args:
            task: current task description
            top_k: number of prior rubrics to retrieve (used for whole-rubric fallback)

        Returns:
            Formatted prompt section, or "" if nothing retrieved.
        """
        # Try per-criterion retrieval first
        criteria_seeds = self.retrieve_criteria(task, top_k=12)
        if criteria_seeds:
            return self._format_criteria_seeds(criteria_seeds)

        # Fall back to whole-rubric retrieval
        retrieved = self.retrieve(task, top_k=top_k)
        if not retrieved:
            return ""

        lines = [
            "RETRIEVED RUBRIC SEEDS — Prior rubrics for similar tasks. "
            "Use these as seeds: adopt criteria that are domain-appropriate, "
            "refine ones that are too vague, and skip any that don't apply to "
            "the current task. Do not copy them blindly — treat them as a "
            "starting checklist that your domain research may override.\n",
        ]

        for i, record in enumerate(retrieved, 1):
            domain = record.get("domain", "unknown") or "unknown"
            score = record.get("final_score", 0.0)
            task_preview = (record.get("task", "") or "")[:100]
            criteria = record.get("criteria", [])

            lines.append(
                f"Prior Rubric {i}  "
                f"(domain: {domain}, final score: {score:.0%}, "
                f"{len(criteria)} criteria):"
            )
            lines.append(f"  Task: {task_preview}")

            for c in criteria:
                desc = (c.get("description", "") or "")[:120]
                pass_cond = (c.get("pass_condition", "") or "")[:80]
                method = c.get("scoring_method", "") or ""
                pts = c.get("max_points", 1)
                category = c.get("category", "") or ""
                research = (c.get("research_basis", "") or "")[:100]

                cat_tag = f"[{category}] " if category else ""
                lines.append(f"    - {cat_tag}{desc}")
                if pass_cond:
                    lines.append(f"      Pass condition: {pass_cond}")
                if method:
                    lines.append(f"      Scoring: {method} ({pts} pts)")
                if research:
                    lines.append(f"      Research basis: {research}")

            lines.append("")

        return "\n".join(lines)

    def _format_criteria_seeds(self, criteria: List[Dict[str, Any]]) -> str:
        """Format retrieved criteria as a 'prior art seeds' prompt section.

        Uses language that instructs the rubric architect to treat these as
        starting points — adopt, adapt, or discard — never copy wholesale.
        Includes discriminative power metadata so the architect can see which
        criteria proved most useful at separating quality levels.
        """
        lines = [
            "PRIOR ART CRITERION SEEDS — The following criteria from past evaluations "
            "proved effective for similar tasks (filtered: stuck and always-passing "
            "criteria excluded). Consider incorporating or adapting them into the new "
            "rubric, but ALWAYS generate the optimal rubric for THIS specific task. "
            "These are informed starting points, not constraints — refine, extend, or "
            "replace any seed that doesn't fit the current domain or task requirements.\n",
        ]

        for c in criteria:
            cid = c.get("criterion_id", "")
            desc = (c.get("description", "") or "")[:120]
            pass_cond = (c.get("pass_condition", "") or "")[:80]
            method = c.get("scoring_method", "") or ""
            pts = c.get("max_points", 3)
            category = c.get("category", "") or ""
            research = (c.get("research_basis", "") or "")[:100]
            disc = c.get("avg_discriminative_power", 0.0)
            contrib = c.get("avg_score_contribution", 0.5)
            uses = c.get("times_used", 1)

            cat_tag = f"[{category}] " if category else ""
            # Effectiveness tag: flag how discriminating this criterion was
            if disc >= 0.30:
                eff_tag = "HIGH discriminative power"
            elif disc >= 0.15:
                eff_tag = "moderate discriminative power"
            else:
                eff_tag = "low discriminative power"

            lines.append(f"  Seed [{cid}]: {cat_tag}{desc}")
            if pass_cond:
                lines.append(f"    Pass condition: {pass_cond}")
            if method:
                lines.append(f"    Scoring: {method} ({pts} pts)")
            lines.append(
                f"    Effectiveness: {eff_tag} "
                f"(disc={disc:.2f}, avg_score={contrib:.0%}, used={uses}x)"
            )
            if research:
                lines.append(f"    Research basis: {research}")
            lines.append("")

        return "\n".join(lines)
