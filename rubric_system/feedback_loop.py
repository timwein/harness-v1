#!/usr/bin/env python3
"""
Feedback Self-Improvement Loop

Persistent feedback memory that makes the rubric system learn from human input.
Organizes feedback into structured YAML files by type, and injects relevant
feedback into generation/scoring prompts during the GAN loop.

Feedback types:
  - rubric: "This criterion is too strict / too lenient / missing something"
  - scoring: "The scorer misjudged this — evidence was there but missed"
  - verification: "The verification step should have caught X"
  - general: "Overall preference / style / priority feedback"

Usage:
    from rubric_system.feedback_loop import FeedbackStore, FeedbackInjector

    store = FeedbackStore()  # defaults to .rubric_feedback/
    store.add("rubric", "src_freshness criterion is too strict for historical topics",
              task="Write a history of computing", criterion_id="src_freshness")

    injector = FeedbackInjector(store)
    context = injector.get_relevant_feedback(task="Write a research brief", domain="knowledge_work")
"""

import os
import json
import re
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Optional
from enum import Enum


class FeedbackType(Enum):
    RUBRIC = "rubric"
    SCORING = "scoring"
    VERIFICATION = "verification"
    GENERAL = "general"


@dataclass
class FeedbackEntry:
    """A single piece of human feedback."""
    id: str
    feedback_type: str  # FeedbackType value
    content: str  # The actual feedback text
    task: str = ""  # What task triggered this
    domain: str = ""  # Domain context
    criterion_id: str = ""  # Specific criterion if applicable
    sub_attribute_id: str = ""  # Specific sub-attribute if applicable
    tags: list[str] = field(default_factory=list)  # Searchable tags
    created_at: str = ""
    applied_count: int = 0  # How many times this was used in a prompt
    effectiveness: Optional[float] = None  # Did applying it improve scores?


