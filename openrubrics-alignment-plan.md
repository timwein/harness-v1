# OpenRubrics Alignment Plan

Plan to bring `rubric_system/` closer to the rigor of OpenRubrics (Liu et al., arXiv 2510.07743), staged across five phases. Paper-inspired, adapted to our codebase — not a literal reimplementation.

Branch: `claude/clarify-account-usage-qagCz`. Deliverable is this plan only; no code changes in this pass.

---

## Table of contents

1. OpenRubrics in one page
2. Current state of `rubric_system/`
3. Design decisions (locked)
4. Phase 1 — Contrastive Rubric Generation
5. Phase 2 — Hard-rule / Principle taxonomy
6. Phase 3 — Preference-label consistency filter
7. Phase 4 — Scoring aggregation (implicit + voting)
8. Phase 5 — Dataset building
9. Cross-cutting concerns
10. Sequencing, dependencies, and acceptance
11. Risks and open questions

---

## 1. OpenRubrics in one page

- **Contrastive Rubric Generation (CRG).** A rubric is generated conditioned on `(prompt, preferred, rejected)` from an existing preference dataset. Real outcome signal, not imagined contrasts.
- **Two-tier criterion taxonomy.**
  - *Hard rules* — explicit, pass/fail constraints (format, length, required entities, no-hallucination). Cut verbosity bias and fabricated-citation failures.
  - *Principles* — implicit qualities (nuance, calibration, reasoning depth) that generalize across tasks.
- **Preference-label consistency filter.** Every generated rubric is tested: applied to the source `(preferred, rejected)`, does it reproduce `preferred > rejected`? Rubrics that fail are rejection-sampled out. Removing this filter drops RM accuracy ~2–3 pts.
- **Aggregation.** Explicit (per-criterion score, weight-sum, normalize) or implicit (LLM judge on full rubric). Voting@5 on implicit judging adds robustness.
- **Ablations.** No filter → −2–3 pts RM accuracy. No hard rules *or* no principles → −4 pts downstream. No-SFT prompt→rubric→judge baseline peaks at 58.9%. Full Rubric-RM beats size-matched 7B baselines by +6.8–8.4%.

## 2. Current state of `rubric_system/`

| Capability | Paper | Us |
| --- | --- | --- |
| Contrastive conditioning at generation | Yes (CRG) | **No** — `RUBRIC_GENERATION_PROMPT` at `rubric_system/rubric_harness.py:3161` conditions only on task + web research + learning context. Near-misses exist at line 3226 but are imagined, not extracted from real pairs. |
| Hard rules / principles split | Yes, first-class | **No** — `ScoringMethod` at `rubric_system/scoring_engine.py:207` is a rough proxy (penalty≈hard rule, weighted≈principle), with no enforcement. |
| Preference-label consistency filter | Yes — the single most-impactful gate | **No** — `QualityGate` enforces discriminative power / redundancy / measurability; `RegressionSuite` protects self-edits. Neither checks pair ranking. |
| Learning signal | Dense — preference pairs | Sparse — git/CI outcome tracking (`rubric_system/models.py:190-231`, `rubric_system/rubric_learning.py:30-82`). Valuable but slow. |
| Aggregation | Explicit + implicit + voting@5 | Explicit only (`ScoringEngine.score_criterion`). |
| Rubric generator | SFT'd on curated corpus | Prompted `claude-sonnet-4-20250514` only. |
| Contrast surface | From real data | `Criterion.pass_examples` / `fail_examples` at `rubric_system/models.py:94-95` — author-imagined. |

## 3. Design decisions (locked)

Captured from clarification rounds.

**Scope & rollout**
- Deliverable: this plan document. Development continues on `claude/clarify-account-usage-qagCz`.
- Framing: paper-inspired, adapted to our design.
- Rollout: phase-gated flags; each phase flips default-on after a soak of ≥20 runs with clean telemetry.
- Backward compat: add nullable columns to `RubricStore`, lazy-fill on use. No one-shot migration.

