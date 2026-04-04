# Eval Results: Rubric Harness vs. Vanilla Claude

**Generated:** 2026-04-04 19:29:11 UTC  
**Model:** `claude-sonnet-4-20250514`  
**Max harness iterations:** 0

## Per-Task Results

| Task | Domain | Baseline % | Harness % | Delta | Iters | Base Time | Harness Time |
|------|--------|:----------:|:---------:|:-----:|:-----:|:---------:|:------------:|
| cold_outreach_email | cold_outreach_email | 29.1% | 86.4% | +57.3% | 4 | 225s | 2903s |

## Aggregate Statistics

| Metric | Value |
|--------|-------|
| Tasks evaluated | 1 |
| Mean lift | **+57.3%** |
| Median lift | +57.3% |
| Std dev | 0.0% |
| Improved (>1%) | 1/1 |
| Neutral (±1%) | 0/1 |
| Regressed (<-1%) | 0/1 |

## Per-Criterion Lift (top 15 by avg lift across tasks)

| Criterion | Category | Avg Lift | Appearances |
|-----------|----------|:--------:|:-----------:|
| metrics_integrity_and_context | credibility | +100.0% | 1 |
| strategic_investment_thesis | Strategic Depth | +100.0% | 1 |
| business_model_clarity | Business Fundamentals | +100.0% | 1 |
| competitive_differentiation | Market Positioning | +100.0% | 1 |
| investment_rationale_clarity | Investment Logic | +100.0% | 1 |
| social_proof_pathway | trust_building | +100.0% | 1 |
| investment_urgency_articulation | strategic_positioning | +100.0% | 1 |
| unique_value_proposition_clarity | strategic_positioning | +92.5% | 1 |
| operational_depth_sufficiency | business_substance | +92.5% | 1 |
| operational_reality_grounding | Business Authenticity | +85.0% | 1 |
| credibility_anchoring_strategy | positioning | +83.8% | 1 |
| go_to_market_strategy_articulation | strategic_depth | +83.8% | 1 |
| positive_signal_strength | traction | +77.5% | 1 |
| claim_specificity_and_verifiability | credibility | +77.5% | 1 |
| strategic_risk_awareness | founder_maturity | +75.0% | 1 |

## Cost & Token Comparison

| Metric | Baseline | Harness |
|--------|----------|---------|
| Tasks with data | 1 | 1 |
| Total wall time | 225s | 2903s |
| Avg time / task | 225s | 2903s |
| Input tokens (total) | 22 | ~32,000 (est.) |
| Output tokens (total) | 393 | ~6,000 (est.) |
| Est. cost (USD) | $0.0060 | ~$0.1860 (est.) |
| Avg iterations | 1 | 4.0 |

> Harness token/cost figures are estimates based on 8,000 input + 1,500 output tokens per iteration. Actual usage varies.