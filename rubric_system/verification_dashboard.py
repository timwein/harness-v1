#!/usr/bin/env python3
"""
Verification Dashboard

Interactive HTML dashboard that reports on all verification steps completed
during a rubric loop run. Shows what was checked, how, and with what result —
making the discriminator's work fully auditable.

Features:
1. Real-time verification step tracking
2. Interactive HTML dashboard with filtering/sorting
3. Drill-down from overall score to sub-attribute evidence
4. Visual pass/fail/warn status for every check
5. Improvement trajectory across iterations
6. Exportable as standalone HTML file

Usage:
    from rubric_system.verification_dashboard import VerificationTracker, DashboardGenerator

    tracker = VerificationTracker()
    tracker.start_iteration(1)
    tracker.add_step("src_freshness", "weighted_components",
                      sub_scores={"headline_freshness": 0.9, "supporting_freshness": 0.7},
                      evidence="8/10 headline sources within 2 years",
                      status="pass", points_earned=8.5, max_points=10)
    ...
    html = DashboardGenerator(tracker).generate()
"""

import json
from datetime import datetime
from dataclasses import dataclass, field, asdict
from typing import Optional
from pathlib import Path

from rubric_system.models import CriterionScore, Iteration, LoopResult


@dataclass
class VerificationStep:
    """A single verification action performed."""
    criterion_id: str
    scoring_method: str
    status: str  # "pass", "warn", "fail"
    points_earned: float
    max_points: int
    percentage: float
    sub_scores: dict = field(default_factory=dict)  # sub_id -> raw_value
    penalties: list[str] = field(default_factory=list)  # violations found
    evidence: str = ""
    methodology: str = ""
    improvement_hints: list[str] = field(default_factory=list)
    duration_ms: int = 0  # How long this check took
    verification_method: str = "llm_scoring"  # llm_scoring, linter, url_check, etc.


@dataclass
class IterationRecord:
    """All verification steps for one iteration."""
    number: int
    total_score: float
    max_score: int
    percentage: float
    steps: list[VerificationStep] = field(default_factory=list)
    started_at: str = ""
    completed_at: str = ""
    focus_areas: list[str] = field(default_factory=list)


class VerificationTracker:
    """
    Tracks all verification steps across iterations.
    Wire this into RubricLoop to capture everything the scorer does.
    """

    def __init__(self):
        self.task: str = ""
        self.domain: str = ""
        self.iterations: list[IterationRecord] = []
        self._current_iteration: Optional[IterationRecord] = None
        self.started_at: str = datetime.utcnow().isoformat()
        self.completed_at: str = ""

    def set_task(self, task: str, domain: str):
        self.task = task
        self.domain = domain

    def start_iteration(self, number: int, focus_areas: list[str] = None):
        self._current_iteration = IterationRecord(
            number=number,
            total_score=0,
            max_score=0,
            percentage=0,
            started_at=datetime.utcnow().isoformat(),
            focus_areas=focus_areas or [],
        )

    def add_step(
        self,
        criterion_id: str,
        scoring_method: str,
        points_earned: float,
        max_points: int,
        evidence: str = "",
        methodology: str = "",
        sub_scores: dict = None,
        penalties: list[str] = None,
        improvement_hints: list[str] = None,
        duration_ms: int = 0,
        verification_method: str = "llm_scoring",
    ):
        """Record a single verification step."""
        pct = points_earned / max_points if max_points > 0 else 0
        status = "pass" if pct >= 0.8 else "warn" if pct >= 0.5 else "fail"

        step = VerificationStep(
            criterion_id=criterion_id,
            scoring_method=scoring_method,
            status=status,
            points_earned=round(points_earned, 2),
            max_points=max_points,
            percentage=round(pct, 4),
            sub_scores=sub_scores or {},
            penalties=penalties or [],
            evidence=evidence,
            methodology=methodology,
            improvement_hints=improvement_hints or [],
            duration_ms=duration_ms,
            verification_method=verification_method,
        )

        if self._current_iteration:
            self._current_iteration.steps.append(step)

    def add_steps_from_criterion_scores(self, criterion_scores: list[CriterionScore]):
        """Bulk-add steps from the scoring engine output."""
        for cs in criterion_scores:
            self.add_step(
                criterion_id=cs.criterion_id,
                scoring_method=cs.methodology.split(":")[0] if cs.methodology else "unknown",
                points_earned=cs.points_earned,
                max_points=cs.max_points,
                evidence=cs.evidence,
                methodology=cs.methodology,
                sub_scores={ss.sub_id: ss.raw_value for ss in cs.sub_scores},
                penalties=[p["violation"] for p in cs.penalties_applied],
                improvement_hints=cs.improvement_hints,
            )

    def complete_iteration(self, total_score: float, max_score: int):
        """Finalize the current iteration."""
        if self._current_iteration:
            self._current_iteration.total_score = total_score
            self._current_iteration.max_score = max_score
            self._current_iteration.percentage = total_score / max_score if max_score > 0 else 0
            self._current_iteration.completed_at = datetime.utcnow().isoformat()
            self.iterations.append(self._current_iteration)
            self._current_iteration = None

    def complete(self):
        self.completed_at = datetime.utcnow().isoformat()

    def from_loop_result(self, result: LoopResult):
        """Populate tracker from a completed LoopResult."""
        self.task = result.rubric.task
        self.domain = result.rubric.domain

        for iteration in result.history:
            self.start_iteration(iteration.number, iteration.focus_areas)
            self.add_steps_from_criterion_scores(iteration.criterion_scores)
            self.complete_iteration(iteration.total_score, iteration.max_score)

        self.complete()

    def to_dict(self) -> dict:
        return {
            "task": self.task,
            "domain": self.domain,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "iterations": [asdict(it) for it in self.iterations],
        }


