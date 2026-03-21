"""
Metrics Dashboard Module

Track rubric scores over time. Identify recurring failure patterns.
Provides insights for improving code quality and rubric effectiveness.

Features:
- Time-series tracking of scores
- Failure pattern analysis
- Team/project breakdowns
- Trend detection
- Export for visualization
"""

import json
import sqlite3
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from typing import Optional
from pathlib import Path
from collections import defaultdict
import statistics

# ============================================================================
# Data Models
# ============================================================================

@dataclass
class MetricPoint:
    """A single metric measurement."""
    timestamp: str
    project: str
    file_path: str
    score: float
    criteria_passed: int
    criteria_total: int
    iteration_count: int
    author: Optional[str] = None
    commit_sha: Optional[str] = None
    pr_number: Optional[int] = None

@dataclass
class TrendAnalysis:
    """Analysis of score trends."""
    direction: str  # "improving", "declining", "stable"
    change_rate: float  # Percentage change per week
    current_avg: float
    previous_avg: float
    confidence: float  # 0-1 based on data points

@dataclass
class FailurePattern:
    """A recurring failure pattern."""
    criterion_id: str
    description: str
    failure_count: int
    failure_rate: float
    common_contexts: list[str]  # File patterns, etc.
    suggested_action: str

@dataclass
class DashboardData:
    """Data for dashboard display."""
    overall_score: float
    trend: TrendAnalysis
    top_failures: list[FailurePattern]
    scores_by_project: dict[str, float]
    scores_over_time: list[dict]
    recent_runs: list[dict]


# ============================================================================
# Metrics Storage
# ============================================================================

