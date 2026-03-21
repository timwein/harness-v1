# Rubric System

A generation-verification loop for AI quality assurance. Conceptually a GAN where Claude generates output, scores it against structured rubrics, and iterates until quality thresholds are met.

## Architecture

```
Task → detect_domain() → build_rubric() → [generate → score → checkpoint → iterate] → LoopResult
                                                ↑                    ↓
                                          feedback_store ←── human feedback
```

**Core loop**: Two separate LLM calls per iteration — one generates content, one scores it against the rubric. Structural separation between generator and discriminator.

**Scoring engine**: 6 methods (binary, percentage, weighted components, penalty-based, threshold tiers, count-based) with sub-attribute decomposition for fine-grained measurement.

**Feedback loop**: Persistent memory that injects prior human feedback into both generation and scoring prompts, making the system learn your preferences over time.

**Checkpoint policy**: Learns when to pause for human verification based on task complexity, score trajectory, and historical feedback patterns.

**Verification dashboard**: Interactive HTML dashboard showing every verification step, sub-score breakdowns, and improvement trajectories.

## Quick Start

```bash
pip install anthropic
export ANTHROPIC_API_KEY=sk-ant-...

# Run from CLI
python rubric_claude_code.py "Implement rate limiting middleware"

# With options
python rubric_claude_code.py --threshold 0.90 --max-iter 7 "Write a research brief on AI chips"
python rubric_claude_code.py --file src/auth.ts --task "Add PKCE support" --auto-approve
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

## Project Structure

```
rubric_system/
├── rubric_harness.py              # Core loop: RubricLoop, domain detection, rubric builders
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
│   ├── sample_rubrics.py          # 10 task-specific rubrics
│   ├── rubric_library.md          # 8 domain templates (API, Auth, DB, React, etc.)
│   ├── knowledge_work_rubric.md   # 28-criteria research document rubric
│   └── frontend_design_rubric.md  # 17-criteria UI design rubric
│
├── tests/
│   └── test_integration.py        # 47 integration tests
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