**Pair sourcing (Phase 1)**
- All four sources supported: caller-supplied, RubricStore-mined, self-contrast, synthetic.
- Priority (highest first): **caller > store > self-contrast > synthetic**.
- Pair budget per generation: **up to 3**.
- Prompt: single unified template with an optional pair block.
- Discriminators: top-level field on `Rubric`, each criterion must cite ≥1 in `research_basis`.
- Self-contrast: N=3 provisional attempts, take top vs bottom as the pair.
- Synthetic pairs: 3 pairs produced in one generator-model call.

**Taxonomy (Phase 2)**
- Add `CriterionTier = {hard_rule, principle}` to `models.py`.
- Legacy mapping: `BINARY` + `PENALTY_BASED` → `hard_rule`; everything else → `principle`.
- Auto-tag existing criteria by scoring method, re-tag on regeneration.
- Minimums for QualityGate: **≥2 hard rules AND ≥3 principles**.
- Single-tier rubrics are rejected and regenerated with tier-specific feedback.

**Consistency filter (Phase 3)**
- Held-out pair source: RubricStore; synthetic fallback when empty.
- Minimum pairs before filter runs: **≥5**; below, skip and log `insufficient_pairs`.
- Threshold: `hit_rate ≥ 0.8`.
- Check aggregator: the existing explicit `ScoringEngine` (cheap, deterministic, matches runtime).
- Failure action: **bounded retry (N=2) then warn-and-proceed**, flagging the rubric low-confidence.
- Granularity: whole-rubric by default; per-criterion attribution computed only when a retry is triggered.
- Placement in loop: **after Rubric Negotiation, before Quality Gate** (`rubric_harness.py:7920-7936`).
- Outcome stored first-class on `Rubric`: `consistency_hit_rate`, `consistency_n_pairs`, `consistency_status`.

**Aggregation (Phase 4)**
- Add `ImplicitAggregator` LLM-judge path; judge model is `--judge-model` configurable (default `claude-sonnet-4-20250514`).
- Voting@K: **K=3**, opt-in via `--voting-k`.
- Tiebreak on explicit/implicit divergence: **explicit wins**; disagreement is logged for `self_improve.py`.
- Extra-call budget: **≤ +10 calls/run**; over-budget emits a warning and skips the next optional extra call.

**Dataset (Phase 5)**
- Storage: new table in existing `RubricStore` SQLite.
- Collection: **opt-in per run** via `--collect-dataset`.
- Privacy: hash task text + regex-scrub obvious PII (emails, tokens, keys) from responses before persistence.
- Distillation mechanics deferred until **≥1000** validated records accumulate.

**Testing & observability**
- Unit tests per component + one deterministic end-to-end canned task per phase.
- Per-run telemetry: `pairs_used`, `pairs_source`, `discriminators_count`, `tier_counts`, `consistency_hit_rate`, `consistency_n_pairs`, `retries_triggered`, `aggregator_disagreements`, `extra_calls`.

---

## 4. Phase 1 — Contrastive Rubric Generation

Goal: stop imagining contrasts and start generating rubrics conditioned on real `(preferred, rejected)` pairs. This is the low-risk, high-ROI entry point that every later phase feeds off.

### 4.1 Data model changes

- `rubric_system/models.py`
  - Add `PairSource = Enum("caller", "store", "self_contrast", "synthetic")`.
  - Add `ReferencePair` dataclass: `task_hash: str`, `preferred: str`, `rejected: str`, `source: PairSource`, `provenance: dict` (run id, timestamp, outcome labels).
  - Add `Rubric.discriminators: list[str]` — distinguishing features extracted from pairs before criteria are emitted.
  - Add `Criterion.cited_discriminators: list[str]` — indices/slugs into `Rubric.discriminators`. Each criterion must cite ≥1 when pairs were used; unenforced when `reference_pairs` is empty.
  - All new fields nullable / default-empty for backward compat.

### 4.2 Control flow

