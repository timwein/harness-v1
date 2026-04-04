# Eval Results: Rubric Harness vs. Vanilla Claude

**Generated:** 2026-04-04 19:53:13 UTC  
**Model:** `claude-sonnet-4-20250514`  
**Max harness iterations:** 0

## Per-Task Results

| Task | Domain | Baseline % | Harness % | Delta | Iters | Base Time | Harness Time |
|------|--------|:----------:|:---------:|:-----:|:-----:|:---------:|:------------:|
| startup_naming | creative_naming | 42.8% | 66.1% | +23.3% | 7 | 234s | 4573s |

## Aggregate Statistics

| Metric | Value |
|--------|-------|
| Tasks evaluated | 1 |
| Mean lift | **+23.3%** |
| Median lift | +23.3% |
| Std dev | 0.0% |
| Improved (>1%) | 1/1 |
| Neutral (±1%) | 0/1 |
| Regressed (<-1%) | 0/1 |

## Per-Criterion Lift (top 15 by avg lift across tasks)

| Criterion | Category | Avg Lift | Appearances |
|-----------|----------|:--------:|:-----------:|
| legal_domain_sophistication | Domain Expertise | +50.0% | 1 |
| strategic_market_intelligence | Business Strategy | +50.0% | 1 |
| legal_industry_authenticity | Industry Credibility | +45.0% | 1 |
| legal_workflow_credibility | Legal Workflow Credibility | +43.8% | 1 |
| ai_methodology_transparency | Technical Credibility | +42.5% | 1 |
| psychological_adoption_dynamics | User Psychology | +42.5% | 1 |
| domain_digital_asset_availability | Digital Brand Foundation | +40.0% | 1 |
| economic_value_signaling | Business Positioning | +35.0% | 1 |
| narrative_storytelling_power | Brand Narrative | +35.0% | 1 |
| competitive_differentiation | Competitive Differentiation | +27.5% | 1 |
| brand_emotional_resonance | Brand Psychology | +25.0% | 1 |
| innovation_premium_positioning | Market Positioning | +25.0% | 1 |
| contract_domain_relevance | Domain Specificity | +25.0% | 1 |
| category_definition_leadership | Market Positioning | +25.0% | 1 |
| semantic_conceptual_coherence | Linguistic Quality | +25.0% | 1 |

## Cost & Token Comparison

| Metric | Baseline | Harness |
|--------|----------|---------|
| Tasks with data | 1 | 1 |
| Total wall time | 234s | 4573s |
| Avg time / task | 234s | 4573s |
| Input tokens (total) | 28 | ~56,000 (est.) |
| Output tokens (total) | 154 | ~10,500 (est.) |
| Est. cost (USD) | $0.0024 | ~$0.3255 (est.) |
| Avg iterations | 1 | 7.0 |

> Harness token/cost figures are estimates based on 8,000 input + 1,500 output tokens per iteration. Actual usage varies.