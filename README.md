# Rubric System

A generation-verification loop harness. GAN-inspired: Claude creates a rubric, then generates output, scores it against the task-specific rubric, and iterates until quality threshold is met — with each agent operating in an isolated context window to prevent self-leniency bias.

## Architecture

```
Task ──► Web Research ──► RubricAgent ──► Negotiation ──► Gen-Verify Loop ──► Result
          (web research)  (isolated ctx)   (isolated ctx)     ↑           ↓
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

**Web-research-grounded rubric generation** — Before generating any rubric, the system calls Claude with `web_search` (uncapped — the model searches as much as needed) to ground criteria in real professional standards, not generic LLM intuitions. Each criterion is traced back to the research via `ResearchTracer`; ungrounded criteria are patched or removed. Research runs in three phases: (A) professional standards and frameworks, (B) expert failure modes and common mistakes, (C) expert exemplar retrieval for contrastive criterion extraction.

**Expert persona elicitation** — Before rubric generation, the system synthesizes a domain expert persona: credentials, focus areas, and what they'd catch that a generalist would miss. This persona is injected into both the rubric generation and web research prompts, shifting criteria from generic quality dimensions toward domain-specific substance. One short LLM call; disable with `--no-expert-persona`.

**Exemplar retrieval + contrastive criterion extraction** — During research, the system searches for expert-quality example outputs for similar tasks (published templates, award-winning examples, professional samples). It also generates a quick single-shot baseline. The gap between expert exemplar and baseline is fed to the RubricAgent: "For each dimension where the expert is clearly superior, generate a criterion that scores the expert at 90-100% and the baseline at 40-60%." This produces the most discriminative criteria — derived from observed differences, not abstract quality dimensions. Disable with `--no-exemplar`.

**8–12 criteria per rubric, 6 scoring methods** — `BINARY`, `PERCENTAGE`, `WEIGHTED_COMPONENTS`, `PENALTY_BASED`, `THRESHOLD_TIERS`, `COUNT_BASED`. Sub-attribute decomposition gives fine-grained per-dimension measurement.

**Two-stage checklist scoring** — Stage 1: binary fact extraction (YES/NO observations with evidence quotes). Stage 2: mechanical score mapping from Stage 1 facts. No impressionistic holistic ratings. Criteria that are programmatically verifiable are routed to deterministic checks instead of LLM judgment.

**Deterministic verifiers** — Before LLM scoring, the `DeterministicVerifier` scans each criterion for programmatically checkable sub-attributes: count-based ("at least N items"), length-based ("under X words"), format-based ("includes headers"), code syntax (Python `ast.parse`, SQL, bash), and presence-based ("mentions X"). Matching criteria are scored with zero-variance code checks; the rest fall through to the LLM scorer. Evidence shows the exact check result (e.g., "Word count: 247, target: under 300 ✓"). Disable with `--no-deterministic`.

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

**ACON paired trajectories (cross-task compression learning)** — After every run, the system automatically generates content twice: once with full iteration history, once with compressed history (3-line summaries + file pointers). Both paths are scored, and per-criterion deltas are recorded. After 5+ runs in a domain, `AconGuidelineLearner` classifies each criterion type as:

- **SAFE** (max delta <2pp): compression has no measurable effect — always compress
- **CAUTION** (mean delta <3pp, stddev <4pp): minor risk — compress with monitoring
- **UNSAFE** (otherwise): compression degrades quality — keep full context

This learns which types of criteria are sensitive to context loss *across tasks within a domain*, not just within a single run. Guidelines are stored in `~/.rubric_loop/acon_guidelines/{domain}/` and automatically applied to future runs in the same domain.

Paired trajectories run by default. Disable with `--no-paired-trajectories`. Control which iteration is used for the paired comparison with `--paired-iteration N` (default: 2).

Data storage:
- `~/.rubric_loop/acon_paired_results.json` — raw paired results per run
- `~/.rubric_loop/acon_guidelines/{domain}/` — learned compression guidelines per domain

**Observation masking + filesystem fallback** — Older iterations are replaced in-context with 3-line summaries (score, delta, top focus areas) while full artifacts live in `.rubric_iterations/`. The scoring agent can selectively re-read specific iterations from disk when needed. This prevents context bloat from killing late-iteration quality.

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
| `--no-expert-persona` | off | Skip expert persona elicitation in rubric generation |
| `--no-exemplar` | off | Skip exemplar retrieval and contrastive criterion extraction |
| `--no-deterministic` | off | Disable deterministic verifiers, use all-LLM scoring |
| `--no-tradeoff-detection` | off | Skip trade-off detection between criteria |
| `--no-rubric-critic` | off | Skip rubric critic calibration step |
| `--no-paired-trajectories` | off | Disable ACON paired trajectory collection |
| `--paired-iteration` | `2` | Which iteration to run paired paths on |
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
├── deterministic_verifier.py   # Programmatic scoring for checkable criteria (counts, lengths, syntax)
├── acon_trajectory.py          # ACON paired trajectory system (cross-task compression learning)
├── sample_rubrics.py          # 10 task-specific rubrics + RubricRegistry
├── rubric_library.md          # 8 domain templates (API, Auth, DB, React, etc.)
├── knowledge_work_rubric.md   # 28-criteria research document rubric
└── frontend_design_rubric.md  # 17-criteria UI design rubric

tests/
└── test_integration.py        # 47 integration tests

rubrics/                       # Generated rubric .md files (one per run)
.rubric_iterations/            # Per-iteration artifact files (file-based handoff)
.rubric_feedback/              # Persistent feedback store (created at runtime)
~/.rubric_loop/                # ACON data (paired results + per-domain compression guidelines)
```

## Requirements

- Python 3.9+
- `anthropic` package
- `ANTHROPIC_API_KEY` environment variable