- `RubricLoop.run(..., reference_pairs: list[ReferencePair] | None = None)`.
- If `reference_pairs` is `None`, invoke `ReferencePairResolver.resolve(task)`:
  1. Caller-supplied (none in this path — early exit).
  2. `RubricStore.mine_pairs(task, k=3)` using existing `pass_then_success` vs `pass_then_bug` outcomes from `rubric_system/rubric_learning.py:30-82` on the same or near-duplicate task hash.
  3. If <3 pairs: run self-contrast — generate 3 provisional attempts against a stub rubric, score with current `ScoringEngine`, take top vs bottom as one pair.
  4. If still <3: single generator-model call asks for 3 synthetic `(preferred, rejected)` pairs seeded with the task text.
  5. Cap at 3 pairs, tag each with its `source`.
- Feed resolved pairs into the unified generation prompt.

### 4.3 Prompt strategy

Single `RUBRIC_GENERATION_PROMPT` in `rubric_harness.py:3161`, extended with an optional block rendered only when `reference_pairs` is non-empty. Sketch:

```
[existing preamble...]

## Reference pairs (up to 3)
For each pair, a PREFERRED response is better than a REJECTED response for this task.
Before writing criteria:
  (a) List 3–8 discriminators — concrete, observable differences that make
      PREFERRED better than REJECTED.
  (b) Each criterion you emit MUST cite at least one discriminator in
      `research_basis` and populate `cited_discriminators`.

Pair 1 [source: {source}]
  PREFERRED:
  {preferred}
  REJECTED:
  {rejected}
...

[existing output-format instructions, extended with discriminators + cited_discriminators fields]
```

When no pairs are available, the block is omitted and behavior matches today.

### 4.4 New files / modules

- `rubric_system/reference_pairs.py` — `ReferencePairResolver`, `SelfContrastSampler`, `SyntheticPairSynthesizer`, `mine_pairs` query.
- No new top-level script.

### 4.5 Acceptance criteria

- With `reference_pairs` supplied: generator output contains ≥3 discriminators and every criterion cites ≥1. Fail-closed: `QualityGate` rejects rubrics that violate this when pairs were used.
- With no pairs available: run behavior is byte-identical to current main (golden-file test).
- Telemetry records `pairs_used`, `pairs_source`, `discriminators_count`, and source mix per run.

### 4.6 Risks

- Self-contrast can amplify whatever bias the provisional rubric already has. Mitigation: provisional rubric is a minimal template-only rubric, not a negotiated one; self-contrast is the third-choice source, not the first.
- Synthetic pairs risk self-reinforcement of model priors. Mitigation: tag synthetic clearly so downstream (Phase 3, Phase 5) can filter or de-weight them.

## 5. Phase 2 — Hard-rule / Principle taxonomy

Goal: make the two-tier split first-class so both tiers are present, enforced, and separately ablatable. The paper's −4 pt downstream regression when either tier is dropped justifies treating this as a gate, not a suggestion.

### 5.1 Data model changes

- `rubric_system/models.py`
  - `CriterionTier = Enum("hard_rule", "principle")`.
  - `Criterion.tier: CriterionTier | None` — nullable, lazy-filled on next touch for legacy rows.
- Default mapping for legacy / untagged criteria:
  - `BINARY`, `PENALTY_BASED` → `hard_rule`.
  - `PERCENTAGE`, `WEIGHTED_COMPONENTS`, `THRESHOLD_TIERS`, `COUNT_BASED` → `principle`.

### 5.2 Prompt changes

`RUBRIC_GENERATION_PROMPT` in `rubric_harness.py:3161` is extended with:

- Explicit definitions of hard rules vs principles.
- A minimums contract: `≥2 hard rules AND ≥3 principles`.
- Each emitted criterion must include `tier` in its JSON.
- Hard-rule criteria must be violated-or-not (binary or penalty-based); principles must be graded.

### 5.3 Quality gate changes

Add two new checks to `QualityGate`:

1. `tier_coverage` — rejects rubrics with <2 hard rules or <3 principles.
2. `tier_consistency` — rejects rubrics where a criterion's declared `tier` disagrees with the default mapping of its `scoring_method` (soft, warn-only on the first build; harden after soak).

Rejections feed back into the negotiation loop with tier-specific feedback (e.g. `"need 1 more hard rule — currently 1 of 2"`).

### 5.4 Migration

- On first touch (read or re-score) of a legacy criterion whose `tier is None`, back-fill via the default mapping.
- On any regeneration, the generator emits `tier` directly and the mapping is bypassed.

