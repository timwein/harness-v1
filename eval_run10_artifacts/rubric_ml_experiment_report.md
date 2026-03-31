# Rubric: technical_writing

**Task:** Write a reproducible ML experiment report for fine-tuning a language model on domain-specific data, covering dataset construction, training methodology, evaluation metrics, ablation results, and failure analysis

**Domain:** technical_writing
**Total Points:** 56
**Pass Threshold:** 85%
**Criteria Count:** 5
**Generated:** 2026-03-31 06:22:50 UTC

---

## 1. ml_methodology

**Category:** rigor
**Description:** Training methodology is fully specified and reproducible

**Pass Condition:** Specifies: base model, fine-tuning approach (full/LoRA/QLoRA), hyperparameters (LR, batch size, epochs, warmup), hardware, training time, and framework. Enough detail for reproduction.

**Scoring Method:** `weighted_components`
**Max Points:** 14

### Sub-Attributes

| Sub-ID | Weight | Description | Measurement |
|--------|--------|-------------|-------------|
| `completeness` | 35% | All training parameters specified (model, method, hyperparams, hardware) | % of required training details specified |
| `method_justification` | 30% | Explains why this fine-tuning approach was chosen | 1.0 if justified vs alternatives, 0.5 if mentioned, 0.0 if just stated |
| `reproducibility` | 35% | Could someone reproduce this from the report alone? | 1.0 if fully reproducible, 0.5 if mostly, 0.0 if missing key details |

### Pass Examples

- Base: Llama-3-8B, Method: QLoRA (r=64, alpha=128, target: q_proj,v_proj), LR: 2e-4 cosine, Batch: 8 (gradient accumulation 4), 3 epochs, A100 80GB x2, ~4.5 hours

### Fail Examples

- 'We fine-tuned a large language model on our data'

---

## 2. ml_dataset

**Category:** data
**Description:** Dataset construction is documented with quality controls and statistics

**Pass Condition:** Source, size, splits (train/val/test), preprocessing steps, quality filters, distribution analysis, contamination checks. Includes dataset statistics table.

**Scoring Method:** `weighted_components`
**Max Points:** 12

### Sub-Attributes

| Sub-ID | Weight | Description | Measurement |
|--------|--------|-------------|-------------|
| `construction` | 30% | Source data, collection method, preprocessing pipeline documented | % of pipeline steps documented |
| `statistics` | 30% | Size, splits, distribution metrics, class balance | 1.0 if comprehensive stats, 0.5 if basic counts, 0.0 if none |
| `quality_controls` | 25% | Dedup, filtering, contamination checks described | 1.0 if quality pipeline, 0.5 if basic filters, 0.0 if no quality control |
| `contamination_check` | 15% | Checks for test set leakage into training data | 1.0 if explicit contamination check, 0.0 if not addressed |

### Pass Examples

- 12,400 examples (10K train / 1.2K val / 1.2K test), sourced from internal docs. Deduped via MinHash (3.2% removed). N-gram contamination check against test set: 0 matches.

### Fail Examples

- 'We used our company's data for training'

---

## 3. ml_evaluation

**Category:** measurement
**Description:** Evaluation uses multiple metrics with proper baselines and statistical significance

**Pass Condition:** Multiple metrics (not just loss). Task-specific evaluation (not just perplexity). Comparison against base model and at least one other baseline. Confidence intervals or significance tests.

**Scoring Method:** `weighted_components`
**Max Points:** 12

### Sub-Attributes

| Sub-ID | Weight | Description | Measurement |
|--------|--------|-------------|-------------|
| `metric_diversity` | 30% | Multiple relevant metrics (accuracy, F1, BLEU, human eval, etc.) | 1.0 if 3+ relevant metrics, 0.5 if 1-2, 0.0 if loss only |
| `baseline_comparison` | 30% | Results compared to base model + at least one other baseline | 1.0 if 2+ baselines, 0.5 if base model only, 0.0 if no comparison |
| `statistical_rigor` | 20% | Confidence intervals, multiple runs, or significance tests | 1.0 if CI or significance test, 0.5 if multiple runs, 0.0 if single run |
| `task_specific_eval` | 20% | Evaluation on downstream task, not just language modeling metrics | 1.0 if task-specific, 0.5 if mixed, 0.0 if perplexity only |

### Pass Examples

- Domain QA accuracy: 78.3% (CI: 76.1-80.5) vs base model 52.1% vs GPT-4 71.4%. 3 runs, std dev reported.

### Fail Examples

- 'The model achieved good performance' or just reporting training loss

---

## 4. ml_ablation

**Category:** analysis
**Description:** Ablation study isolates the contribution of key design decisions

**Pass Condition:** At least 3 ablations (e.g., dataset size, LoRA rank, base model, data mix). Each ablation changes one variable. Results in table format. Conclusions drawn from ablation results.

**Scoring Method:** `weighted_components`
**Max Points:** 10

### Sub-Attributes

| Sub-ID | Weight | Description | Measurement |
|--------|--------|-------------|-------------|
| `ablation_count` | 30% | At least 3 meaningful ablations | 1.0 if 3+, 0.5 if 1-2, 0.0 if none |
| `controlled_variables` | 30% | Each ablation changes exactly one variable | 1.0 if controlled, 0.5 if mostly, 0.0 if confounded |
| `insights` | 40% | Ablation results lead to actionable conclusions | 1.0 if clear insights (e.g., 'LoRA r=64 matches full FT at 1/3 cost'), 0.0 if just numbers |

### Pass Examples

- Ablation table: LoRA rank (16/32/64/128) → accuracy saturates at r=64, r=128 adds compute cost with no quality gain

### Fail Examples

- No ablations, or ablating multiple variables simultaneously

---

## 5. ml_failure_analysis

**Category:** honesty
**Description:** Failure analysis identifies what doesn't work and why, with concrete examples

**Pass Condition:** Identifies specific failure modes with examples. Categorizes failures (hallucination, format, knowledge gap). Quantifies failure rates. Proposes concrete next steps.

**Scoring Method:** `weighted_components`
**Max Points:** 8

### Sub-Attributes

| Sub-ID | Weight | Description | Measurement |
|--------|--------|-------------|-------------|
| `failure_identification` | 35% | Specific failure modes identified with examples | 1.0 if categorized failures with examples, 0.5 if mentioned, 0.0 if absent |
| `quantification` | 30% | Failure rates quantified (e.g., 12% hallucination rate on X) | 1.0 if quantified, 0.5 if qualitative, 0.0 if not addressed |
| `next_steps` | 35% | Concrete proposed improvements based on failure analysis | 1.0 if specific improvements tied to failures, 0.5 if generic, 0.0 if absent |

### Pass Examples

- Failure mode 1: Hallucinated entity names in 12% of responses (23/192 test examples). Root cause: training data skew toward entity-heavy documents. Proposed fix: entity-masking augmentation.

### Fail Examples

- 'The model sometimes makes mistakes' with no analysis

---