class DashboardGenerator:
    """Generates an interactive HTML dashboard from verification data."""

    def __init__(self, tracker: VerificationTracker):
        self.tracker = tracker

    def generate(self) -> str:
        """Generate standalone HTML dashboard."""
        data = json.dumps(self.tracker.to_dict(), indent=2)
        return self._html_template(data)

    def save(self, path: str):
        """Save dashboard to file."""
        Path(path).write_text(self.generate())

    def _html_template(self, data_json: str) -> str:
        return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Verification Dashboard</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js"></script>
<style>
  :root {{
    --bg: #0f1117;
    --surface: #1a1d27;
    --surface2: #242836;
    --border: #2e3345;
    --text: #e4e6ed;
    --text-secondary: #8b8fa3;
    --pass: #22c55e;
    --warn: #f59e0b;
    --fail: #ef4444;
    --accent: #3b82f6;
    --accent-dim: rgba(59,130,246,0.15);
  }}
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    background: var(--bg);
    color: var(--text);
    line-height: 1.5;
    padding: 24px;
  }}
  .header {{
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    margin-bottom: 32px;
    padding-bottom: 24px;
    border-bottom: 1px solid var(--border);
  }}
  .header h1 {{
    font-size: 24px;
    font-weight: 600;
    margin-bottom: 4px;
  }}
  .header .meta {{
    color: var(--text-secondary);
    font-size: 14px;
  }}
  .summary-cards {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
    gap: 16px;
    margin-bottom: 32px;
  }}
  .card {{
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 20px;
  }}
  .card .label {{
    font-size: 12px;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--text-secondary);
    margin-bottom: 8px;
  }}
  .card .value {{
    font-size: 28px;
    font-weight: 700;
  }}
  .card .value.pass {{ color: var(--pass); }}
  .card .value.warn {{ color: var(--warn); }}
  .card .value.fail {{ color: var(--fail); }}
  .section {{
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 24px;
    margin-bottom: 24px;
  }}
  .section h2 {{
    font-size: 16px;
    font-weight: 600;
    margin-bottom: 16px;
    display: flex;
    align-items: center;
    gap: 8px;
  }}
  .chart-container {{
    position: relative;
    height: 250px;
    margin-bottom: 16px;
  }}
  .iteration-tabs {{
    display: flex;
    gap: 8px;
    margin-bottom: 16px;
    flex-wrap: wrap;
  }}
  .iteration-tabs button {{
    background: var(--surface2);
    color: var(--text-secondary);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 8px 16px;
    cursor: pointer;
    font-size: 13px;
    transition: all 0.15s;
  }}
  .iteration-tabs button:hover {{ background: var(--accent-dim); color: var(--text); }}
  .iteration-tabs button.active {{
    background: var(--accent-dim);
    color: var(--accent);
    border-color: var(--accent);
  }}
  .steps-grid {{
    display: grid;
    gap: 12px;
  }}
  .step {{
    background: var(--surface2);
    border-radius: 8px;
    padding: 16px;
    border-left: 4px solid var(--border);
    cursor: pointer;
    transition: all 0.15s;
  }}
  .step:hover {{ background: #2a2e3d; }}
  .step.pass {{ border-left-color: var(--pass); }}
  .step.warn {{ border-left-color: var(--warn); }}
  .step.fail {{ border-left-color: var(--fail); }}
  .step-header {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 8px;
  }}
  .step-header .criterion {{
    font-weight: 600;
    font-size: 14px;
  }}
  .step-header .score {{
    font-weight: 700;
    font-size: 14px;
  }}
  .step-header .score.pass {{ color: var(--pass); }}
  .step-header .score.warn {{ color: var(--warn); }}
  .step-header .score.fail {{ color: var(--fail); }}
  .step-detail {{
    display: none;
    margin-top: 12px;
    padding-top: 12px;
    border-top: 1px solid var(--border);
  }}
  .step.expanded .step-detail {{ display: block; }}
  .sub-score-bar {{
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 6px;
    font-size: 13px;
  }}
  .sub-score-bar .bar-container {{
    flex: 1;
    background: var(--bg);
    border-radius: 4px;
    height: 8px;
    overflow: hidden;
  }}
  .sub-score-bar .bar-fill {{
    height: 100%;
    border-radius: 4px;
    transition: width 0.3s ease;
  }}
  .sub-score-bar .bar-fill.pass {{ background: var(--pass); }}
  .sub-score-bar .bar-fill.warn {{ background: var(--warn); }}
  .sub-score-bar .bar-fill.fail {{ background: var(--fail); }}
  .badge {{
    display: inline-block;
    padding: 2px 8px;
    border-radius: 4px;
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
  }}
  .badge.pass {{ background: rgba(34,197,94,0.15); color: var(--pass); }}
  .badge.warn {{ background: rgba(245,158,11,0.15); color: var(--warn); }}
  .badge.fail {{ background: rgba(239,68,68,0.15); color: var(--fail); }}
  .evidence {{
    font-size: 13px;
    color: var(--text-secondary);
    margin-top: 8px;
    padding: 8px;
    background: var(--bg);
    border-radius: 6px;
    font-family: 'JetBrains Mono', monospace;
  }}
  .hints {{
    margin-top: 8px;
  }}
  .hints li {{
    font-size: 13px;
    color: var(--warn);
    margin-left: 16px;
    margin-bottom: 4px;
  }}
  .penalties {{
    margin-top: 8px;
  }}
  .penalty-tag {{
    display: inline-block;
    padding: 2px 8px;
    border-radius: 4px;
    font-size: 12px;
    background: rgba(239,68,68,0.1);
    color: var(--fail);
    margin: 2px 4px 2px 0;
  }}
  .filter-bar {{
    display: flex;
    gap: 8px;
    margin-bottom: 16px;
    flex-wrap: wrap;
  }}
  .filter-bar select {{
    background: var(--surface2);
    color: var(--text);
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 6px 12px;
    font-size: 13px;
  }}
</style>
</head>
<body>

<div class="header">
  <div>
    <h1>Verification Dashboard</h1>
    <div class="meta" id="taskMeta"></div>
  </div>
  <div style="text-align: right;">
    <div class="meta" id="timeMeta"></div>
  </div>
</div>

<div class="summary-cards" id="summaryCards"></div>

<div class="section">
  <h2>Score Trajectory</h2>
  <div class="chart-container">
    <canvas id="trajectoryChart"></canvas>
  </div>
</div>

<div class="section">
  <h2>Verification Steps</h2>
  <div class="filter-bar">
    <select id="filterStatus" onchange="renderSteps()">
      <option value="all">All Statuses</option>
      <option value="pass">Pass</option>
      <option value="warn">Warning</option>
      <option value="fail">Fail</option>
    </select>
    <select id="sortBy" onchange="renderSteps()">
      <option value="status">Sort by Status</option>
      <option value="points">Sort by Points Gap</option>
      <option value="name">Sort by Name</option>
    </select>
  </div>
  <div class="iteration-tabs" id="iterationTabs"></div>
  <div class="steps-grid" id="stepsGrid"></div>
</div>

<div class="section" id="criterionTrends">
  <h2>Criterion Trends Across Iterations</h2>
  <div class="chart-container">
    <canvas id="criterionChart"></canvas>
  </div>
</div>

<script>
const DATA = {data_json};
let activeIteration = DATA.iterations.length - 1;

function init() {{
  renderMeta();
  renderSummary();
  renderTrajectoryChart();
  renderIterationTabs();
  renderSteps();
  renderCriterionTrends();
}}

function renderMeta() {{
  document.getElementById('taskMeta').textContent =
    `${{DATA.domain}} | ${{DATA.task.substring(0, 80)}}${{DATA.task.length > 80 ? '...' : ''}}`;
  const iters = DATA.iterations.length;
  const final = DATA.iterations[iters - 1];
  document.getElementById('timeMeta').textContent =
    `${{iters}} iteration${{iters > 1 ? 's' : ''}} | ${{new Date(DATA.started_at).toLocaleString()}}`;
}}

function renderSummary() {{
  const final = DATA.iterations[DATA.iterations.length - 1];
  const pct = (final.percentage * 100).toFixed(1);
  const pctClass = final.percentage >= 0.85 ? 'pass' : final.percentage >= 0.5 ? 'warn' : 'fail';
  const totalSteps = final.steps.length;
  const passed = final.steps.filter(s => s.status === 'pass').length;
  const failed = final.steps.filter(s => s.status === 'fail').length;
  const warned = final.steps.filter(s => s.status === 'warn').length;

  document.getElementById('summaryCards').innerHTML = `
    <div class="card">
      <div class="label">Final Score</div>
      <div class="value ${{pctClass}}">${{pct}}%</div>
    </div>
    <div class="card">
      <div class="label">Points</div>
      <div class="value">${{final.total_score.toFixed(1)}}/${{final.max_score}}</div>
    </div>
    <div class="card">
      <div class="label">Passed</div>
      <div class="value pass">${{passed}}/${{totalSteps}}</div>
    </div>
    <div class="card">
      <div class="label">Warnings</div>
      <div class="value warn">${{warned}}</div>
    </div>
    <div class="card">
      <div class="label">Failed</div>
      <div class="value fail">${{failed}}</div>
    </div>
    <div class="card">
      <div class="label">Iterations</div>
      <div class="value">${{DATA.iterations.length}}</div>
    </div>
  `;
}}

function renderTrajectoryChart() {{
  const ctx = document.getElementById('trajectoryChart').getContext('2d');
  const labels = DATA.iterations.map(it => `Iter ${{it.number}}`);
  const scores = DATA.iterations.map(it => (it.percentage * 100).toFixed(1));

  new Chart(ctx, {{
    type: 'line',
    data: {{
      labels,
      datasets: [{{
        label: 'Score %',
        data: scores,
        borderColor: '#3b82f6',
        backgroundColor: 'rgba(59,130,246,0.1)',
        fill: true,
        tension: 0.3,
        pointRadius: 6,
        pointBackgroundColor: scores.map(s => s >= 85 ? '#22c55e' : s >= 50 ? '#f59e0b' : '#ef4444'),
      }}, {{
        label: 'Pass Threshold',
        data: labels.map(() => 85),
        borderColor: 'rgba(34,197,94,0.4)',
        borderDash: [5, 5],
        pointRadius: 0,
        fill: false,
      }}]
    }},
    options: {{
      responsive: true,
      maintainAspectRatio: false,
      scales: {{
        y: {{
          min: 0, max: 100,
          grid: {{ color: 'rgba(255,255,255,0.05)' }},
          ticks: {{ color: '#8b8fa3' }}
        }},
        x: {{
          grid: {{ color: 'rgba(255,255,255,0.05)' }},
          ticks: {{ color: '#8b8fa3' }}
        }}
      }},
      plugins: {{
        legend: {{ labels: {{ color: '#8b8fa3' }} }}
      }}
    }}
  }});
}}

function renderIterationTabs() {{
  const tabs = DATA.iterations.map((it, idx) => {{
    const cls = idx === activeIteration ? 'active' : '';
    const pct = (it.percentage * 100).toFixed(0);
    return `<button class="${{cls}}" onclick="activeIteration=${{idx}};renderIterationTabs();renderSteps()">
      Iter ${{it.number}} (${{pct}}%)
    </button>`;
  }}).join('');
  document.getElementById('iterationTabs').innerHTML = tabs;
}}

function renderSteps() {{
  const iteration = DATA.iterations[activeIteration];
  const filterStatus = document.getElementById('filterStatus').value;
  const sortBy = document.getElementById('sortBy').value;

  let steps = [...iteration.steps];

  if (filterStatus !== 'all') {{
    steps = steps.filter(s => s.status === filterStatus);
  }}

  if (sortBy === 'status') {{
    const order = {{ fail: 0, warn: 1, pass: 2 }};
    steps.sort((a, b) => order[a.status] - order[b.status]);
  }} else if (sortBy === 'points') {{
    steps.sort((a, b) => (a.percentage) - (b.percentage));
  }} else {{
    steps.sort((a, b) => a.criterion_id.localeCompare(b.criterion_id));
  }}

  const html = steps.map(step => {{
    const pct = (step.percentage * 100).toFixed(0);
    const subScoresHtml = Object.entries(step.sub_scores).map(([id, val]) => {{
      const valPct = (val * 100).toFixed(0);
      const cls = val >= 0.8 ? 'pass' : val >= 0.5 ? 'warn' : 'fail';
      return `<div class="sub-score-bar">
        <span style="width:140px;color:var(--text-secondary)">${{id}}</span>
        <div class="bar-container"><div class="bar-fill ${{cls}}" style="width:${{valPct}}%"></div></div>
        <span style="width:40px;text-align:right">${{valPct}}%</span>
      </div>`;
    }}).join('');

    const penaltiesHtml = step.penalties.length
      ? `<div class="penalties">${{step.penalties.map(p => `<span class="penalty-tag">${{p}}</span>`).join('')}}</div>`
      : '';

    const hintsHtml = step.improvement_hints.length
      ? `<ul class="hints">${{step.improvement_hints.map(h => `<li>${{h}}</li>`).join('')}}</ul>`
      : '';

    const evidenceHtml = step.evidence
      ? `<div class="evidence">${{step.evidence}}</div>`
      : '';

    return `<div class="step ${{step.status}}" onclick="this.classList.toggle('expanded')">
      <div class="step-header">
        <span class="criterion">${{step.criterion_id}} <span class="badge ${{step.status}}">${{step.status}}</span></span>
        <span class="score ${{step.status}}">${{step.points_earned}}/${{step.max_points}} (${{pct}}%)</span>
      </div>
      <div style="font-size:12px;color:var(--text-secondary)">${{step.methodology}}</div>
      <div class="step-detail">
        ${{subScoresHtml}}
        ${{penaltiesHtml}}
        ${{evidenceHtml}}
        ${{hintsHtml}}
      </div>
    </div>`;
  }}).join('');

  document.getElementById('stepsGrid').innerHTML = html;
}}

function renderCriterionTrends() {{
  if (DATA.iterations.length < 2) {{
    document.getElementById('criterionTrends').style.display = 'none';
    return;
  }}

  const criterionIds = DATA.iterations[0].steps.map(s => s.criterion_id);
  const colors = ['#3b82f6','#22c55e','#f59e0b','#ef4444','#8b5cf6','#ec4899','#14b8a6','#f97316','#6366f1','#84cc16'];
  const datasets = criterionIds.slice(0, 10).map((id, idx) => ({{
    label: id,
    data: DATA.iterations.map(it => {{
      const step = it.steps.find(s => s.criterion_id === id);
      return step ? (step.percentage * 100).toFixed(1) : 0;
    }}),
    borderColor: colors[idx % colors.length],
    tension: 0.3,
    pointRadius: 4,
    fill: false,
  }}));

  const ctx = document.getElementById('criterionChart').getContext('2d');
  new Chart(ctx, {{
    type: 'line',
    data: {{
      labels: DATA.iterations.map(it => `Iter ${{it.number}}`),
      datasets
    }},
    options: {{
      responsive: true,
      maintainAspectRatio: false,
      scales: {{
        y: {{
          min: 0, max: 100,
          grid: {{ color: 'rgba(255,255,255,0.05)' }},
          ticks: {{ color: '#8b8fa3' }}
        }},
        x: {{
          grid: {{ color: 'rgba(255,255,255,0.05)' }},
          ticks: {{ color: '#8b8fa3' }}
        }}
      }},
      plugins: {{
        legend: {{
          labels: {{ color: '#8b8fa3', font: {{ size: 11 }} }},
          position: 'bottom'
        }}
      }}
    }}
  }});
}}

init();
</script>
</body>
</html>"""
