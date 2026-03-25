# Rubric System

A generation-verification loop for AI quality assurance. Conceptually a GAN where Claude generates output, scores it against structured rubrics, and iterates until quality thresholds are met — with a self-improvement engine that rewrites its own rubrics based on accumulated learnings.

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           Full Pipeline                                      │
│                                                                              │
│  Task ──► Deep Research ──► Rubric Generation ──► Gen-Verify Loop ──► Result│
│            (web_search)      (LLM + seeds +          ↑         ↓            │
│                               learning context)  generate   score           │
│                                                      ↑         ↓            │
│                                               Loop 1: feedback injection    │
│                                                                              │
│  ──────────────────────── Learning Loops ───────────────────────────────    │
│                                                                              │
│  Loop 1 (within-run)    Feedback store → injected into generation/scoring   │
│  Loop 2 (checkpoint)    Checkpoint policy learns when to pause from history │
│  Loop 3 (cross-run)     Criterion effectiveness tracking → RubricAgent  │
│                          ↑ LearningIntegrator feeds pass rates / bug rates  │
│                          ↑ OutcomeTracker closes loop via git/CI signals     │
│                                                                              │
│  ──────────────────── Self-Improvement Engine ─────────────────────────── │
│                                                                              │
│  SelfEditor: loop 3 insights → Claude proposes code patches → ast.parse()  │
│              validates → git commits to rubric factories / scoring prompts  │
└─────────────────────────────────────────────────────────────────────────────┘
```

**5 independent agents**: Each with its own `Anthropic()` client, system prompt, and isolated context window — no cross-agent context leakage:

| Agent | Role | Isolation Guarantee |
|-------|------|-------------------|
| **GenerationAgent** | Content creation | Never sees scoring calibration or rubric design rationale |
| **RubricAgent** | Rubric design grounded in web research | Never sees generated content or scores |
| **ScoringAgent** | Adversarial two-stage measurement | Never sees generation strategy or task context |
| **FeedbackAgent** | Translates scores into actionable editing instructions | Never sees generation prompts or scoring calibration |
| **EvaluationAgent** | Pass/fail decisions, regression detection, convergence | Only sees numeric score trajectories |

**Scoring engine**: 6 methods (binary, percentage, weighted components, penalty-based, threshold tiers, count-based) with sub-attribute decomposition for fine-grained measurement.

**Anti-leniency scoring**: Perfect score prohibition, calibration anchors, first-iteration ceiling — prevents the generator from gaming the scorer.

**Rubric markdown export**: Every run saves the full rubric as a human-readable `.md` file to `rubrics/`, capturing all criteria, scoring methods, sub-attributes, penalties, and research basis.

**Feedback loop**: Persistent memory that injects prior human feedback into both generation and scoring prompts, making the system learn your preferences over time.

**Checkpoint policy**: Learns when to pause for human verification based on task complexity, score trajectory, and historical feedback patterns.

**Convergence detection**: The loop runs until it passes or scores plateau — no arbitrary iteration cap. The EvaluationAgent detects convergence automatically.

**Verification dashboard**: Interactive HTML dashboard showing every verification step, sub-score breakdowns, and improvement trajectories.

## Quick Start

```bash
pip install anthropic
export ANTHROPIC_API_KEY=sk-ant-...

# Run from CLI (auto-detects best rubric, runs deep research, learns from history)
python rubric_harness.py "Implement rate limiting middleware"

# With options
python rubric_harness.py --threshold 0.90 --max-iter 7 "Write a research brief on AI chips"
python rubric_harness.py --file src/auth.ts --context "Add PKCE support" --auto-approve

# Rubric introspection
python rubric_harness.py --list-rubrics
python rubric_harness.py --explain "Write a cold outreach email to a CTO"

# Control learning and research
python rubric_harness.py --no-research "Quick task where speed matters"
python rubric_harness.py --no-learn "Experimental run — don't track outcomes"

# Self-improvement (dry run to preview proposed code edits)
python rubric_harness.py --self-improve "any task"

# Self-improvement (apply edits to source files)
python rubric_harness.py --self-improve-apply "any task"
```

### As a Python Library

```python
import asyncio
from rubric_harness import RubricLoop