### 5.5 Acceptance criteria

- Any new rubric passing `QualityGate` has `≥2 hard_rule` and `≥3 principle` criteria.
- A rubric regenerated from a legacy version preserves prior tier assignments unless the generator deliberately re-classifies.
- Telemetry emits `tier_counts` per run.

### 5.6 Risks

- Over-constraining small tasks where 2+3 is overkill. Mitigation: log `tier_minimums_forced_regeneration_count`; if this fires on >20% of runs during soak, revisit minimums before flipping default-on.
- Tier mis-assignment from the generator. Mitigation: the `tier_consistency` soft check surfaces disagreements; post-soak analysis decides whether to harden.

## 6. Phase 3 — Preference-label consistency filter

Goal: the single most-impactful gate in the paper. Before a rubric is allowed to score real attempts, prove it can reproduce `preferred > rejected` on held-out pairs.

### 6.1 New component

`rubric_system/consistency.py`

```python
@dataclass
class ConsistencyResult:
    hit_rate: float           # fraction of pairs where preferred_score > rejected_score
    n_pairs: int              # number of held-out pairs actually used
    status: Literal["passed", "failed", "insufficient_pairs", "skipped"]
    per_pair: list[PairResult]            # pair_id, preferred_score, rejected_score, ranked_correctly
    per_criterion: dict[str, float] | None  # populated only on retry

class RubricConsistencyValidator:
    threshold: float = 0.8
    min_pairs: int = 5

    def validate(self, rubric: Rubric, held_out: list[ReferencePair]) -> ConsistencyResult: ...
    def attribute(self, rubric: Rubric, failing_pairs: list[ReferencePair]) -> dict[str, float]:
        # per-criterion contribution to misranking; only called on retry
```

### 6.2 Held-out pair sourcing

- Primary: mine from `RubricStore` using the same pass/bug outcomes exposed in `rubric_system/rubric_learning.py:30-82`, excluding any pair already used as a Phase 1 reference for this run.
- Fallback: synthetic pairs from one generator-model call, tagged `source="synthetic"`. Synthetic pairs are flagged in the stored result so self_improve can treat synthetic-validated rubrics as lower-confidence.
- If fewer than 5 pairs are obtainable across both sources: `status = "insufficient_pairs"`, skip the filter, log a warning, continue to Quality Gate.

### 6.3 Placement in the loop

Between Rubric Negotiation and Quality Gate (`rubric_harness.py:7920-7936`):

```
negotiate → consistency_filter → quality_gate → scoring_engine
```

Failure paths:

- `hit_rate < threshold`: trigger bounded retry.
- `insufficient_pairs`: record and continue. QG still runs.
- Validator errors (e.g. pair scoring exception): record as `status="errored"`; rubric is flagged low-confidence but passes through. No retry on errors to avoid loops.

### 6.4 Bounded retry (N=2)

On sub-threshold `hit_rate`:

1. Compute `attribute(rubric, failing_pairs)` to produce per-criterion misranking contribution.
2. Re-enter generation with the failing pairs added to `reference_pairs` (still capped at 3) plus a feedback block listing the top-contributing criteria and the discriminators they missed.
3. Re-run `validate`.
4. On second failure, mark the rubric `consistency_status="failed_accepted"`, emit a warning, and proceed. Store the `hit_rate` and `n_pairs` on the `Rubric` record for `self_improve.py` to consume.

### 6.5 Scoring inside the check

- Use the existing explicit `ScoringEngine`. Cheap, deterministic, and — critically — matches how the rubric will be used downstream, so the filter isn't measuring a different system than the one we deploy.
- The implicit-judge aggregator introduced in Phase 4 is *not* used here. That choice is deliberate: it would double the cost of the filter and couple it to the noisier path.

### 6.6 Storage

New nullable columns on the `Rubric` row:

- `consistency_hit_rate: float | None`
- `consistency_n_pairs: int | None`
- `consistency_status: str | None` — one of `passed`, `failed_accepted`, `insufficient_pairs`, `skipped`, `errored`.
- `consistency_pair_sources: str | None` — comma-joined `PairSource` names actually used.

