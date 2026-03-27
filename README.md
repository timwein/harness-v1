# Rubric System

A generation-verification loop harness. GAN-inspired: Claude generates output, scores it against a task-specific rubric, and iterates until quality threshold is met — with each agent operating in an isolated context window to prevent self-leniency bias.

## Architecture

```
Task ──► Web Research ──► RubricAgent ──► Negotiation ──► Gen-Verify Loop ──► Result
          (5 searches)    (isolated ctx)   (isolated ctx)     ↑           ↓
                                                           generate     score
                                                        [Generator]  [ScoringAgent]
                                                              ↑           ↓
                                                          [FeedbackAgent] (translates scores)
                                                              ↑
                                                        [EvaluationAgent] (pass/fail, convergence)
```

**6 independent agents** — each with its own `Anthropic()` client, system prompt, and isolated context window:

| Agent | Role | What it never sees |
|-------|------|--------------------|
| **RubricAgent** | Rubric design grounded in web research | Generated content or scores |
| **RubricNegotiationAgent** | Sprint contract: refines ambiguous/untestable criteria before iter 1 | Content, scores, generation strategy |
| **GenerationAgent** | Content creation | Scoring calibration, scorer system prompt, negotiation transcript |
| **ScoringAgent** | Adversarial two-stage measurement | Generation prompt, task context, prior attempts |
| **FeedbackAgent** | Translates raw scores → actionable editing instructions | Generation prompts, scoring calibration |
| **EvaluationAgent** | Pass/fail decisions, regression detection, convergence | Generation strategy, rubric design rationale |

**RubricLoop** is the orchestrator — not an agent itself.

The GAN-inspired separation between generator and evaluator is the core fix for self-leniency: when Claude scores its own work in the same context, it grades generously. Fresh contexts with adversarial system prompts produce honest scores.

## Key Features

**Web-research-grounded rubric generation** — Before generating any rubric, the system calls Claude with `web_search` (up to 5 queries) to ground criteria in real professional standards, not generic LLM intuitions. Each criterion is traced back to the research via `ResearchTracer`; ungrounded criteria are patched or removed.

**8–12 criteria per rubric, 6 scoring methods** — `BINARY`, `PERCENTAGE`, `WEIGHTED_COMPONENTS`, `PENALTY_BASED`, `THRESHOLD_TIERS`, `COUNT_BASED`. Sub-attribute decomposition gives fine-grained per-dimension measurement.

**Two-stage checklist scoring** — Stage 1: binary fact extraction (YES/NO observations with evidence quotes). Stage 2: mechanical score mapping from Stage 1 facts. No impressionistic holistic ratings.

**Rubric negotiation** — After rubric generation and before iteration 1, `RubricNegotiationAgent` reviews each criterion for ambiguity or untestability and returns a refined rubric. This "sprint contract" ensures the rubric is objective before any generation begins. One extra LLM call; skipped if `--no-generate` is active.

**Iteration-aware generation** — Early iterations (1–2): bold structural changes. Mid (3–4): add specificity and evidence. Late (5+): surgical fixes to the 2–3 weakest sub-attributes only. Disable with `--lean` for A/B testing against newer models.

**Regression detection with consecutive tracking** — If a score drops >5% from the best prior iteration, it's flagged. Two consecutive regressions trigger a "try a completely different approach" note injected into the next generation prompt.

**Per-criterion delta tracking** — After the loop completes, reports IMPROVED / REGRESSED / PLATEAUED status for every criterion from iter 1 → best → final, making feedback loop effectiveness visible.

**File-based artifact handoffs** — Each iteration's artifact is written to `.rubric_iterations/` before scoring. Keeps bulk content off the context window; enables crash resumability.

**Anti-leniency scoring** — Perfect score prohibition on iteration 1 (ceiling: 90%), calibration anchors, and an adversarial scorer system prompt. Prevents the generator from gaming the scorer.

**Self-improvement engine** — `OutcomeTracker` closes Loop 3 by scanning git reverts and CI failures to detect false passes. `LearningIntegrator` injects criterion effectiveness data from prior runs into `RubricAgent` at generation time. `SelfEditor` proposes and applies code patches to rubric factories and scoring prompts; all proposals validated with `ast.parse()` before applying.

**12 domain-specific rubric templates** — 10 sample rubrics + 2 comprehensive domain rubrics (Knowledge Work Research: 28 criteria, 74 pts; Frontend Design: 17 criteria, 142 pts). Auto-selected via `RubricRegistry` keyword/pattern matching; overridable with `--rubric`.

**Persistent feedback loop** — `FeedbackStore` persists human corrections across runs and injects them into generation and scoring prompts. Tracks which feedback entries actually improved scores.

