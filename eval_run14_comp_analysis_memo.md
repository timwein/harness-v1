# Eval Results: Rubric Harness vs. Vanilla Claude

**Generated:** 2026-04-04 19:20:34 UTC  
**Model:** `claude-sonnet-4-20250514`  
**Max harness iterations:** 0

## Per-Task Results

| Task | Domain | Baseline % | Harness % | Delta | Iters | Base Time | Harness Time |
|------|--------|:----------:|:---------:|:-----:|:-----:|:---------:|:------------:|
| comp_analysis_memo | strategic_analysis | 14.1% | 73.6% | +59.5% | 4 | 191s | 2782s |

## Aggregate Statistics

| Metric | Value |
|--------|-------|
| Tasks evaluated | 1 |
| Mean lift | **+59.5%** |
| Median lift | +59.5% |
| Std dev | 0.0% |
| Improved (>1%) | 1/1 |
| Neutral (±1%) | 0/1 |
| Regressed (<-1%) | 0/1 |

## Per-Criterion Lift (top 15 by avg lift across tasks)

| Criterion | Category | Avg Lift | Appearances |
|-----------|----------|:--------:|:-----------:|
| productivity_cost_roi_coherence | Cross-cutting Analysis | +87.5% | 1 |
| ai_code_quality_rework_rate | Code Quality & Technical Impact | +75.0% | 1 |
| context_window_architectural_understanding | Technical Capabilities & Architecture | +75.0% | 1 |
| latency_flow_state_impact | Technical Capabilities & Code Quality | +68.8% | 1 |
| developer_productivity_quantification | Developer Productivity & Experience | +68.8% | 1 |
| code_telemetry_data_governance | Enterprise Security & Compliance | +67.5% | 1 |
| technical_security_alignment_coherence | Cross-cutting Analysis | +60.0% | 1 |
| total_cost_ownership_analysis | Total Cost of Ownership | +57.5% | 1 |
| scalability_adoption_risk_coherence | Cross-cutting Analysis | +56.3% | 1 |
| enterprise_security_compliance | Enterprise Security & Compliance | +56.2% | 1 |
| offline_capability_assessment | Enterprise Scalability & Performance | +50.0% | 1 |
| pilot_program_rollout_strategy | Adoption & Change Management | +48.8% | 1 |
| learning_curve_adoption_analysis | Developer Productivity & Experience | +47.5% | 1 |
| integration_ecosystem_compatibility | Integration & Platform Architecture | +42.9% | 1 |
| dora_ai_capabilities_model | Organizational Performance & AI Maturity | +42.5% | 1 |

## Cost & Token Comparison

| Metric | Baseline | Harness |
|--------|----------|---------|
| Tasks with data | 1 | 1 |
| Total wall time | 191s | 2782s |
| Avg time / task | 191s | 2782s |
| Input tokens (total) | 55 | ~32,000 (est.) |
| Output tokens (total) | 1,991 | ~6,000 (est.) |
| Est. cost (USD) | $0.0300 | ~$0.1860 (est.) |
| Avg iterations | 1 | 4.0 |

> Harness token/cost figures are estimates based on 8,000 input + 1,500 output tokens per iteration. Actual usage varies.