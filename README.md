# Rubric System for auto-verification of complex tasks

A dual adversarial loop harness for high-quality task generation. Two GAN-inspired feedback cycles run in sequence: the first produces a rigorous evaluation rubric, the second iterates the actual task output against it — each with isolated agent contexts to prevent self-leniency.

**Eval results (Run 8: 10 complete tasks):** baseline 44.4% → harness 65%, mean lift **+20.6pp**. See [EVAL.md](EVAL.md).

## Architecture

```
                    ┌─────────────────────────────────────────────────────┐
                    │          LOOP 1: RUBRIC GAN                         │
                    │                                                     │
  Task ──► Expert   │  ┌─────────┐   ┌─────────┐   ┌────────────────┐   │
           Persona ─┼─►│  Web    │──►│Exemplar │──►│ RubricRAG Seed │   │
           Elicit.  │  │Research │   │Retrieval│   │  (past rubrics)│   │
                    │  └────┬────┘   └────┬────┘   └───────┬────────┘   │
                    │       └─────────────┴────────────────┘            │
                    │                     │                              │
                    │          ┌──────────▼──────────┐                   │
                    │          │  Multi-pass Hierarch.│                   │
                    │          │  Generation          │                   │
                    │          │  (3 expert personas) │                   │
                    │          └──────────┬───────────┘                   │
                    │                     │                               │
                    │       ┌─────────────▼──────────────┐               │
                    │       │ Adversarial Coverage Audit  │               │
                    │       │ Research Traceability Audit │               │
                    │       │ Quality Gate                │               │
                    │       └─────────────┬───────────────┘               │
                    └─────────────────────┼─────────────────────────────┘
                                          │ Rubric (20–35 criteria)
                    ┌─────────────────────▼─────────────────────────────┐
                    │          LOOP 2: OUTPUT GAN                        │
                    │                                                    │
                    │  Negotiation ──► GenerationAgent                  │
                    │  (sprint          (isolated ctx) ◄──────────────┐ │
                    │   contract)            │                         │ │
                    │                        ▼                         │ │
                    │                  ScoringAgent                    │ │
                    │                  (adversarial,    ──► pass?  ──►Result
                    │                   isolated ctx)       │         │ │
                    │                        │              │ no      │ │
                    │                        ▼              │         │ │
                    │                  FeedbackAgent  ──────┘         │ │
                    │                  (score → edit                  │ │
                    │                   instructions)                 │ │
                    │                        │                        │ │
                    │                  EvaluationAgent ───────────────┘ │
                    │                  (convergence,                     │
                    │                   regression gate)                 │
                    └────────────────────────────────────────────────────┘
```

## Loop 1: Rubric GAN

The rubric pipeline is itself adversarial: multiple stages challenge, expand, and audit the rubric before it's used to score anything.

### 5-Stage Expert Rubric Generation

**Stage 1 — Expert persona elicitation**
Before any research or generation, the system synthesizes a domain expert persona: credentials, focus areas, what they'd catch that a generalist would miss. Injected into all downstream prompts to shift criteria from generic quality dimensions toward domain-specific substance.

**Stage 2 — Deep domain research (3 phases)**
- **(A)** Professional standards and frameworks
- **(B)** Expert failure modes and common mistakes
- **(C)** Expert exemplar retrieval for contrastive criterion extraction

Research is the structural backbone, not optional context. Each research finding maps directly to criteria; ungrounded criteria are patched or removed by the research traceability audit.

**Stage 3 — Exemplar retrieval + contrastive criterion extraction**
Searches for expert-quality example outputs (published templates, award-winning examples, professional samples), then generates a single-shot baseline. The gap between exemplar and baseline is fed to the RubricAgent: *"For each dimension where the expert is clearly superior, generate a criterion that scores the expert at 90–100% and the baseline at 40–60%."* Produces the most discriminative criteria — derived from observed differences, not abstract quality dimensions.

**Stage 4 — RubricRAG: seed criteria from past rubrics**
`RubricStore` persists evaluation results across runs. Effectiveness-gated criteria extraction from past rubrics provides warm-start seeds for new rubric generation, filtered by domain relevance and historical criterion performance.

**Stage 5 — Quality gate**
After generation, two audits run:
- **Adversarial coverage audit**: a red-team pass generates plausible high-scoring-but-inadequate outputs to find rubric blind spots. Gaps trigger new criteria.
- **Research traceability audit**: verifies every criterion is grounded in the domain research. Ungrounded criteria are patched or removed.

### Multi-Pass Hierarchical Generation

Rather than generating a flat list of criteria, the rubric is built in three passes:
1. **Dimension decomposition** — break the task domain into evaluation dimensions
2. **Per-dimension criteria** — generate 2–5 criteria per dimension
3. **Cross-dimension calibration** — normalize scoring weights, remove redundancy, fill gaps

