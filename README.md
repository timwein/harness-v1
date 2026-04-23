# Auto-verification of complex tasks

A dual adversarial loop harness for high-quality task generation. Two feedback cycles run in sequence: the first produces a rigorous evaluation rubric, the second iterates the actual task output against it — each with isolated agent contexts to prevent self-leniency. The rubric-generation pipeline is aligned with **OpenRubrics** (Liu et al., arXiv 2510.07743): contrastive rubric generation, a two-tier hard-rule / principle taxonomy, and a preference-label consistency filter that rejection-samples rubrics which cannot reproduce known-preferred outcomes. See **[OpenRubrics Alignment](#openrubrics-alignment)** below.

**Eval results (4 hardest tasks, re-run on the aligned pipeline):** mean harness delta **+40.5pp** over the aligned-rubric baseline, with every prior regression converted to a strong positive delta. See [openrubrics-alignment-plan.md](openrubrics-alignment-plan.md) for the plan that drove the work and [EVAL.md](EVAL.md) for cross-run history.

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

## OpenRubrics Alignment

The rubric-generation pipeline is aligned with insights from **OpenRubrics** (Liu et al., arXiv 2510.07743): a scalable method for producing rubric-based reward signals that beats size-matched scalar / pairwise reward models by **+6.8–8.4%** on instruction-following and biomedical benchmarks. The paper's key result — that rubrics grounded in real preference pairs, split into hard rules vs. principles, and rejection-sampled against preference-label consistency outperform hand-authored or naively-generated rubrics — translates directly into our gen-verify loop.

Five phases were added in staged, independently-useful commits. All five are on by default; each can be disabled via a `--no-phaseN` flag for A/B testing and cost control.

### Phase 1 — Contrastive Rubric Generation (CRG)

**Problem:** our prior pipeline conditioned only on the task + web research + seed rubrics. Near-miss examples were **imagined** by the generator. OpenRubrics instead conditions on real `(preferred, rejected)` pairs and asks the model to extract the distinguishing features first, then write criteria that cite those features.

**Implementation** — `rubric_system/reference_pairs.py`:
- `ReferencePairResolver` picks up to 3 pairs in priority order: **caller-supplied → mined from RubricStore → self-contrast from provisional attempts → synthetic from a single Claude call**.
- Mining: cross-joins `scored_rubrics` rows with `outcome="success"` against `outcome="bug_found"` on the same `task_hash` (uses the `attempt_text` column added to the existing store; back-populated on new writes).
- Synthetic fallback: one generator-model call produces three pairs as JSON; tolerant parser handles fences and prose wrappers.
- Before emitting criteria, the generator must list **3–8 discriminators** (concrete observable differences between preferred and rejected) and every criterion must cite ≥1 discriminator in `cited_discriminators`. Enforced at parse time in `_hydrate`.

Surface area on the `Rubric` / `Criterion` dataclasses:
```python
Rubric.discriminators: list[str]             # top-level, extracted from pairs
Criterion.cited_discriminators: list[str]    # per-criterion, each cites ≥1
```

Supply pairs explicitly with `--reference-pairs pairs.json`:
```json
[{"preferred": "…strong answer…", "rejected": "…weak answer…"}]
```

### Phase 2 — Hard-rule / Principle Taxonomy

**Problem:** OpenRubrics shows that dropping either hard rules (explicit violated-or-not constraints) *or* principles (implicit quality dimensions) costs **~4pp** downstream. Our prior rubrics had no first-class distinction — `ScoringMethod` acted as an implicit proxy.

**Implementation** — `rubric_system/tier_gate.py`:
- New `CriterionTier = {HARD_RULE, PRINCIPLE}` enum on `Criterion.tier` (nullable for backward compat).
- Default mapping from `ScoringMethod` to tier for legacy rows: `BINARY`, `PENALTY_BASED` → `HARD_RULE`; `WEIGHTED_COMPONENTS`, `PERCENTAGE`, `THRESHOLD_TIERS`, `COUNT_BASED` → `PRINCIPLE`. Applied lazily on first access so no migration script is required.
- `evaluate_tier_coverage` enforces **≥2 hard rules AND ≥3 principles**; shortfalls trigger one regeneration retry with tier-specific feedback (`"need 1 more hard_rule"`).
- Prompt update: `RUBRIC_GENERATION_PROMPT` now requires a `tier` field per criterion with explicit definitions and minimums.

### Phase 3 — Preference-Label Consistency Filter (biggest lever)

**Problem:** even a plausible-looking rubric can fail to reproduce the ranking of `preferred > rejected` on held-out pairs. OpenRubrics reports that removing this rejection-sampling step costs **2–3pp** of RM accuracy — it's the single most-impactful gate in the pipeline.

**Implementation** — `rubric_system/consistency.py`:
- `RubricConsistencyValidator` scores preferred and rejected with the existing explicit `ScoringEngine` (same path the rubric will actually be used with) and reports the fraction ranked correctly.
- **Threshold**: `hit_rate ≥ 0.8` (paper's implied bar).
- **Minimum pairs**: 5; below that, status becomes `insufficient_pairs` and the filter is skipped with a warning.
- **Held-out pool**: drawn from `RubricStore` + synthetic fallback, excluding the pairs already used for Phase 1.
- **Bounded retry (N=2)**: on sub-threshold `hit_rate`, misranked pairs are fed back into generation as additional contrast. On the second failure the rubric is marked `failed_accepted` (low-confidence) and the run proceeds.
- **Per-criterion attribution** is computed only on the retry path, identifying which criteria are pushing ranking in the wrong direction. Consumed by the next regeneration prompt.
- **Placement**: between rubric negotiation and the existing QualityGate — so measurability/discrimination fixes see a rubric that already ranks real pairs correctly.
- **Storage**: `Rubric.consistency_hit_rate / consistency_n_pairs / consistency_status / consistency_pair_sources` (nullable, populated when the filter ran).

Approximate cost: ~10 extra scoring calls per run (5 pairs × 2 responses), budgeted via `BudgetTracker`.

### Phase 4 — Scoring Aggregation: Implicit LLM-Judge + Voting@K

**Problem:** explicit per-criterion scoring is auditable and cheap but can miss whole-output quality signals. The paper uses **implicit** aggregation — the judge sees the full rubric + attempt and returns one reward — as a cross-check, with voting@5 for robustness.

**Implementation** — `rubric_system/aggregation.py`:
- `ImplicitAggregator` hands `(task, rubric, attempt)` to a Claude judge (default `claude-sonnet-4-20250514`, configurable with `--judge-model`) and parses `{"total", "per_criterion", "rationale"}`.
- **Voting@K** in `{1, 3, 5}` combined via **median** (robust to outliers) on both total and per-criterion.
- **Authority**: explicit scoring remains the system of record for pass/fail and threshold gating. Implicit is a signal, not a decision.
- **Divergence logging**: when the two aggregators disagree on ranking direction (sign flip on Δpercentage vs previous iteration, or >10pp absolute gap on first iteration), a structured record lands in `~/.auto-verifier-data/phase4_disagreements/disagreements.jsonl` for `self_improve.py` to consume.
- **Budget**: shared `BudgetTracker` caps extra calls at 10/run; voting@K auto-degrades when the remaining budget is smaller than K.

### Phase 5 — Dataset Scaffolding + Privacy Scrubber

**Problem:** OpenRubrics' own result is a *distilled* rubric generator trained on curated `(task, rubric)` pairs. To have that option, we need to start collecting `(task, preferred, rejected, validated_rubric)` tuples now.

**Implementation** — `rubric_system/rubric_learning.py` (new `rubric_dataset` table) + `rubric_system/privacy.py`:
- New table alongside `scored_rubrics`: id, created_at, task_hash, scrubbed task/preferred/rejected text, serialized rubric, consistency hit_rate, tier counts, pair sources, `synthetic_fallback_used` flag, `source_run_id`.
- **Privacy scrubber**: conservative regex redaction for emails, URL-embedded credentials, Anthropic / OpenAI / GitHub / AWS keys, bearer tokens, PEM private-key blocks. Replacements are guaranteed shorter than matches. Applied to task / preferred / rejected text before persistence.
- Opt out with `--no-collect-dataset` if you don't want rows written.
- Distillation mechanics (fine-tuning a dedicated rubric generator) are deferred until **≥1000** validated non-synthetic records accumulate.

### Cross-cutting — Per-Run Telemetry

`rubric_system/telemetry.py` appends one JSONL record per run to `~/.auto-verifier-data/telemetry/runs.jsonl` with pairs used + sources, discriminator count, tier counts, consistency outcome, Phase-4 call-budget usage, dataset save status, final percentage, and all phase flags. Silent-failure so observability never breaks a run. `summarize_runs()` walks the file to compute soak-period metrics (median hit_rate, disagreement totals, phase-flag adoption).

### Eval Validation

On the 5 tasks the harness previously struggled hardest with in Run 12 — all of which *regressed* under the prior pipeline — the aligned pipeline produces large positive deltas (4/5 tasks completed; 5th interrupted):

| Task                         | Run 12 delta | Aligned delta | Aligned harness % |
|------------------------------|-------------:|--------------:|------------------:|
| `ml_experiment_report`       | −5.7pp       | **+70.3pp**   | 93.1%             |
| `graphql_schema_federation`  | −6.1pp       | **+38.4pp**   | 95.6%             |
| `regulatory_gap_analysis`    | −8.7pp       | **+28.9pp**   | 67.1%             |
| `security_threat_model`      | −16.1pp      | **+24.2pp**   | 78.8%             |
| `legal_contract_redline`     | −5.1pp       | _(pending)_   | —                 |

Mean delta across the four completed tasks: **+40.5pp**. Raw baselines dropped (the Phase-2-enforced, Phase-3-filtered rubrics are stricter by design) but the apples-to-apples signal — how much the harness lifts the baseline on *the same rubric* — is the delta column, and it's uniformly positive.

### Opt-out Flags

| Phase | Default | Disable with                |
|-------|---------|-----------------------------|
| 1. Contrastive generation        | on  | `--no-phase1`               |
| 2. Tier taxonomy                 | on  | `--no-phase2`               |
| 3. Consistency filter            | on  | `--no-phase3`               |
| 4. Implicit judge + voting       | on  | `--no-implicit`             |
| 5. Dataset collection            | on  | `--no-collect-dataset`      |

Additional knobs: `--reference-pairs FILE`, `--consistency-threshold 0.8`, `--judge-model <model-id>`, `--voting-k {1,3,5}`.

See [openrubrics-alignment-plan.md](openrubrics-alignment-plan.md) for the full plan with per-phase acceptance criteria, risks, and design rationale.

---

## Eval Results

See [EVAL.md](EVAL.md) for full per-run history.

| Run | Mean Baseline | Mean Harness | Mean Delta | Notes |
|-----|--------------|-------------|------------|-------|
| Run 4 (9 valid tasks)   | 46.9% | 72.9% | **+26.0pp** | pre-multi-pass methodology |
| Run 11 (25 tasks)       | 64.6% | 84.3% | **+19.7pp** | best sample-rubric run |
| Run 12 (22 tasks)       | 68.0% | 74.0% | **+6.1pp**  | first fresh-rubric run; 7 regressions |
| OpenRubrics (4/5 hardest) | 43.3% | 83.7% | **+40.5pp** | Phases 1–5 on; every Run-12 regressor converted to a strong positive delta |

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