async def main():
    loop = RubricLoop(
        pass_threshold=0.85,
        max_iterations=5,
        feedback_dir=".rubric_feedback",
        enable_checkpoints=True,
        enable_self_improve=True,   # criterion effectiveness tracking + auto-editing
        enable_research=True,       # deep web research before rubric generation
    )
    result = await loop.run("Write a research brief on AI chip market trends")

    print(f"Success: {result.success}")
    print(f"Score: {result.final_percentage:.0%}")
    print(f"Iterations: {result.iterations}")

    # Save verification dashboard
    loop.save_dashboard("dashboard.html")

    # Add feedback for future runs
    loop.add_feedback("scoring", "Too lenient on source freshness",
                      criterion_id="src_freshness")

    # Run self-improvement dry run
    proposals = loop.self_improve(dry_run=True)

asyncio.run(main())
```

### As a Claude Code Skill

```bash
mkdir -p .claude/skills
cp rubric-loop-skill.md .claude/skills/rubric-loop.md
```

Then say "make sure it's right" or "production quality" in Claude Code and it will follow the generation-verification loop.

### With Checkpoints (Interactive)

```python
from rubric_harness import RubricLoop

def my_checkpoint_handler(checkpoint):
    """Called when the system wants human verification."""
    print(checkpoint.format_prompt())
    action = input("[continue/adjust/feedback/stop]: ").strip() or "continue"
    feedback = ""
    if action == "feedback":
        feedback = input("Feedback: ")
    return action, feedback

loop = RubricLoop(
    enable_checkpoints=True,
    checkpoint_callback=my_checkpoint_handler,
)
result = await loop.run("Design a billing system API")
```

Checkpoint types: `rubric_review` (before work starts), `first_attempt` (after iter 1), `critical_gate` (when critical criteria first pass), `plateau_check` (score stops improving), `mid_loop` (halfway), `pre_final` (last chance to adjust).

### CI Integration (PR Quality Gate)

```bash
# Generate config + GitHub Actions workflow
python -m rubric_system.rubric_ci --init

# Run manually
python -m rubric_system.rubric_ci --base-ref main --output results.md
```

## Deep Research

Before generating any rubric, the system performs domain research to ground criteria in real-world professional standards rather than generic LLM intuitions.

**How it works:**
- Calls Claude with the `web_search` tool (up to 5 searches)
- Searches for: domain expert quality standards, measurable criteria, common failure modes, non-obvious quality signals specific to the task type
- Research brief is injected directly into the rubric generation prompt
- Result: criteria that reflect what practitioners actually care about, not what sounds plausible

**Example searches for "investment memo":**
> "investment memo quality criteria VC standards", "what makes a good investment memo failure modes", "investment memo measurable benchmarks due diligence"

**Skip for speed:**
```bash
python rubric_harness.py --no-research "Quick internal task"
```

## Rubric Generation

When no matching built-in rubric exists (or the task is novel), `RubricAgent` creates a bespoke rubric via LLM in an isolated context window.

**Pipeline:**
1. **Deep Research** — web search for domain best practices (see above)
2. **Seed Examples** — pulls closest-matching rubrics from `RubricRegistry` as few-shot examples
3. **Learning Context** — `LearningIntegrator` injects criterion effectiveness data from prior runs (pass rates, bug rates, false positive rates)
4. **LLM Generation** — `RubricAgent` (with its own system prompt and `Anthropic()` client) generates rubric JSON with criteria, scoring methods, weights, and pass conditions
5. **Research Traceability Audit** — `ResearchTracer` verifies each criterion is grounded in the web research; ungrounded criteria are patched or removed
6. **Hydration** — JSON is parsed and instantiated into canonical `Criterion` + `ScoringRubric` objects
7. **Markdown Export** — full rubric saved as a human-readable `.md` file to `rubrics/`

**Default path**: Every run uses `RubricAgent` unless `--no-generate` is passed. You never need to specify a rubric manually — just give it a task.

```python
from rubric_harness import RubricAgent

agent = RubricAgent(enable_research=True)
rubric = agent.generate("Audit a Kubernetes RBAC configuration for least-privilege violations")
# Returns a fully hydrated Rubric with 5–10 measurable Criterion objects
# Also saved as rubrics/rubric_<timestamp>_<hash>.md
```

## Task-Level Rubric Resolution

`RubricRegistry` automatically selects the best pre-built rubric for a task using `RubricSignature` scoring. If no signature matches well, generation kicks in.

**Signature scoring:**

| Signal | Score |
|--------|-------|
| Keyword match | +1.0 |
| Anti-keyword match | −2.0 |
| Task pattern (regex) match | +1.5 |
| Priority bonus | +0–0.5 |

**12 registered rubrics** (2 domain + 10 sample). Ties broken by priority.

```bash
# List all registered rubrics
python rubric_harness.py --list-rubrics