Targets **20–35 criteria**. Each criterion includes sub-attribute decomposition for fine-grained measurement.

### Expert Panel Simulation

Three complementary expert personas generate criteria from different vantage points (e.g., practitioner, critic, domain scientist). Their proposals are merged and deduplicated, preserving coverage that any single persona would miss.

### Rubric Negotiation

After generation and before iteration 1, `RubricNegotiationAgent` runs a 2-round sprint contract review: ambiguous or untestable criteria are refined. Ensures the rubric is objective before any generation begins.

---

## Loop 2: Output GAN

Six isolated agents iterate the actual task output. Each has its own `Anthropic()` client, system prompt, and context window.

| Agent | Role | What it never sees |
|-------|------|--------------------|
| **RubricNegotiationAgent** | Sprint contract: refines ambiguous/untestable criteria before iter 1 | Content, scores, generation strategy |
| **GenerationAgent** | Content creation | Scoring calibration, scorer system prompt, negotiation transcript |
| **ScoringAgent** | Adversarial two-stage measurement with embedded critiques | Generation prompt, task context, prior attempts |
| **FeedbackAgent** | Deterministic critique-to-instruction translator | Generation prompts, scoring calibration |
| **EvaluationAgent** | Pass/fail, regression detection, convergence | Generation strategy, rubric design rationale |
| **CriticAgent** | Rubric post-hoc calibration | Generation strategy |

**RubricLoop** is the orchestrator — not an agent itself.

### Scoring

**Two-stage checklist scoring** — Stage 1: binary fact extraction (YES/NO with evidence quotes). Stage 2: mechanical score mapping from Stage 1 facts. No holistic impressionistic ratings.

**Embedded critiques** — The ScoringAgent emits a single JSON where every sub-attribute includes its numeric score alongside structured critique data: a `critique` (1-2 sentence summary of what failed), a `suggestion` (specific improvement instruction), and `checks` (binary YES/NO items with exact evidence quotes from the content). This replaces the old two-section output (separate text checklist + JSON scores) and eliminates the fragile regex parsing that connected them.

**6 scoring methods**: `BINARY`, `PERCENTAGE`, `WEIGHTED_COMPONENTS`, `PENALTY_BASED`, `THRESHOLD_TIERS`, `COUNT_BASED`.

**Deterministic verifiers** — Before LLM scoring, `DeterministicVerifier` routes programmatically checkable criteria (count-based, length-based, format-based, code syntax, presence-based) to zero-variance code checks. Evidence shows exact results (e.g., "Word count: 247, target: under 300 ✓"). Disable with `--no-deterministic`.

**Anti-leniency** — Perfect score prohibition on iteration 1 (ceiling: 90%), calibration anchors, adversarial scorer system prompt.

### FeedbackAgent: Deterministic Critique Pipeline

The FeedbackAgent is the sole bridge between the ScoringAgent and the GenerationAgent. Its core design principle: **the scorer is the source of truth**, and feedback is constructed deterministically from the scorer's output — not by asking another LLM to interpret scores.

**How it works:**

1. The ScoringAgent scores content and emits structured critiques per sub-attribute: `{score, critique, suggestion, checks[{check, result, evidence}]}`.
2. The FeedbackAgent reads `_last_critiques` from the ScoringAgent directly. For each failing sub-attribute (score < 75%), it builds a fix item by copying the scorer's own words: the critique becomes `what_failed`, the measurement spec becomes `what_was_expected`, the failed check evidence becomes `what_was_found`, and the suggestion becomes the `instruction`. No LLM reinterpretation.
3. Fix items are sorted by `points_at_stake` (descending) so the generator works on the highest-leverage changes first.
4. Passing criteria (≥ 75%) are listed as `preserve` items — explicit "do not change" instructions.

**Regression content comparison (the one LLM call):** When a criterion's score drops >5% from its best prior iteration, the FeedbackAgent makes a single targeted LLM call that compares the actual content of the best iteration vs the current iteration. It returns three things: what content was lost, what change caused the regression, and a specific recovery instruction. This is the only part that requires content understanding and can't be done deterministically.

**Single signal to the generator:** The generator receives structured feedback as its sole instruction set. The EDIT_PROMPT no longer includes a separate score breakdown or focus section — those were redundant and created conflicting signals. Rule 4 of the EDIT_PROMPT now reads: "The STRUCTURED FEEDBACK FROM EVALUATOR below is your SOLE instruction set."