class FeedbackStore:
    """
    Persistent feedback storage organized by type.

    Directory structure:
        feedback_dir/
            rubric/
                2026-03-20_src_freshness_too_strict.json
                2026-03-20_missing_criterion.json
            scoring/
                2026-03-20_missed_evidence.json
            verification/
                2026-03-20_should_check_urls.json
            general/
                2026-03-20_prefer_concise.json
            _index.json  # Fast lookup index
    """

    def __init__(self, feedback_dir: str = str(Path.home() / ".auto-verifier-data" / "rubric_feedback")):
        self.feedback_dir = Path(feedback_dir)
        self._ensure_dirs()
        self._index: dict[str, list[str]] = {}  # type -> [ids]
        self._entries: dict[str, FeedbackEntry] = {}  # id -> entry
        self._load_index()

    def _ensure_dirs(self):
        for ft in FeedbackType:
            (self.feedback_dir / ft.value).mkdir(parents=True, exist_ok=True)

    def _index_path(self) -> Path:
        return self.feedback_dir / "_index.json"

    def _load_index(self):
        """Load all feedback entries into memory."""
        self._index = {ft.value: [] for ft in FeedbackType}
        self._entries = {}

        for ft in FeedbackType:
            type_dir = self.feedback_dir / ft.value
            for f in sorted(type_dir.glob("*.json")):
                try:
                    data = json.loads(f.read_text())
                    entry = FeedbackEntry(**data)
                    self._entries[entry.id] = entry
                    self._index[ft.value].append(entry.id)
                except (json.JSONDecodeError, TypeError) as e:
                    pass  # Skip malformed files

    def add(
        self,
        feedback_type: str,
        content: str,
        task: str = "",
        domain: str = "",
        criterion_id: str = "",
        sub_attribute_id: str = "",
        tags: list[str] = None,
    ) -> FeedbackEntry:
        """Add a new feedback entry."""
        now = datetime.utcnow()
        entry_id = f"{feedback_type}_{now.strftime('%Y%m%d_%H%M%S')}_{len(self._entries)}"

        # Auto-generate tags from content
        auto_tags = self._extract_tags(content, criterion_id, domain)
        all_tags = list(set((tags or []) + auto_tags))

        entry = FeedbackEntry(
            id=entry_id,
            feedback_type=feedback_type,
            content=content,
            task=task,
            domain=domain,
            criterion_id=criterion_id,
            sub_attribute_id=sub_attribute_id,
            tags=all_tags,
            created_at=now.isoformat(),
        )

        # Save to file
        slug = re.sub(r'[^a-z0-9]+', '_', content[:50].lower()).strip('_')
        filename = f"{now.strftime('%Y-%m-%d')}_{slug}.json"
        filepath = self.feedback_dir / feedback_type / filename

        # Handle collision
        counter = 1
        while filepath.exists():
            filepath = self.feedback_dir / feedback_type / f"{now.strftime('%Y-%m-%d')}_{slug}_{counter}.json"
            counter += 1

        filepath.write_text(json.dumps(asdict(entry), indent=2))

        # Update in-memory index
        self._entries[entry.id] = entry
        if feedback_type not in self._index:
            self._index[feedback_type] = []
        self._index[feedback_type].append(entry.id)

        return entry

    def get_all(self, feedback_type: str = None) -> list[FeedbackEntry]:
        """Get all entries, optionally filtered by type."""
        if feedback_type:
            ids = self._index.get(feedback_type, [])
            return [self._entries[i] for i in ids if i in self._entries]
        return list(self._entries.values())

    def get_by_criterion(self, criterion_id: str) -> list[FeedbackEntry]:
        """Get all feedback for a specific criterion."""
        return [e for e in self._entries.values() if e.criterion_id == criterion_id]

    def get_by_domain(self, domain: str) -> list[FeedbackEntry]:
        """Get all feedback for a specific domain."""
        return [e for e in self._entries.values() if e.domain == domain]

    def search(self, query: str) -> list[FeedbackEntry]:
        """Search feedback by content or tags."""
        query_lower = query.lower()
        results = []
        for entry in self._entries.values():
            if (query_lower in entry.content.lower() or
                any(query_lower in t.lower() for t in entry.tags) or
                query_lower in entry.criterion_id.lower()):
                results.append(entry)
        return results

    def mark_applied(self, entry_id: str, effectiveness: float = None):
        """Mark feedback as applied and optionally record effectiveness."""
        if entry_id in self._entries:
            entry = self._entries[entry_id]
            entry.applied_count += 1
            if effectiveness is not None:
                entry.effectiveness = effectiveness
            # Re-save to disk
            self._save_entry(entry)

    def _save_entry(self, entry: FeedbackEntry):
        """Re-save an entry to disk after update."""
        type_dir = self.feedback_dir / entry.feedback_type
        for f in type_dir.glob("*.json"):
            try:
                data = json.loads(f.read_text())
                if data.get("id") == entry.id:
                    f.write_text(json.dumps(asdict(entry), indent=2))
                    return
            except (json.JSONDecodeError, TypeError):
                pass

    def _extract_tags(self, content: str, criterion_id: str, domain: str) -> list[str]:
        """Auto-extract searchable tags from feedback content."""
        tags = []
        if criterion_id:
            tags.append(criterion_id)
        if domain:
            tags.append(domain)

        # Extract common quality dimensions mentioned in feedback
        keywords = {
            "strict": "strictness",
            "lenient": "leniency",
            "miss": "false_negative",
            "false positive": "false_positive",
            "too harsh": "strictness",
            "not catching": "false_negative",
            "source": "sources",
            "citation": "citations",
            "format": "formatting",
            "tone": "tone",
            "length": "length",
            "evidence": "evidence",
            "score": "scoring",
        }
        content_lower = content.lower()
        for keyword, tag in keywords.items():
            if keyword in content_lower:
                tags.append(tag)

        return tags

    def summary(self) -> dict:
        """Get a summary of all feedback."""
        summary = {
            "total": len(self._entries),
            "by_type": {ft.value: len(self._index.get(ft.value, [])) for ft in FeedbackType},
            "most_referenced_criteria": {},
            "recent": [],
        }

        # Count criteria references
        crit_counts: dict[str, int] = {}
        for e in self._entries.values():
            if e.criterion_id:
                crit_counts[e.criterion_id] = crit_counts.get(e.criterion_id, 0) + 1
        summary["most_referenced_criteria"] = dict(
            sorted(crit_counts.items(), key=lambda x: -x[1])[:10]
        )

        # Recent entries
        recent = sorted(self._entries.values(), key=lambda e: e.created_at, reverse=True)[:5]
        summary["recent"] = [{"id": e.id, "type": e.feedback_type, "content": e.content[:80]} for e in recent]

        return summary