Per-pair detail goes to an audit log (`.rubric_feedback/consistency/*.jsonl`), not the main store, to keep the hot path queryable.

### 6.7 Acceptance criteria

- On a canned task with 6 seeded pairs (3 clear winners, 3 clear losers): validator returns `hit_rate == 1.0`, `status == "passed"`.
- On a canned task where the provisional rubric ranks backwards on 2/6 pairs: validator returns `hit_rate == 0.67`, `status == "failed"`, bounded retry fires, final rubric passes or records `failed_accepted` after N=2.
- Filter adds no more than ~10 scoring calls on the median run (5 pairs × 2 responses = 10).

### 6.8 Risks

- Synthetic-pair fallback can self-reinforce the generator's biases. Mitigation: synthetic-validated rubrics are tagged; Phase 5 excludes them from the distillation dataset unless explicitly allowlisted.
- Explicit scoring inside the filter means a rubric with a dominant high-weight criterion can ride that criterion to `hit_rate ≥ 0.8` while other criteria are noisy. Mitigation: the per-criterion attribution computed on retry surfaces this, and `self_improve.py` can flag rubrics with a single-criterion signal-to-total ratio > 0.8.

## 7. Phase 4 — Scoring aggregation (implicit + voting)

Goal: add the paper's implicit LLM-judge path as a cross-check on the explicit aggregator. Keep explicit as the system of record; use implicit for divergence detection and (opt-in) higher-stakes evaluations.

### 7.1 New component

`rubric_system/aggregation.py`

```python
class ImplicitAggregator:
    def __init__(self, judge_model: str, voting_k: int = 1): ...

    def score(self, rubric: Rubric, attempt: str) -> AggregatedScore:
        # Voting@K:
        #   K=1 → single judge call, returned as-is.
        #   K>1 → K independent samples; majority vote on ranking, median on numeric reward.
        ...

@dataclass
class AggregatedScore:
    total: float
    per_criterion: dict[str, float]
    judge_trajectories: list[str]  # K raw outputs, for audit
```

### 7.2 Integration

- `ScoringEngine.score_attempt` returns both an `explicit: AggregatedScore` and an optional `implicit: AggregatedScore | None`.
- The explicit score remains authoritative (decisions, threshold gating, quality gate comparisons).
- When both are present and their attempt rankings disagree (explicit says A > B, implicit says B > A): log `aggregator_disagreement` with both scores, top-contributing criteria from explicit, and the judge trajectory(ies). No automated override.
- `self_improve.py` gets a new hook to read disagreement logs and flag rubrics whose explicit/implicit agreement is consistently low.

### 7.3 Configuration

- New CLI flags on `rubric_harness.py`:
  - `--judge-model <model-id>` — default `claude-sonnet-4-20250514`.
  - `--voting-k {1,3,5}` — default `1`.
  - `--enable-implicit` — off by default; turns on the implicit aggregator path.
- Budget enforcement:
  - Per-run extra-call cap: **10** (consistency filter ≈ 10 scoring calls max; implicit judge consumes from the same budget).
  - If the next optional call would exceed the cap, skip it, emit `extra_calls_budget_exceeded`, and continue.

### 7.4 Acceptance criteria

- On a canned task where explicit and implicit agree: both scores recorded, `aggregator_disagreement` not emitted.
- On a canned task engineered to disagree: explicit decision is used, disagreement is logged with full judge trajectory(ies).
- Voting@3 reduces per-run variance on a fixed attempt by ≥30% vs K=1 (acceptance measured on a repeatable seeded attempt).
- Total extra calls per run stay ≤10 on the median run; warnings fire when exceeded.

### 7.5 Risks

- Judge prompt drift: implicit judgments are sensitive to prompt phrasing. Mitigation: keep the judge prompt versioned and snapshot-tested.
- Cost creep when `--enable-implicit` becomes default-on. Mitigation: voting@K stays opt-in even post-soak until cost data supports the flip.

## 8. Phase 5 — Dataset building

Goal: accumulate `(task, preferred, rejected, validated_rubric)` tuples so that eventually a domain-specific rubric generator can be distilled — OpenRubrics' play, scaled to our use case. No distillation work in this phase; scaffolding only.