class MetricsStore:
    """SQLite-based metrics storage."""
    
    def __init__(self, db_path: str = "~/.rubric_loop/metrics.db"):
        self.db_path = Path(db_path).expanduser()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
    
    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    project TEXT,
                    file_path TEXT NOT NULL,
                    score REAL NOT NULL,
                    criteria_passed INTEGER NOT NULL,
                    criteria_total INTEGER NOT NULL,
                    iteration_count INTEGER NOT NULL,
                    author TEXT,
                    commit_sha TEXT,
                    pr_number INTEGER
                );
                
                CREATE INDEX IF NOT EXISTS idx_metrics_timestamp ON metrics(timestamp);
                CREATE INDEX IF NOT EXISTS idx_metrics_project ON metrics(project);
                CREATE INDEX IF NOT EXISTS idx_metrics_file_path ON metrics(file_path);
                
                CREATE TABLE IF NOT EXISTS criterion_failures (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    criterion_id TEXT NOT NULL,
                    description TEXT,
                    file_path TEXT,
                    project TEXT,
                    fix_hint TEXT
                );
                
                CREATE INDEX IF NOT EXISTS idx_failures_criterion ON criterion_failures(criterion_id);
                CREATE INDEX IF NOT EXISTS idx_failures_timestamp ON criterion_failures(timestamp);
            """)
    
    def record_metric(self, metric: MetricPoint):
        """Record a metric point."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO metrics 
                (timestamp, project, file_path, score, criteria_passed, 
                 criteria_total, iteration_count, author, commit_sha, pr_number)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                metric.timestamp,
                metric.project,
                metric.file_path,
                metric.score,
                metric.criteria_passed,
                metric.criteria_total,
                metric.iteration_count,
                metric.author,
                metric.commit_sha,
                metric.pr_number
            ))
    
    def record_failure(
        self,
        criterion_id: str,
        description: str,
        file_path: str,
        project: str = None,
        fix_hint: str = None
    ):
        """Record a criterion failure."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO criterion_failures
                (timestamp, criterion_id, description, file_path, project, fix_hint)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                datetime.now().isoformat(),
                criterion_id,
                description,
                file_path,
                project,
                fix_hint
            ))
    
    def get_scores_over_time(
        self,
        project: str = None,
        days: int = 30,
        granularity: str = "day"
    ) -> list[dict]:
        """Get aggregated scores over time."""
        since = (datetime.now() - timedelta(days=days)).isoformat()
        
        # SQLite date functions for grouping
        if granularity == "hour":
            date_format = "%Y-%m-%d %H:00"
        elif granularity == "day":
            date_format = "%Y-%m-%d"
        elif granularity == "week":
            date_format = "%Y-W%W"
        else:
            date_format = "%Y-%m-%d"
        
        with sqlite3.connect(self.db_path) as conn:
            query = f"""
                SELECT 
                    strftime('{date_format}', timestamp) as period,
                    AVG(score) as avg_score,
                    COUNT(*) as count,
                    SUM(criteria_passed) as total_passed,
                    SUM(criteria_total) as total_criteria
                FROM metrics
                WHERE timestamp >= ?
            """
            params = [since]
            
            if project:
                query += " AND project = ?"
                params.append(project)
            
            query += f" GROUP BY strftime('{date_format}', timestamp) ORDER BY period"
            
            rows = conn.execute(query, params).fetchall()
            
            return [
                {
                    "period": row[0],
                    "avg_score": row[1],
                    "count": row[2],
                    "pass_rate": row[3] / row[4] if row[4] > 0 else 0
                }
                for row in rows
            ]
    
    def get_failure_patterns(
        self,
        project: str = None,
        days: int = 30,
        min_failures: int = 3
    ) -> list[FailurePattern]:
        """Get recurring failure patterns."""
        since = (datetime.now() - timedelta(days=days)).isoformat()
        
        with sqlite3.connect(self.db_path) as conn:
            query = """
                SELECT 
                    criterion_id,
                    description,
                    COUNT(*) as failure_count,
                    GROUP_CONCAT(DISTINCT file_path) as file_paths,
                    GROUP_CONCAT(DISTINCT fix_hint) as fix_hints
                FROM criterion_failures
                WHERE timestamp >= ?
            """
            params = [since]
            
            if project:
                query += " AND project = ?"
                params.append(project)
            
            query += f"""
                GROUP BY criterion_id
                HAVING COUNT(*) >= ?
                ORDER BY failure_count DESC
            """
            params.append(min_failures)
            
            rows = conn.execute(query, params).fetchall()
            
            # Get total runs for failure rate calculation
            total_runs = conn.execute(
                "SELECT COUNT(DISTINCT timestamp || file_path) FROM metrics WHERE timestamp >= ?",
                [since]
            ).fetchone()[0] or 1
            
            patterns = []
            for row in rows:
                file_paths = row[3].split(',') if row[3] else []
                fix_hints = [h for h in (row[4] or '').split(',') if h]
                
                # Analyze file paths for common patterns
                contexts = self._analyze_contexts(file_paths)
                
                # Generate suggested action
                action = self._suggest_action(row[0], row[1], contexts, fix_hints)
                
                patterns.append(FailurePattern(
                    criterion_id=row[0],
                    description=row[1] or '',
                    failure_count=row[2],
                    failure_rate=row[2] / total_runs,
                    common_contexts=contexts,
                    suggested_action=action
                ))
            
            return patterns
    
    def _analyze_contexts(self, file_paths: list[str]) -> list[str]:
        """Analyze file paths for common patterns."""
        contexts = []
        
        # Directory patterns
        dirs = defaultdict(int)
        for path in file_paths:
            parts = path.split('/')
            if len(parts) > 1:
                dirs[parts[0]] += 1
        
        for dir_name, count in sorted(dirs.items(), key=lambda x: -x[1])[:3]:
            if count >= 2:
                contexts.append(f"{dir_name}/ ({count} files)")
        
        # Extension patterns
        exts = defaultdict(int)
        for path in file_paths:
            if '.' in path:
                ext = path.rsplit('.', 1)[1]
                exts[ext] += 1
        
        for ext, count in sorted(exts.items(), key=lambda x: -x[1])[:2]:
            if count >= 2:
                contexts.append(f"*.{ext} files ({count})")
        
        return contexts
    
    def _suggest_action(
        self,
        criterion_id: str,
        description: str,
        contexts: list[str],
        fix_hints: list[str]
    ) -> str:
        """Generate suggested action for a failure pattern."""
        
        # Use most common fix hint if available
        if fix_hints:
            hint_counts = defaultdict(int)
            for hint in fix_hints:
                hint_counts[hint] += 1
            most_common = max(hint_counts.items(), key=lambda x: x[1])[0]
            return f"Common fix: {most_common}"
        
        # Generate based on criterion type
        if "validation" in criterion_id.lower():
            return "Add input validation middleware or schema"
        elif "error" in criterion_id.lower():
            return "Add try/catch blocks and error handling"
        elif "auth" in criterion_id.lower():
            return "Review authentication implementation"
        elif "test" in criterion_id.lower():
            return "Add missing test coverage"
        
        return f"Review {criterion_id} requirements in affected files"
    
    def get_project_scores(self, days: int = 30) -> dict[str, float]:
        """Get average scores by project."""
        since = (datetime.now() - timedelta(days=days)).isoformat()
        
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute("""
                SELECT project, AVG(score) as avg_score
                FROM metrics
                WHERE timestamp >= ? AND project IS NOT NULL
                GROUP BY project
            """, [since]).fetchall()
            
            return {row[0]: row[1] for row in rows}
    
    def get_recent_runs(self, limit: int = 20) -> list[dict]:
        """Get recent rubric runs."""
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute("""
                SELECT timestamp, project, file_path, score, 
                       criteria_passed, criteria_total, author
                FROM metrics
                ORDER BY timestamp DESC
                LIMIT ?
            """, [limit]).fetchall()
            
            return [
                {
                    "timestamp": row[0],
                    "project": row[1],
                    "file_path": row[2],
                    "score": row[3],
                    "criteria_passed": row[4],
                    "criteria_total": row[5],
                    "author": row[6]
                }
                for row in rows
            ]


# ============================================================================
# Trend Analysis
# ============================================================================

class TrendAnalyzer:
    """Analyzes score trends."""
    
    def __init__(self, store: MetricsStore):
        self.store = store
    
    def analyze_trend(
        self,
        project: str = None,
        days: int = 30
    ) -> TrendAnalysis:
        """Analyze score trend over time."""
        
        scores = self.store.get_scores_over_time(project, days, "day")
        
        if len(scores) < 2:
            return TrendAnalysis(
                direction="stable",
                change_rate=0,
                current_avg=scores[0]["avg_score"] if scores else 0,
                previous_avg=scores[0]["avg_score"] if scores else 0,
                confidence=0
            )
        
        # Split into recent and previous halves
        midpoint = len(scores) // 2
        recent = scores[midpoint:]
        previous = scores[:midpoint]
        
        recent_avg = statistics.mean(s["avg_score"] for s in recent)
        previous_avg = statistics.mean(s["avg_score"] for s in previous)
        
        # Calculate change rate (per week)
        total_days = (
            datetime.fromisoformat(scores[-1]["period"]) -
            datetime.fromisoformat(scores[0]["period"])
        ).days or 1
        
        change = recent_avg - previous_avg
        change_rate = (change / previous_avg * 100) if previous_avg > 0 else 0
        weekly_rate = change_rate / (total_days / 7)
        
        # Determine direction
        if abs(change) < 0.02:  # Less than 2% change
            direction = "stable"
        elif change > 0:
            direction = "improving"
        else:
            direction = "declining"
        
        # Calculate confidence based on data points and consistency
        confidence = min(1.0, len(scores) / 14)  # Max confidence at 2 weeks of daily data
        
        # Reduce confidence if high variance
        if len(scores) >= 3:
            variance = statistics.variance(s["avg_score"] for s in scores)
            if variance > 0.1:
                confidence *= 0.7
        
        return TrendAnalysis(
            direction=direction,
            change_rate=weekly_rate,
            current_avg=recent_avg,
            previous_avg=previous_avg,
            confidence=confidence
        )


# ============================================================================
# Dashboard Generator
# ============================================================================

class Dashboard:
    """Generates dashboard data and reports."""
    
    def __init__(self, store: MetricsStore = None):
        self.store = store or MetricsStore()
        self.analyzer = TrendAnalyzer(self.store)
    
    def get_dashboard_data(
        self,
        project: str = None,
        days: int = 30
    ) -> DashboardData:
        """Get all data for dashboard display."""
        
        scores_over_time = self.store.get_scores_over_time(project, days)
        
        overall_score = (
            statistics.mean(s["avg_score"] for s in scores_over_time)
            if scores_over_time else 0
        )
        
        return DashboardData(
            overall_score=overall_score,
            trend=self.analyzer.analyze_trend(project, days),
            top_failures=self.store.get_failure_patterns(project, days),
            scores_by_project=self.store.get_project_scores(days),
            scores_over_time=scores_over_time,
            recent_runs=self.store.get_recent_runs()
        )
    
    def generate_html_dashboard(
        self,
        project: str = None,
        days: int = 30
    ) -> str:
        """Generate an HTML dashboard."""
        
        data = self.get_dashboard_data(project, days)
        
        # Generate chart data
        chart_labels = json.dumps([s["period"] for s in data.scores_over_time])
        chart_values = json.dumps([s["avg_score"] * 100 for s in data.scores_over_time])
        
        # Trend arrow and color
        if data.trend.direction == "improving":
            trend_arrow = "↑"
            trend_color = "#22c55e"
        elif data.trend.direction == "declining":
            trend_arrow = "↓"
            trend_color = "#ef4444"
        else:
            trend_arrow = "→"
            trend_color = "#6b7280"
        
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Rubric Loop Dashboard</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f3f4f6; padding: 20px; }}
        .dashboard {{ max-width: 1200px; margin: 0 auto; }}
        .header {{ background: white; padding: 20px; border-radius: 8px; margin-bottom: 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
        .header h1 {{ font-size: 24px; color: #111827; }}
        .header p {{ color: #6b7280; margin-top: 4px; }}
        .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 20px; }}
        .card {{ background: white; padding: 20px; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
        .card h2 {{ font-size: 14px; text-transform: uppercase; color: #6b7280; letter-spacing: 0.05em; margin-bottom: 12px; }}
        .metric {{ font-size: 48px; font-weight: bold; color: #111827; }}
        .metric-label {{ font-size: 14px; color: #6b7280; }}
        .trend {{ display: inline-flex; align-items: center; gap: 4px; font-size: 14px; margin-top: 8px; }}
        .failure-list {{ list-style: none; }}
        .failure-item {{ padding: 12px 0; border-bottom: 1px solid #e5e7eb; }}
        .failure-item:last-child {{ border-bottom: none; }}
        .failure-id {{ font-weight: 600; color: #111827; }}
        .failure-count {{ background: #fee2e2; color: #dc2626; padding: 2px 8px; border-radius: 12px; font-size: 12px; }}
        .failure-context {{ font-size: 12px; color: #6b7280; margin-top: 4px; }}
        .recent-table {{ width: 100%; border-collapse: collapse; }}
        .recent-table th, .recent-table td {{ padding: 8px; text-align: left; border-bottom: 1px solid #e5e7eb; }}
        .recent-table th {{ font-size: 12px; text-transform: uppercase; color: #6b7280; }}
        .score-badge {{ padding: 2px 8px; border-radius: 12px; font-size: 12px; }}
        .score-pass {{ background: #dcfce7; color: #16a34a; }}
        .score-warn {{ background: #fef9c3; color: #ca8a04; }}
        .score-fail {{ background: #fee2e2; color: #dc2626; }}
    </style>
</head>
<body>
    <div class="dashboard">
        <div class="header">
            <h1>Rubric Loop Dashboard</h1>
            <p>Last {days} days{f' • {project}' if project else ''}</p>
        </div>
        
        <div class="grid">
            <div class="card">
                <h2>Overall Score</h2>
                <div class="metric">{data.overall_score:.0%}</div>
                <div class="trend" style="color: {trend_color}">
                    {trend_arrow} {data.trend.direction.title()}
                    ({data.trend.change_rate:+.1f}%/week)
                </div>
            </div>
            
            <div class="card">
                <h2>Score Trend</h2>
                <canvas id="scoreChart" height="150"></canvas>
            </div>
            
            <div class="card" style="grid-column: span 2;">
                <h2>Top Failure Patterns</h2>
                <ul class="failure-list">
                    {''.join(f'''
                    <li class="failure-item">
                        <span class="failure-id">{fp.criterion_id}</span>
                        <span class="failure-count">{fp.failure_count} failures</span>
                        <div class="failure-context">{fp.description[:80]}...</div>
                        <div class="failure-context">📍 {', '.join(fp.common_contexts[:2]) if fp.common_contexts else 'Various files'}</div>
                        <div class="failure-context">💡 {fp.suggested_action}</div>
                    </li>
                    ''' for fp in data.top_failures[:5]) or '<li class="failure-item">No failure patterns detected</li>'}
                </ul>
            </div>
            
            <div class="card" style="grid-column: span 2;">
                <h2>Recent Runs</h2>
                <table class="recent-table">
                    <thead>
                        <tr>
                            <th>Time</th>
                            <th>File</th>
                            <th>Score</th>
                            <th>Criteria</th>
                        </tr>
                    </thead>
                    <tbody>
                        {''.join(f'''
                        <tr>
                            <td>{run['timestamp'][:16]}</td>
                            <td>{run['file_path'][:40]}{'...' if len(run['file_path']) > 40 else ''}</td>
                            <td>
                                <span class="score-badge {'score-pass' if run['score'] >= 0.85 else 'score-warn' if run['score'] >= 0.7 else 'score-fail'}">
                                    {run['score']:.0%}
                                </span>
                            </td>
                            <td>{run['criteria_passed']}/{run['criteria_total']}</td>
                        </tr>
                        ''' for run in data.recent_runs[:10])}
                    </tbody>
                </table>
            </div>
        </div>
    </div>
    
    <script>
        new Chart(document.getElementById('scoreChart'), {{
            type: 'line',
            data: {{
                labels: {chart_labels},
                datasets: [{{
                    label: 'Score',
                    data: {chart_values},
                    borderColor: '#6366f1',
                    backgroundColor: 'rgba(99, 102, 241, 0.1)',
                    fill: true,
                    tension: 0.3
                }}]
            }},
            options: {{
                responsive: true,
                plugins: {{ legend: {{ display: false }} }},
                scales: {{
                    y: {{
                        min: 0,
                        max: 100,
                        ticks: {{ callback: v => v + '%' }}
                    }}
                }}
            }}
        }});
    </script>
</body>
</html>
"""
        return html
    
    def generate_markdown_report(
        self,
        project: str = None,
        days: int = 30
    ) -> str:
        """Generate a Markdown report."""
        
        data = self.get_dashboard_data(project, days)
        
        lines = [
            "# Rubric Loop Metrics Report",
            f"*Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}*",
            f"*Period: Last {days} days{f' • {project}' if project else ''}*",
            "",
            "## Summary",
            "",
            f"- **Overall Score:** {data.overall_score:.0%}",
            f"- **Trend:** {data.trend.direction.title()} ({data.trend.change_rate:+.1f}%/week)",
            f"- **Confidence:** {data.trend.confidence:.0%}",
            "",
        ]
        
        if data.scores_by_project:
            lines.extend([
                "## Scores by Project",
                "",
                "| Project | Average Score |",
                "|---------|---------------|"
            ])
            for project_name, score in sorted(data.scores_by_project.items(), key=lambda x: -x[1]):
                lines.append(f"| {project_name} | {score:.0%} |")
            lines.append("")
        
        if data.top_failures:
            lines.extend([
                "## Top Failure Patterns",
                "",
                "| Criterion | Failures | Rate | Suggested Action |",
                "|-----------|----------|------|------------------|"
            ])
            for fp in data.top_failures[:10]:
                lines.append(
                    f"| {fp.criterion_id} | {fp.failure_count} | {fp.failure_rate:.0%} | {fp.suggested_action[:50]} |"
                )
            lines.append("")
        
        if data.scores_over_time:
            lines.extend([
                "## Score Trend",
                "",
                "| Date | Average Score | Runs |",
                "|------|---------------|------|"
            ])
            for point in data.scores_over_time[-14:]:  # Last 2 weeks
                lines.append(
                    f"| {point['period']} | {point['avg_score']:.0%} | {point['count']} |"
                )
        
        return "\n".join(lines)