class FeedbackInjector:
    """
    Injects relevant feedback into generation and scoring prompts.

    Used by RubricLoop to make the system learn from human preferences.
    """

    def __init__(self, store: FeedbackStore):
        self.store = store

    def get_relevant_feedback(
        self,
        task: str = "",
        domain: str = "",
        criteria_ids: list[str] = None,
        feedback_types: list[str] = None,
        max_entries: int = 10,
    ) -> list[FeedbackEntry]:
        """Find feedback entries relevant to the current context."""
        candidates = []

        for entry in self.store.get_all():
            score = self._relevance_score(entry, task, domain, criteria_ids or [], feedback_types)
            if score > 0:
                candidates.append((score, entry))

        candidates.sort(key=lambda x: -x[0])
        return [entry for _, entry in candidates[:max_entries]]

    def format_for_generation_prompt(
        self,
        task: str,
        domain: str,
        criteria_ids: list[str],
    ) -> str:
        """Format relevant feedback as a prompt section for content generation."""
        entries = self.get_relevant_feedback(
            task=task,
            domain=domain,
            criteria_ids=criteria_ids,
            feedback_types=["rubric", "general"],
            max_entries=8,
        )

        if not entries:
            return ""

        lines = ["\nHUMAN FEEDBACK HISTORY (apply these learnings):"]
        for entry in entries:
            prefix = f"[{entry.feedback_type.upper()}]"
            criterion_note = f" (re: {entry.criterion_id})" if entry.criterion_id else ""
            lines.append(f"  {prefix}{criterion_note}: {entry.content}")

        return "\n".join(lines)

    def format_for_scoring_prompt(
        self,
        domain: str,
        criteria_ids: list[str],
    ) -> str:
        """Format relevant feedback as a prompt section for scoring/measurement."""
        entries = self.get_relevant_feedback(
            domain=domain,
            criteria_ids=criteria_ids,
            feedback_types=["scoring", "verification"],
            max_entries=6,
        )

        if not entries:
            return ""

        lines = ["\nSCORING CALIBRATION (from human feedback):"]
        for entry in entries:
            criterion_note = f" [{entry.criterion_id}]" if entry.criterion_id else ""
            lines.append(f"  - {entry.content}{criterion_note}")

        return "\n".join(lines)

    def format_for_rubric_generation(
        self,
        task: str,
        domain: str,
    ) -> str:
        """Format feedback that should influence rubric construction."""
        entries = self.get_relevant_feedback(
            task=task,
            domain=domain,
            feedback_types=["rubric"],
            max_entries=8,
        )

        if not entries:
            return ""

        lines = ["\nRUBRIC ADJUSTMENTS (from prior human feedback):"]
        for entry in entries:
            criterion_note = f" [{entry.criterion_id}]" if entry.criterion_id else ""
            lines.append(f"  - {entry.content}{criterion_note}")

        return "\n".join(lines)

    def _relevance_score(
        self,
        entry: FeedbackEntry,
        task: str,
        domain: str,
        criteria_ids: list[str],
        feedback_types: list[str] = None,
    ) -> float:
        """Score how relevant a feedback entry is to the current context."""
        score = 0.0

        # Type filter
        if feedback_types and entry.feedback_type not in feedback_types:
            return 0.0

        # Domain match
        if domain and entry.domain == domain:
            score += 3.0
        elif domain and entry.domain:
            # Partial domain relevance (e.g., both are code-related)
            score += 0.5

        # Criterion match
        if entry.criterion_id and entry.criterion_id in criteria_ids:
            score += 5.0

        # Task keyword overlap
        if task and entry.task:
            task_words = set(task.lower().split())
            entry_words = set(entry.task.lower().split())
            overlap = len(task_words & entry_words) / max(len(task_words), 1)
            score += overlap * 2.0

        # Tag relevance
        if criteria_ids:
            tag_overlap = len(set(entry.tags) & set(criteria_ids))
            score += tag_overlap * 1.5

        # General feedback always somewhat relevant
        if entry.feedback_type == "general":
            score += 1.0

        # Recency bonus (feedback from last 30 days gets a boost)
        if entry.created_at:
            try:
                age_days = (datetime.utcnow() - datetime.fromisoformat(entry.created_at)).days
                if age_days < 7:
                    score += 2.0
                elif age_days < 30:
                    score += 1.0
            except (ValueError, TypeError):
                pass

        # Effectiveness-weighted: if feedback was applied before and helped, boost it
        if entry.effectiveness is not None and entry.effectiveness > 0:
            score += entry.effectiveness * 2.0

        return score