### 8.1 Storage

New table in the existing `RubricStore` SQLite DB (no new file / service):

```sql
CREATE TABLE IF NOT EXISTS rubric_dataset (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    task_hash TEXT NOT NULL,
    task_text TEXT NOT NULL,          -- scrubbed
    preferred TEXT NOT NULL,          -- scrubbed
    rejected TEXT NOT NULL,           -- scrubbed
    rubric_json TEXT NOT NULL,        -- full serialized Rubric
    rubric_consistency_hit_rate REAL,
    rubric_tier_counts TEXT,          -- json {"hard_rule": N, "principle": M}
    pair_sources TEXT,                -- comma-joined PairSource
    synthetic_fallback_used INTEGER NOT NULL DEFAULT 0,
    source_run_id TEXT
);
CREATE INDEX IF NOT EXISTS idx_rubric_dataset_task_hash ON rubric_dataset(task_hash);
```

### 8.2 Collection policy

- Opt-in per run via `--collect-dataset`.
- Only rubrics that passed QualityGate *and* the consistency filter (or `insufficient_pairs` with a manual `--allow-unvalidated` override) are eligible.
- Synthetic-only-validated rubrics are written but flagged with `synthetic_fallback_used=1` so they can be filtered at training time.

### 8.3 Privacy

- `task_hash` = SHA-256 of the raw task string.
- Regex scrubber runs over `task_text`, `preferred`, `rejected` before persistence: emails, URLs with secrets, AWS/GCP/Anthropic key patterns, bearer tokens, `BEGIN ... KEY` blocks.
- Scrubber is a small standalone module (`rubric_system/privacy.py`) with unit tests for each pattern.

### 8.4 Distillation gate

- Defer distillation mechanics until **≥1000** validated, non-synthetic records are in the table.
- Emit a log line on every run with current `rubric_dataset` count (once per run, not per record).
- At ≥1000: revisit format choice (SQLite → HF datasets export), model choice, and training harness. Not in scope for this plan.

### 8.5 Acceptance criteria

- `--collect-dataset` off → no writes to `rubric_dataset`.
- `--collect-dataset` on + clean run → one row written, scrubbed fields verified against originals.
- Scrubber unit tests cover each pattern; fuzz test ensures scrubbed output is always shorter or equal, never longer.
- Count log appears exactly once per run when collection is on.

### 8.6 Risks

- SQLite write contention under parallel runs. Mitigation: existing `RubricStore` already handles concurrent access; reuse its connection/lock discipline.
- Over-aggressive scrubbing strips legitimate content. Mitigation: capture raw-length vs scrubbed-length metrics and sample-review.

## 9. Cross-cutting concerns

### 9.1 Rollout

- Every phase ships behind a `--phase-N` flag, default-off at merge.
- Phase flips default-on once telemetry shows **≥20 runs** with no regression on:
  - downstream outcome rates (`pass_then_success` vs `pass_then_bug`),
  - QualityGate pass rate,
  - per-run extra-call count,
  - aggregator disagreement rate.
- The flip itself is a one-line defaults change; the old behavior remains available via `--no-phase-N`.

### 9.2 Migration

- All new columns and fields are nullable with sensible defaults.
- No one-shot migration script. Legacy rows back-fill lazily on next touch:
  - Phase 2: `tier` is derived from `scoring_method` on first read.
  - Phase 3: `consistency_*` remain `NULL` until a rubric is next validated.
  - Phase 5: only new rows are written to `rubric_dataset`; the old store is untouched.
- `RubricStore` bumps its internal schema-version constant and adds columns with `ALTER TABLE ... ADD COLUMN` on startup when missing.

### 9.3 Telemetry

Every run emits a structured record (JSONL, append to `.rubric_feedback/telemetry/`) with, at minimum:

- `run_id`, `task_hash`, `phase_flags`.
- `pairs_used`, `pairs_source`, `discriminators_count`.
- `tier_counts`, `tier_minimums_forced_regeneration_count`.
- `consistency_hit_rate`, `consistency_n_pairs`, `consistency_status`, `consistency_retries`.
- `aggregator_disagreements`, `voting_k`.
- `extra_calls`, `extra_calls_budget_exceeded`.
- `rubric_id`, `final_outcome`.

