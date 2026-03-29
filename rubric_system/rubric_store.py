from __future__ import annotations
"""
RubricRAG Store — JSONL-based persistent store for RubricRAG-style retrieval.

Stores lightweight rubric records from completed runs so future rubric
generation can retrieve similar prior rubrics as seed criteria, grounding
new rubric generation in proven patterns rather than generic intuition.

Usage:
    store = RubricStore()
    store.save(task, rubric, final_score=0.91)
    section = store.format_retrieval_section(task)  # inject into generation prompt
"""

import json
import re
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any


DEFAULT_STORE_PATH = ".rubric_store/rubrics.jsonl"


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

    Retrieval uses Jaccard similarity over task word tokens — no external
    dependencies, no embeddings, no pip installs required.

    Retrieved criteria are formatted as a prompt section for injection into
    rubric generation, paralleling how contrastive_section works in the
    exemplar pipeline.
    """

    def __init__(self, store_path: str = DEFAULT_STORE_PATH):
        self.store_path = Path(store_path)
        self.store_path.parent.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Write
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
    # Read
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
    # Format for prompt injection
    # ------------------------------------------------------------------

    def format_retrieval_section(self, task: str, top_k: int = 3) -> str:
        """Retrieve similar rubrics and format them as a generation-prompt section.

        Returns a formatted string ready for injection into the rubric
        generation prompt (appended after research_section, similar to
        how contrastive_section is appended). Returns empty string when
        no similar rubrics exist.

        Args:
            task: current task description
            top_k: number of prior rubrics to retrieve

        Returns:
            Formatted prompt section, or "" if nothing retrieved.
        """
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