# Explain why a rubric was chosen for a task
python rubric_harness.py --explain "Write a cold outreach email to a CTO"
# Output: matched 'cold_outreach_email' (score 4.5) — keywords: [email, outreach, cold]
#         runner-up: 'investment_memo' (score 0.5)
```

**Explicit override:**
```bash
python rubric_harness.py --rubric knowledge_work_research "Write a report on quantum computing"
```

## Self-Improvement Engine

The most distinctive capability: the harness rewrites its own source code based on what it learns across runs.

```bash
# Also available as a standalone command
python -m rubric_system.self_improve scan|propose|apply|auto|history|revert
```

### OutcomeTracker

Auto-closes Loop 3 by scanning external signals to determine whether a rubric evaluation was accurate.

**Signal sources:**
- **Git**: Detects revert commits and hotfix branches within N days of a rubric evaluation — signals a false pass
- **CI**: Detects test failures on files that previously passed rubric — signals undetected issues
- **Manual**: `tracker.report_outcome(rubric_id, "bug_found", "Prod incident on auth flow")`

```python
from rubric_system.self_improve import OutcomeTracker
from rubric_system.rubric_learning import RubricStore

store = RubricStore()
tracker = OutcomeTracker(store)
tracker.scan_git_outcomes(repo_path="/path/to/repo", lookback_days=14)
tracker.scan_ci_failures(ci_results_dir=".ci_results/")
```

### LearningIntegrator

Bridges `RubricLearner` criterion effectiveness data into `RubricAgent` at generation time. Ensures newly generated rubrics avoid repeating criteria that have historically underperformed.

**What it injects:**
- Criteria with high false positive rates ("always passes even when quality is low")
- Criteria with high false negative rates ("passes but bugs found later")
- Criteria that reliably predict good outcomes (reinforce these)
- Task similarity context from past successful evaluations

```python
from rubric_system.self_improve import LearningIntegrator

integrator = LearningIntegrator(store, feedback_store)
context = integrator.build_learning_context(task="Write a Python CSV parser")
# context is injected into RubricAgent.generate() automatically
```

### SelfEditor

The core self-editing capability. Analyzes criterion effectiveness data, calls Claude to propose code patches to rubric factory functions and scoring prompts, validates with `ast.parse()`, and commits.

**What it edits:**
- Scoring rubric factories (the functions that build `ScoringRubric` objects)
- Measurement prompts (the LLM instructions used to score each criterion)
- Generation prompts (the system prompt for `RubricAgent`)

**Safety:**
- All proposals validated with `ast.parse()` before applying — syntax errors are rejected
- Dry run mode (`--self-improve`) previews proposals without touching files
- Full edit history with revert support

```bash
# Preview what would be changed
python rubric_harness.py --self-improve "any task"

# Apply changes
python rubric_harness.py --self-improve-apply "any task"

# View edit history
python -m rubric_system.self_improve history

# Revert last edit
python -m rubric_system.self_improve revert
```

## Project Structure

```
rubric_system/
├── rubric_harness.py              # Core loop: RubricLoop, 5 agents (Generation, Rubric, Scoring, Feedback, Evaluation)
├── rubric_claude_code.py          # Claude Code CLI wrapper + approval workflow
├── rubric-loop-skill.md           # Claude Code skill definition
├── rubric-loop-harness-spec.md    # Original system spec
│
├── rubric_system/                 # Package modules
│   ├── models.py                  # All dataclasses + enums (single source of truth)
│   ├── scoring_engine.py          # Standalone scoring engine (6 methods)
│   ├── feedback_loop.py           # Persistent feedback store + prompt injection
│   ├── verification_dashboard.py  # Interactive HTML dashboard generator
│   ├── checkpoint_policy.py       # When to pause for human verification
│   ├── rubric_ci.py               # GitHub Actions CI integration
│   ├── rubric_learning.py         # SQLite criterion effectiveness tracking
│   ├── metrics_dashboard.py       # Chart.js metrics dashboard
│   ├── test_generator.py          # Auto-generate tests from rubric criteria
│   ├── self_improve.py            # Self-improvement engine (OutcomeTracker, LearningIntegrator, SelfEditor)
│   ├── sample_rubrics.py          # 10 task-specific rubrics with RubricRegistry integration
│   ├── rubric_library.md          # 8 domain templates (API, Auth, DB, React, etc.)
│   ├── knowledge_work_rubric.md   # 28-criteria research document rubric
│   └── frontend_design_rubric.md  # 17-criteria UI design rubric
│
├── tests/
│   └── test_integration.py        # 47 integration tests
│
├── rubrics/                       # Generated rubric .md files (one per run)
│
└── .rubric_feedback/              # Created at runtime
    ├── rubric/                    # Rubric adjustment feedback
    ├── scoring/                   # Scoring calibration feedback
    ├── verification/              # Verification feedback
    ├── general/                   # General preferences
    └── checkpoint_history.json    # Checkpoint learning data