`self_improve.py` reads this log in addition to `OutcomeTracker` for richer signals.

### 9.4 Testing

- **Unit tests** (per component):
  - `ReferencePairResolver` priority ordering and fallback behavior.
  - Synthetic pair parser (malformed model output).
  - `CriterionTier` auto-tagger mapping.
  - `RubricConsistencyValidator.validate` with synthesized `ScoringEngine` stubs.
  - `ImplicitAggregator` voting math and tie-handling.
  - Privacy scrubber patterns.
- **End-to-end canned task** per phase:
  - Phase 1: task with caller-supplied pairs → assert discriminators present + cited.
  - Phase 2: task forcing tier-minimum violations → assert regeneration is triggered.
  - Phase 3: task with seeded backwards-ranking pairs → assert retry + final status.
  - Phase 4: seeded disagreement → assert explicit decision + logged disagreement.
  - Phase 5: collection on/off → assert row counts.
- Golden-file test: empty-pair run produces byte-identical output to current `main`. Enforced for every phase until Phase 2's mandatory `tier` field breaks it (at which point the golden is regenerated and recorded in the PR).

### 9.5 Observability checks post-soak

After each phase accumulates ≥20 runs:

- Plot `consistency_hit_rate` distribution; median should sit comfortably above 0.8.
- Plot `tier_counts` — a bimodal or degenerate distribution suggests over-enforcement.
- Plot `aggregator_disagreement_rate` — a spike after Phase 4 lands is expected; a sustained high rate past soak is a signal that one aggregator is miscalibrated.

## 10. Sequencing, dependencies, and acceptance

Order: **1 → 3 → 2 → 4 → 5**.

- Phase 1 unlocks the ability to feed pairs forward. Small, low-risk, immediate uplift.
- Phase 3 is sequenced next because it's the single highest-impact gate and feeds directly off Phase 1's pair plumbing; every retry is itself a Phase 1 regeneration.
- Phase 2 after both because the tier taxonomy compounds with contrastive pairs (hard rules tend to be the most discriminator-rich), and QG tier checks are cheap to add once the loop is stable.
- Phase 4 multiplies the value of 1–3 by adding a cross-check on their outputs. Without 1–3 it's a noisier single-model judge.
- Phase 5 is the long-horizon play; it rides on the data flywheel created by 1–4 and only becomes valuable at scale.

Acceptance for the overall alignment effort (measured on our evaluation harness, post-soak across all five phases):

- ≥10% absolute reduction in `pass_then_bug` rate vs current main on a frozen task set.
- Median `consistency_hit_rate` ≥ 0.85 across runs that had sufficient pairs.
- Phase flags stable at default-on with no production-incident rollbacks for ≥30 days.

## 11. Risks and open questions

### Accepted risks

- Synthetic-only validation creates a feedback loop; tagging + Phase 5 exclusion manages it but doesn't eliminate it.
- Pair mining from `RubricStore` presumes reasonably consistent task hashing; near-duplicate detection may drift on paraphrases. Conservative: exact-hash only in v1; fuzzy-match is a follow-up.
- Explicit scoring inside the consistency filter privileges rubrics that score like the runtime scorer — which is the point, but it closes off the possibility of catching runtime-scorer miscalibrations via the filter.

### Open questions (to revisit after Phase 1 lands)

- Should `ReferencePair.provenance` include attempt iteration index so self_improve can reason about *when* in a run a preferred response emerged?
- Is the +10 call/run cap tight enough once Phase 4 is default-on with voting? Needs real-run data before deciding.
- Does `RubricStore` need partitioning by task domain before Phase 5 distillation? Only answerable at ~1k records.

### Deferred (explicit non-goals for this plan)

- Fine-tuning our own rubric generator (Phase 5 gate: ≥1000 validated records).
- Fine-tuning a dedicated judge model. Sonnet as the judge is good enough for the agreement-check use case.
- Integrating external preference datasets (HH-RLHF, UltraFeedback). Our own run history is the first-class source.
- Fuzzy / semantic task-hash matching for pair mining.