**Rubric markdown export** — Every run saves the full rubric to `rubrics/rubric_<timestamp>_<hash>.md` capturing all criteria, scoring methods, sub-attributes, penalties, and research basis.

## CLI Usage

```bash
pip install anthropic
export ANTHROPIC_API_KEY=sk-ant-...

# Basic run
python rubric_harness.py "Implement rate limiting middleware"

# With options
python rubric_harness.py --threshold 0.90 --max-iter 7 "Write a research brief on AI chips"

# Warm-start from existing draft
python rubric_harness.py --seed draft.md "Write a research brief on AI chips"

# With context files (notes, reference docs, chat summaries)
python rubric_harness.py --context notes.md data.csv "Analyze Q3 earnings"

# Force a specific rubric
python rubric_harness.py --rubric knowledge_work_research "Write a report on quantum computing"

# Skip rubric generation, use registry matching only
python rubric_harness.py --no-generate "Python CSV parser"

# List registered rubrics / explain rubric selection
python rubric_harness.py --list-rubrics
python rubric_harness.py --explain "Write a cold outreach email to a CTO"

# Lean mode (strips early/mid/late iteration scaffolding)
python rubric_harness.py --lean "any task"

# Control research and learning
python rubric_harness.py --no-research "Quick internal task"
python rubric_harness.py --no-learn "Experimental run — don't track outcomes"
python rubric_harness.py --no-auto-improve "Run but don't auto-edit source"

# Self-improvement
python rubric_harness.py --self-improve "any task"        # dry run: preview proposed edits
python rubric_harness.py --self-improve-apply "any task"  # apply edits to source files

# JSON output
python rubric_harness.py --json "any task"
```

**All flags:**

| Flag | Default | Description |
|------|---------|-------------|
| `--max-iter / -m` | `0` (unlimited) | Stop after N iterations |
| `--threshold / -t` | `0.85` | Pass threshold (0–1) |
| `--seed / -s` | — | Warm-start: score existing draft instead of generating iter 1 |
| `--context / -c` | — | One or more context files injected into generation prompts |
| `--rubric / -r` | — | Override rubric registry selection |
| `--no-generate` | off | Use registry matching only, skip LLM rubric generation |
| `--lean` | off | Strip iteration-aware scaffolding (early/mid/late strategy) |
| `--no-research` | off | Skip web research step in rubric generation |
| `--no-learn` | off | Disable criterion effectiveness tracking for this run |
| `--no-auto-improve` | off | Disable automatic self-editing (keeps learning active) |
| `--self-improve` | off | Dry run: propose source code edits based on learning data |
| `--self-improve-apply` | off | Apply proposed source code edits |
| `--json / -j` | off | Emit result as JSON |
| `--quiet / -q` | off | Suppress verbose logging |
| `--list-rubrics` | — | Print all registered rubrics and exit |
| `--explain` | — | Show rubric resolution scoring for a task and exit |

## Custom Commands

- `/verify <task>` — Run the rubric gen-verify loop on any task
- `/verify-improve` — Analyze accumulated criterion effectiveness data and propose source code edits

## Project Structure

```
rubric_harness.py              # Core loop: all 6 agents + RubricLoop orchestrator
rubric-loop-harness-spec.md    # Full system spec

rubric_system/
├── models.py                  # All dataclasses + enums (single source of truth)
├── scoring_engine.py          # Standalone scoring engine (6 methods)
├── self_improve.py            # OutcomeTracker, LearningIntegrator, SelfEditor
├── rubric_learning.py         # SQLite criterion effectiveness tracking
├── feedback_loop.py           # Persistent feedback store + prompt injection
├── checkpoint_policy.py       # When to pause for human verification
├── verification_dashboard.py  # Interactive HTML dashboard generator
├── rubric_ci.py               # GitHub Actions CI integration
├── metrics_dashboard.py       # Chart.js metrics dashboard
├── test_generator.py          # Auto-generate tests from rubric criteria
├── sample_rubrics.py          # 10 task-specific rubrics + RubricRegistry
├── rubric_library.md          # 8 domain templates (API, Auth, DB, React, etc.)
├── knowledge_work_rubric.md   # 28-criteria research document rubric
└── frontend_design_rubric.md  # 17-criteria UI design rubric

tests/
└── test_integration.py        # 47 integration tests

rubrics/                       # Generated rubric .md files (one per run)
.rubric_iterations/            # Per-iteration artifact files (file-based handoff)
.rubric_feedback/              # Persistent feedback store (created at runtime)
```

## Requirements

- Python 3.9+
- `anthropic` package
- `ANTHROPIC_API_KEY` environment variable