```

## Scoring Methods

| Method | How It Works | Example |
|--------|-------------|---------|
| `BINARY` | Full points or zero | "Exactly 5 names provided" → 4 or 0 pts |
| `PERCENTAGE` | Linear scale | "75% of sources current" → 7.5/10 pts |
| `WEIGHTED_COMPONENTS` | Sub-attributes with weights | Freshness: headline (50%) + supporting (30%) + overall (20%) |
| `PENALTY_BASED` | Start at max, deduct for violations | 8 pts - sycophantic (-2) - salesy (-2) = 4 pts |
| `THRESHOLD_TIERS` | Discrete tiers | Value 85% → "good" tier → 7/10 pts |
| `COUNT_BASED` | Points per instance, capped | 3 test cases × 2 pts = 6/10 pts |

## Sample Rubrics (10 Built-In)

| # | Task | Domain | Criteria | Max Pts | Threshold |
|---|------|--------|----------|---------|-----------|
| 1 | Cold outreach email | `cold_outreach_email` | 7 | 56 | 80% |
| 2 | Python CSV parser | `code_generation` | 5 | 44 | 85% |
| 3 | Executive summary (3 bullets) | `summarization` | 4 | 38 | 85% |
| 4 | SQL top-10 by LTV | `sql_query` | 4 | 36 | 85% |
| 5 | AGI counterargument | `argumentation` | 4 | 36 | 80% |
| 6 | SaaS billing JSON schema | `schema_design` | 4 | 38 | 85% |
| 7 | Explain attention to a teen | `explanation` | 4 | 36 | 80% |
| 8 | Startup names (AI contract review) | `creative_naming` | 5 | 36 | 75% |
| 9 | Bash PostgreSQL backup to S3 | `bash_scripting` | 5 | 44 | 85% |
| 10 | Investment memo (defense drones) | `investment_memo` | 5 | 44 | 85% |

```python
from rubric_system.sample_rubrics import build_rubric_for_task
rubric = build_rubric_for_task(1)  # Cold outreach email
```

## Domain Rubrics

Two comprehensive domain rubrics with full scoring rubric factories:

**Knowledge Work Research** (in harness): 28 criteria, 74 points. Categories: source quality, evidence & claims, data & visualizations, forward-looking statements, document structure, professional polish. Based on CRAAP Test, journalism triangulation, PLOS, APA JARS.

**Frontend Design** (in harness): 17 criteria, 142 points. Categories: color system, typography, spacing/layout, components/patterns, visual polish, accessibility. Includes anti-patterns catalog.

## Feedback System

The feedback loop makes the system learn from your corrections:

```python
# After a run, add feedback
loop.add_feedback("rubric", "src_freshness is too strict for historical topics",
                  criterion_id="src_freshness", domain="knowledge_work_research")

loop.add_feedback("scoring", "The scorer missed that sources were paywalled",
                  criterion_id="src_authority")

loop.add_feedback("general", "I prefer concise outputs under 500 words")
```

Feedback is stored in `.rubric_feedback/` and automatically injected into relevant future prompts. The system tracks which feedback entries actually improved scores and weights them accordingly.

## Tests

```bash
pip install pytest
python -m pytest tests/ -v
```

47 tests covering: import chains, model consistency, all 10 sample rubrics, all 6 scoring methods (perfect + zero scores), improvement hints generation.

## Requirements

- Python 3.10+
- `anthropic` (for LLM calls in the loop)
- `pytest` (for tests, dev only)