**Output format to the generator:**
```
REGRESSIONS (RECOVER THESE FIRST — highest priority):
  REGRESSED: criterion_x — was 80% at iter 2, now 55% (-25%)
    What was lost: [content comparison from LLM]
    Why it dropped: [content comparison from LLM]
    → RECOVER: [specific recovery instruction]

DO NOT CHANGE (these sections are passing):
  ✓ criterion_a: 85% — keep unchanged

REQUIRED FIXES (ordered by point impact):
  FIX 1: criterion_y.sub_z (current: 25%, 4.5 pts at stake)
    Scorer's critique: [scorer's own words]
    Measurement spec: [from rubric]
    Evidence found: [scorer's evidence quote]
    ✗ FAILED CHECK: Contains specific dollar thresholds
      Evidence: 'material amounts' with no numeric definition
    → ACTION: [scorer's own suggestion]
```

**FeedbackLearningLoop** tracks fix effectiveness across iterations: each prescribed fix is classified as EFFECTIVE, INEFFECTIVE, or HARMFUL based on whether the targeted criterion's score improved, stalled, or regressed. Accumulated learnings are distilled into markdown and injected into future runs.

### Iteration Control

**Iteration-aware generation** — Early (1–2): bold structural changes. Mid (3–4): add specificity and evidence. Late (5+): surgical fixes to the 2–3 weakest sub-attributes only.

**Regression recovery learning** — If score drops >5% from best prior iteration, flagged. Two consecutive regressions inject a "try a completely different approach" note into the next generation prompt. Best iteration (not latest) is the learning signal.

**Preserve-what-works constraint** — Criteria scoring ≥75% are protected from regression in subsequent iterations.

**Stall detection + early stopping** — Detects plateau and stops early when further iterations are unlikely to improve score.

**Trade-off detection** — Flags when improving one criterion degrades another.

**Per-criterion delta tracking** — Reports IMPROVED / REGRESSED / PLATEAUED per criterion from iter 1 → best → final.

**Observation masking + filesystem fallback** — Older iterations are replaced in-context with 3-line summaries while full artifacts live in `.rubric_iterations/`. Prevents context bloat from killing late-iteration quality.

---

## Self-Improvement Systems

Three interconnected loops close the feedback cycle across runs:

**SelfEditor** — Proposes and applies patches to rubric factories and scoring prompts based on accumulated criterion effectiveness data. All proposals validated with `ast.parse()` before applying. Run with `--self-improve` (dry run) or `--self-improve-apply`.

**Regression gate on self-edits** — Before/after eval confirms self-edits don't degrade performance. Proposals that fail regression are rejected.

**RubricStore + rubric seeding** — Persists full evaluation results (criteria, scores, task domain) to SQLite. Future rubric generation pulls effectiveness-gated seed criteria as warm-start context.

**Feedback persistence** — `FeedbackStore` persists human corrections across runs and injects them into generation and scoring prompts. Tracks which entries actually improved scores.

**Outcome tracking** — `OutcomeTracker` scans git reverts and CI failures to auto-close the learning loop on false passes.

**ACON paired trajectory system** — After every run, generates content twice: once with full iteration history, once with compressed history (3-line summaries + file pointers). Per-criterion deltas are recorded. After 5+ runs in a domain, `AconGuidelineLearner` classifies each criterion type:

- **SAFE** (max delta <2pp): compression has no measurable effect — always compress
- **CAUTION** (mean delta <3pp, stddev <4pp): minor risk — compress with monitoring
- **UNSAFE** (otherwise): compression degrades quality — keep full context

Guidelines stored in `~/.rubric_loop/acon_guidelines/{domain}/` and applied to future runs in the same domain. Disable with `--no-paired-trajectories`.

---

## Eval Results

See [EVAL.md](EVAL.md) for full Run 4 results.

| Run | Mean Baseline | Mean Harness | Mean Delta |
|-----|--------------|-------------|------------|
| Run 4 (9 valid tasks) | 46.9% | 72.9% | **+26.0pp** |

---

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
rubric_harness.py              # Core loop: all agents + RubricLoop orchestrator
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
├── deterministic_verifier.py  # Programmatic scoring for checkable criteria
├── acon_trajectory.py         # ACON paired trajectory system
├── sample_rubrics.py          # 10 task-specific rubrics + RubricRegistry
├── rubric_library.md          # 8 domain templates (API, Auth, DB, React, etc.)
├── knowledge_work_rubric.md   # 28-criteria research document rubric
└── frontend_design_rubric.md  # 17-criteria UI design rubric

tests/
└── test_integration.py        # 47 integration tests

rubrics/                       # Generated rubric .md files (one per run)
.rubric_iterations/            # Per-iteration artifact files (file-based handoff)
.rubric_feedback/              # Persistent feedback store (created at runtime)
~/.rubric_loop/                # ACON data + per-domain compression guidelines
```

## Requirements

- Python 3.9+
- `anthropic` package
- `ANTHROPIC_API_KEY` environment variable
