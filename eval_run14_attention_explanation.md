# Eval Results: Rubric Harness vs. Vanilla Claude

**Generated:** 2026-04-04 19:41:01 UTC  
**Model:** `claude-sonnet-4-20250514`  
**Max harness iterations:** 0

## Per-Task Results

| Task | Domain | Baseline % | Harness % | Delta | Iters | Base Time | Harness Time |
|------|--------|:----------:|:---------:|:-----:|:-----:|:---------:|:------------:|
| attention_explanation | explanation | 36.2% | 74.5% | +38.3% | 5 | 205s | 3899s |

## Aggregate Statistics

| Metric | Value |
|--------|-------|
| Tasks evaluated | 1 |
| Mean lift | **+38.3%** |
| Median lift | +38.3% |
| Std dev | 0.0% |
| Improved (>1%) | 1/1 |
| Neutral (±1%) | 0/1 |
| Regressed (<-1%) | 0/1 |

## Per-Criterion Lift (top 15 by avg lift across tasks)

| Criterion | Category | Avg Lift | Appearances |
|-----------|----------|:--------:|:-----------:|
| query_key_asymmetry_understanding | Conceptual Misconception Prevention | +85.0% | 1 |
| active_learning_engagement | pedagogical_effectiveness | +82.5% | 1 |
| computational_walkthrough_completeness | practical_understanding | +75.0% | 1 |
| attention_impact_demonstration | mechanistic_understanding | +62.5% | 1 |
| prerequisite_knowledge_scaffolding | foundation_building | +57.5% | 1 |
| mathematical_intuition_depth | conceptual_understanding | +57.5% | 1 |
| conceptual_bridge_construction | Conceptual Progression & Scaffolding | +56.2% | 1 |
| attention_type_distinctions | Mathematical Accuracy & Precision | +52.5% | 1 |
| age_appropriate_comprehension_depth | pedagogical_effectiveness | +42.5% | 1 |
| progressive_complexity_alignment | Cross-Cutting Coherence | +25.0% | 1 |
| foundation_building | Foundation for Advanced Learning | +25.0% | 1 |
| intuitive_scaffolding_progression | pedagogical_effectiveness | +22.5% | 1 |
| explanation_mathematical_coherence | Cross-Cutting Coherence | +22.5% | 1 |
| computation_chain_accuracy | Mathematical Accuracy & Precision | +18.0% | 1 |
| analogy_completeness_coherence | conceptual_clarity | +17.5% | 1 |

## Cost & Token Comparison

| Metric | Baseline | Harness |
|--------|----------|---------|
| Tasks with data | 1 | 1 |
| Total wall time | 205s | 3899s |
| Avg time / task | 205s | 3899s |
| Input tokens (total) | 21 | ~40,000 (est.) |
| Output tokens (total) | 792 | ~7,500 (est.) |
| Est. cost (USD) | $0.0119 | ~$0.2325 (est.) |
| Avg iterations | 1 | 5.0 |

> Harness token/cost figures are estimates based on 8,000 input + 1,500 output tokens per iteration. Actual usage varies.