# ============================================================================
# CLI
# ============================================================================

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Rubric Loop Metrics Dashboard")
    subparsers = parser.add_subparsers(dest="command")
    
    # Dashboard command
    dash_parser = subparsers.add_parser("dashboard", help="Generate HTML dashboard")
    dash_parser.add_argument("--output", "-o", default="dashboard.html")
    dash_parser.add_argument("--project", "-p", help="Filter by project")
    dash_parser.add_argument("--days", "-d", type=int, default=30)
    
    # Report command
    report_parser = subparsers.add_parser("report", help="Generate Markdown report")
    report_parser.add_argument("--output", "-o", default="metrics-report.md")
    report_parser.add_argument("--project", "-p", help="Filter by project")
    report_parser.add_argument("--days", "-d", type=int, default=30)
    
    # Failures command
    fail_parser = subparsers.add_parser("failures", help="Show failure patterns")
    fail_parser.add_argument("--project", "-p", help="Filter by project")
    fail_parser.add_argument("--days", "-d", type=int, default=30)
    fail_parser.add_argument("--min", type=int, default=3, help="Minimum failures")
    
    # Export command
    export_parser = subparsers.add_parser("export", help="Export metrics as JSON")
    export_parser.add_argument("--output", "-o", default="metrics.json")
    export_parser.add_argument("--days", "-d", type=int, default=30)
    
    args = parser.parse_args()
    
    store = MetricsStore()
    dashboard = Dashboard(store)
    
    if args.command == "dashboard":
        html = dashboard.generate_html_dashboard(args.project, args.days)
        Path(args.output).write_text(html)
        print(f"Dashboard saved to {args.output}")
    
    elif args.command == "report":
        report = dashboard.generate_markdown_report(args.project, args.days)
        Path(args.output).write_text(report)
        print(f"Report saved to {args.output}")
    
    elif args.command == "failures":
        patterns = store.get_failure_patterns(args.project, args.days, args.min)
        print(f"{'Criterion':<30} {'Failures':>8} {'Rate':>8} Action")
        print("-" * 80)
        for fp in patterns:
            print(f"{fp.criterion_id:<30} {fp.failure_count:>8} {fp.failure_rate:>7.0%} {fp.suggested_action[:30]}")
    
    elif args.command == "export":
        data = dashboard.get_dashboard_data(days=args.days)
        export = {
            "generated_at": datetime.now().isoformat(),
            "overall_score": data.overall_score,
            "trend": asdict(data.trend),
            "top_failures": [asdict(fp) for fp in data.top_failures],
            "scores_by_project": data.scores_by_project,
            "scores_over_time": data.scores_over_time,
            "recent_runs": data.recent_runs
        }
        Path(args.output).write_text(json.dumps(export, indent=2))
        print(f"Metrics exported to {args.output}")
    
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
