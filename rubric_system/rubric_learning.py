"""
Rubric Learning Module

Saves scored rubrics and learns which criteria predict actual bugs/issues.
Enables continuous improvement of rubric templates based on real outcomes.

Features:
1. Persistence: Save all scored rubrics with outcomes
2. Analysis: Identify criteria that correlate with bugs
3. Refinement: Suggest rubric improvements based on history
4. Transfer: Find similar past tasks and their effective rubrics
"""

import json
import sqlite3
from datetime import datetime
from dataclasses import asdict
from typing import Optional
from pathlib import Path
import hashlib
from collections import defaultdict

from rubric_system.models import ScoredRubricRecord, CriterionStats


# ============================================================================
# Storage Layer
# ============================================================================

class RubricStore:
    """SQLite-based storage for rubric history."""
    
    def __init__(self, db_path: str = str(Path.home() / ".auto-verifier-data" / "rubrics.db")):
        self.db_path = Path(db_path).expanduser()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
    
    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS scored_rubrics (
                    id TEXT PRIMARY KEY,
                    task TEXT NOT NULL,
                    task_hash TEXT NOT NULL,
                    template_id TEXT,
                    criteria JSON NOT NULL,
                    scores JSON NOT NULL,
                    overall_score REAL NOT NULL,
                    outcome TEXT,
                    outcome_details TEXT,
                    days_to_bug INTEGER,
                    created_at TEXT NOT NULL,
                    project TEXT,
                    author TEXT,
                    iteration_count INTEGER NOT NULL
                );
                
                CREATE INDEX IF NOT EXISTS idx_task_hash ON scored_rubrics(task_hash);
                CREATE INDEX IF NOT EXISTS idx_template_id ON scored_rubrics(template_id);
                CREATE INDEX IF NOT EXISTS idx_outcome ON scored_rubrics(outcome);
                CREATE INDEX IF NOT EXISTS idx_created_at ON scored_rubrics(created_at);
                
                CREATE TABLE IF NOT EXISTS criterion_stats (
                    criterion_id TEXT PRIMARY KEY,
                    description TEXT,
                    times_used INTEGER DEFAULT 0,
                    times_passed INTEGER DEFAULT 0,
                    times_failed INTEGER DEFAULT 0,
                    pass_then_bug INTEGER DEFAULT 0,
                    fail_then_bug INTEGER DEFAULT 0,
                    pass_then_success INTEGER DEFAULT 0,
                    fail_then_success INTEGER DEFAULT 0,
                    updated_at TEXT
                );
                
                CREATE TABLE IF NOT EXISTS task_embeddings (
                    task_hash TEXT PRIMARY KEY,
                    task TEXT,
                    keywords TEXT,  -- JSON array
                    template_ids TEXT  -- JSON array of templates used
                );
            """)
    
    def save_rubric(self, record: ScoredRubricRecord):
        """Save a scored rubric."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO scored_rubrics
                (id, task, task_hash, template_id, criteria, scores, overall_score,
                 outcome, outcome_details, days_to_bug, created_at, project, author,
                 iteration_count)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                record.id,
                record.task,
                record.task_hash,
                record.template_id,
                json.dumps(record.criteria),
                json.dumps(record.scores),
                record.overall_score,
                record.outcome,
                record.outcome_details,
                record.days_to_bug,
                record.created_at,
                record.project,
                record.author,
                record.iteration_count
            ))
            
            # Update criterion stats
            for score in record.scores:
                self._update_criterion_stats(conn, score, record.outcome)
    
    def _update_criterion_stats(self, conn, score: dict, outcome: Optional[str]):
        """Update statistics for a criterion based on new score."""
        criterion_id = score.get('criterion_id') or score.get('id')
        passed = score.get('passed', False)
        
        # Get or create stats record
        row = conn.execute(
            "SELECT * FROM criterion_stats WHERE criterion_id = ?",
            (criterion_id,)
        ).fetchone()
        
        if row is None:
            conn.execute("""
                INSERT INTO criterion_stats (criterion_id, description, updated_at)
                VALUES (?, ?, ?)
            """, (criterion_id, score.get('description', ''), datetime.now().isoformat()))
        
        # Update counts
        updates = ["times_used = times_used + 1"]
        if passed:
            updates.append("times_passed = times_passed + 1")
        else:
            updates.append("times_failed = times_failed + 1")
        
        # Update outcome correlation if known
        if outcome == 'bug_found':
            if passed:
                updates.append("pass_then_bug = pass_then_bug + 1")
            else:
                updates.append("fail_then_bug = fail_then_bug + 1")
        elif outcome == 'success':
            if passed:
                updates.append("pass_then_success = pass_then_success + 1")
            else:
                updates.append("fail_then_success = fail_then_success + 1")
        
        updates.append("updated_at = ?")
        
        conn.execute(f"""
            UPDATE criterion_stats
            SET {', '.join(updates)}
            WHERE criterion_id = ?
        """, (datetime.now().isoformat(), criterion_id))
    
    def update_outcome(self, rubric_id: str, outcome: str, 
                       details: str = None, days_to_bug: int = None):
        """Update the outcome for a previously saved rubric."""
        with sqlite3.connect(self.db_path) as conn:
            # Get the original record
            row = conn.execute(
                "SELECT scores, outcome FROM scored_rubrics WHERE id = ?",
                (rubric_id,)
            ).fetchone()
            
            if not row:
                raise ValueError(f"Rubric {rubric_id} not found")
            
            scores = json.loads(row[0])
            old_outcome = row[1]
            
            # Update the record
            conn.execute("""
                UPDATE scored_rubrics
                SET outcome = ?, outcome_details = ?, days_to_bug = ?
                WHERE id = ?
            """, (outcome, details, days_to_bug, rubric_id))
            
            # Update criterion stats if outcome changed
            if old_outcome != outcome:
                for score in scores:
                    self._update_outcome_stats(conn, score, old_outcome, outcome)
    
    def _update_outcome_stats(self, conn, score: dict, 
                              old_outcome: Optional[str], new_outcome: str):
        """Adjust criterion stats when outcome changes."""
        criterion_id = score.get('criterion_id') or score.get('id')
        passed = score.get('passed', False)
        
        # Decrement old outcome stat
        if old_outcome == 'bug_found':
            col = "pass_then_bug" if passed else "fail_then_bug"
            conn.execute(f"""
                UPDATE criterion_stats
                SET {col} = MAX(0, {col} - 1)
                WHERE criterion_id = ?
            """, (criterion_id,))
        elif old_outcome == 'success':
            col = "pass_then_success" if passed else "fail_then_success"
            conn.execute(f"""
                UPDATE criterion_stats
                SET {col} = MAX(0, {col} - 1)
                WHERE criterion_id = ?
            """, (criterion_id,))
        
        # Increment new outcome stat
        if new_outcome == 'bug_found':
            col = "pass_then_bug" if passed else "fail_then_bug"
        elif new_outcome == 'success':
            col = "pass_then_success" if passed else "fail_then_success"
        else:
            return
        
        conn.execute(f"""
            UPDATE criterion_stats
            SET {col} = {col} + 1, updated_at = ?
            WHERE criterion_id = ?
        """, (datetime.now().isoformat(), criterion_id))
    
    def list_all(self) -> list[ScoredRubricRecord]:
        """Return all scored rubric records ordered by creation date descending."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM scored_rubrics ORDER BY created_at DESC"
            ).fetchall()
            return [self._row_to_record(row) for row in rows]

    def count_rubrics(self) -> int:
        """Return the total number of scored rubrics in the store."""
        with sqlite3.connect(self.db_path) as conn:
            return conn.execute("SELECT COUNT(*) FROM scored_rubrics").fetchone()[0]

    def get_criterion_stats(self, min_uses: int = 5) -> list[CriterionStats]:
        """Get statistics for all criteria with minimum usage."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("""
                SELECT * FROM criterion_stats
                WHERE times_used >= ?
                ORDER BY times_used DESC
            """, (min_uses,)).fetchall()
            
            return [CriterionStats(
                criterion_id=row['criterion_id'],
                description=row['description'] or '',
                times_used=row['times_used'],
                times_passed=row['times_passed'],
                times_failed=row['times_failed'],
                pass_then_bug=row['pass_then_bug'],
                fail_then_bug=row['fail_then_bug'],
                pass_then_success=row['pass_then_success'],
                fail_then_success=row['fail_then_success']
            ) for row in rows]
    
    def find_similar_tasks(self, task: str, limit: int = 5) -> list[ScoredRubricRecord]:
        """Find similar past tasks based on keyword matching."""
        keywords = self._extract_keywords(task)
        task_hash = self._hash_task(task)
        
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            
            # First try exact hash match
            rows = conn.execute("""
                SELECT * FROM scored_rubrics
                WHERE task_hash = ?
                ORDER BY created_at DESC
                LIMIT ?
            """, (task_hash, limit)).fetchall()
            
            if rows:
                return [self._row_to_record(row) for row in rows]
            
            # Fall back to keyword matching
            # This is a simple approach; could use FTS5 or vector embeddings
            like_clauses = " OR ".join(["task LIKE ?" for _ in keywords])
            params = [f"%{kw}%" for kw in keywords] + [limit]
            
            rows = conn.execute(f"""
                SELECT * FROM scored_rubrics
                WHERE {like_clauses}
                ORDER BY overall_score DESC
                LIMIT ?
            """, params).fetchall()
            
            return [self._row_to_record(row) for row in rows]
    
    def _row_to_record(self, row) -> ScoredRubricRecord:
        return ScoredRubricRecord(
            id=row['id'],
            task=row['task'],
            task_hash=row['task_hash'],
            template_id=row['template_id'],
            criteria=json.loads(row['criteria']),
            scores=json.loads(row['scores']),
            overall_score=row['overall_score'],
            outcome=row['outcome'],
            outcome_details=row['outcome_details'],
            days_to_bug=row['days_to_bug'],
            created_at=row['created_at'],
            project=row['project'],
            author=row['author'],
            iteration_count=row['iteration_count']
        )
    
    def _extract_keywords(self, task: str) -> list[str]:
        """Extract keywords from task description."""
        # Simple keyword extraction - could use NLP
        stopwords = {'a', 'an', 'the', 'to', 'for', 'of', 'with', 'and', 'or', 'in'}
        words = task.lower().split()
        return [w for w in words if w not in stopwords and len(w) > 2]
    
    def _hash_task(self, task: str) -> str:
        """Create a hash for task similarity matching."""
        normalized = ' '.join(sorted(self._extract_keywords(task)))
        return hashlib.md5(normalized.encode()).hexdigest()[:12]


# ============================================================================
# Learning & Analysis
# ============================================================================

class RubricLearner:
    """Analyzes rubric history to improve future rubrics."""
    
    def __init__(self, store: RubricStore):
        self.store = store
    
    def get_insights(self) -> dict:
        """Generate insights from rubric history."""
        stats = self.store.get_criterion_stats(min_uses=5)
        
        insights = {
            "high_value_criteria": [],
            "low_value_criteria": [],
            "suggested_additions": [],
            "suggested_removals": [],
            "summary": {}
        }
        
        for s in stats:
            if s.predictive_value > 0.7:
                insights["high_value_criteria"].append({
                    "id": s.criterion_id,
                    "description": s.description,
                    "predictive_value": round(s.predictive_value, 2),
                    "bug_prevention_rate": round(s.bug_prevention_rate, 2),
                    "recommendation": "Keep this criterion - highly predictive"
                })
            
            if s.false_positive_rate > 0.5 and s.times_used > 10:
                insights["low_value_criteria"].append({
                    "id": s.criterion_id,
                    "description": s.description,
                    "false_positive_rate": round(s.false_positive_rate, 2),
                    "recommendation": "Consider removing or refining - often fails unnecessarily"
                })
            
            if s.pass_rate > 0.95 and s.times_used > 20:
                insights["suggested_removals"].append({
                    "id": s.criterion_id,
                    "description": s.description,
                    "pass_rate": round(s.pass_rate, 2),
                    "recommendation": "Always passes - may be too easy or redundant"
                })
        
        # Summary stats
        total_rubrics = len(stats)
        high_value_count = len(insights["high_value_criteria"])

        insights["summary"] = {
            "total_criteria_tracked": total_rubrics,
            "high_value_criteria": high_value_count,
            "low_value_criteria": len(insights["low_value_criteria"]),
            "average_predictive_value": (
                sum(s.predictive_value for s in stats) / len(stats)
                if stats else 0
            )
        }

        # Add total evaluations and all criteria stats for auto-improve trigger
        insights["total_evaluations"] = self.store.count_rubrics()
        all_stats = self.store.get_criterion_stats(min_uses=1)
        insights["all_criteria_stats"] = [
            {"criterion_id": s.criterion_id, "times_used": s.times_used,
             "pass_rate": round(s.pass_rate, 2)}
            for s in all_stats
        ]

        return insights
    
    def suggest_rubric_for_task(self, task: str) -> dict:
        """Suggest a rubric based on similar past tasks."""
        similar = self.store.find_similar_tasks(task, limit=5)
        
        if not similar:
            return {
                "source": "template",
                "confidence": "low",
                "message": "No similar tasks found. Using default template.",
                "criteria": []
            }
        
        # Aggregate criteria from similar tasks
        criteria_usage = defaultdict(lambda: {
            "count": 0,
            "pass_rate": [],
            "outcomes": [],
            "definition": None
        })
        
        for record in similar:
            for score in record.scores:
                cid = score.get('criterion_id') or score.get('id')
                criteria_usage[cid]["count"] += 1
                criteria_usage[cid]["pass_rate"].append(1 if score.get('passed') else 0)
                if record.outcome:
                    criteria_usage[cid]["outcomes"].append(record.outcome)
                if not criteria_usage[cid]["definition"]:
                    # Find the criterion definition
                    for c in record.criteria:
                        if c.get('id') == cid:
                            criteria_usage[cid]["definition"] = c
                            break
        
        # Select criteria that were used in multiple similar tasks
        suggested = []
        for cid, data in criteria_usage.items():
            if data["count"] >= 2 and data["definition"]:
                avg_pass_rate = sum(data["pass_rate"]) / len(data["pass_rate"])
                bug_rate = data["outcomes"].count("bug_found") / len(data["outcomes"]) if data["outcomes"] else 0
                
                suggested.append({
                    **data["definition"],
                    "confidence": data["count"] / len(similar),
                    "historical_pass_rate": round(avg_pass_rate, 2),
                    "historical_bug_rate": round(bug_rate, 2)
                })
        
        # Sort by weight and confidence
        suggested.sort(key=lambda x: (-x.get('weight', 1), -x.get('confidence', 0)))
        
        return {
            "source": "learning",
            "confidence": "high" if len(similar) >= 3 else "medium",
            "similar_tasks": len(similar),
            "message": f"Based on {len(similar)} similar past tasks",
            "criteria": suggested
        }
    
    def generate_report(self) -> str:
        """Generate a human-readable report of rubric effectiveness."""
        insights = self.get_insights()
        stats = self.store.get_criterion_stats(min_uses=5)
        
        lines = [
            "# Rubric Learning Report",
            f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            "",
            "## Summary",
            f"- Total criteria tracked: {insights['summary']['total_criteria_tracked']}",
            f"- High-value criteria: {insights['summary']['high_value_criteria']}",
            f"- Low-value criteria: {insights['summary']['low_value_criteria']}",
            f"- Average predictive value: {insights['summary']['average_predictive_value']:.1%}",
            "",
        ]
        
        if insights["high_value_criteria"]:
            lines.extend([
                "## High-Value Criteria (Keep These)",
                "",
                "| Criterion | Predictive Value | Bug Prevention |",
                "|-----------|-----------------|----------------|"
            ])
            for c in insights["high_value_criteria"]:
                lines.append(
                    f"| {c['id']} | {c['predictive_value']:.0%} | {c['bug_prevention_rate']:.0%} |"
                )
            lines.append("")
        
        if insights["low_value_criteria"]:
            lines.extend([
                "## Low-Value Criteria (Consider Refining)",
                "",
                "| Criterion | False Positive Rate | Recommendation |",
                "|-----------|--------------------|--------------------|"
            ])
            for c in insights["low_value_criteria"]:
                lines.append(
                    f"| {c['id']} | {c['false_positive_rate']:.0%} | {c['recommendation']} |"
                )
            lines.append("")
        
        if insights["suggested_removals"]:
            lines.extend([
                "## Criteria That May Be Redundant",
                "",
                "| Criterion | Pass Rate | Note |",
                "|-----------|-----------|------|"
            ])
            for c in insights["suggested_removals"]:
                lines.append(
                    f"| {c['id']} | {c['pass_rate']:.0%} | {c['recommendation']} |"
                )
            lines.append("")
        
        lines.extend([
            "## All Criteria Statistics",
            "",
            "| Criterion | Uses | Pass Rate | Predictive Value |",
            "|-----------|------|-----------|------------------|"
        ])
        
        for s in stats[:20]:  # Top 20
            lines.append(
                f"| {s.criterion_id} | {s.times_used} | {s.pass_rate:.0%} | {s.predictive_value:.0%} |"
            )
        
        return "\n".join(lines)


# ============================================================================
# CLI Interface
# ============================================================================

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Rubric Learning System")
    subparsers = parser.add_subparsers(dest="command")
    
    # Report command
    report_parser = subparsers.add_parser("report", help="Generate learning report")
    report_parser.add_argument("--output", "-o", help="Output file")
    
    # Stats command
    stats_parser = subparsers.add_parser("stats", help="Show criterion statistics")
    stats_parser.add_argument("--min-uses", type=int, default=5)
    
    # Suggest command
    suggest_parser = subparsers.add_parser("suggest", help="Suggest rubric for task")
    suggest_parser.add_argument("task", help="Task description")
    
    # Update outcome command
    outcome_parser = subparsers.add_parser("outcome", help="Update rubric outcome")
    outcome_parser.add_argument("rubric_id", help="Rubric ID")
    outcome_parser.add_argument("outcome", choices=["success", "bug_found", "reverted"])
    outcome_parser.add_argument("--details", help="Outcome details")
    outcome_parser.add_argument("--days", type=int, help="Days until bug found")
    
    args = parser.parse_args()
    
    store = RubricStore()
    learner = RubricLearner(store)
    
    if args.command == "report":
        report = learner.generate_report()
        if args.output:
            Path(args.output).write_text(report)
            print(f"Report saved to {args.output}")
        else:
            print(report)
    
    elif args.command == "stats":
        stats = store.get_criterion_stats(min_uses=args.min_uses)
        print(f"{'Criterion':<30} {'Uses':>6} {'Pass%':>7} {'Predictive':>10}")
        print("-" * 60)
        for s in stats:
            print(f"{s.criterion_id:<30} {s.times_used:>6} {s.pass_rate:>6.0%} {s.predictive_value:>10.0%}")
    
    elif args.command == "suggest":
        suggestion = learner.suggest_rubric_for_task(args.task)
        print(f"Source: {suggestion['source']} (confidence: {suggestion['confidence']})")
        print(f"Message: {suggestion['message']}")
        print("\nSuggested criteria:")
        for c in suggestion['criteria']:
            print(f"  - [{c.get('weight', 1)}/3] {c.get('id')}: {c.get('description', '')[:60]}")
    
    elif args.command == "outcome":
        store.update_outcome(
            args.rubric_id,
            args.outcome,
            args.details,
            args.days
        )
        print(f"Updated outcome for {args.rubric_id} to '{args.outcome}'")
    
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
