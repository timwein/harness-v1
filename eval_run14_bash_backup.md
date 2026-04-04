# Eval Results: Rubric Harness vs. Vanilla Claude

**Generated:** 2026-04-04 19:14:16 UTC  
**Model:** `claude-sonnet-4-20250514`  
**Max harness iterations:** 0

## Per-Task Results

| Task | Domain | Baseline % | Harness % | Delta | Iters | Base Time | Harness Time |
|------|--------|:----------:|:---------:|:-----:|:-----:|:---------:|:------------:|
| bash_backup | bash_scripting | 32.3% | 66.0% | +33.7% | 6 | 134s | 2542s |

## Aggregate Statistics

| Metric | Value |
|--------|-------|
| Tasks evaluated | 1 |
| Mean lift | **+33.7%** |
| Median lift | +33.7% |
| Std dev | 0.0% |
| Improved (>1%) | 1/1 |
| Neutral (±1%) | 0/1 |
| Regressed (<-1%) | 0/1 |

## Per-Criterion Lift (top 15 by avg lift across tasks)

| Criterion | Category | Avg Lift | Appearances |
|-----------|----------|:--------:|:-----------:|
| postgresql_aware_error_handling | PostgreSQL Operations Excellence | +83.8% | 1 |
| s3_lifecycle_backup_rotation | Backup Rotation & Lifecycle Management | +50.0% | 1 |
| structured_logging_monitoring | Monitoring & Alerting Integration | +45.0% | 1 |
| encryption_compliance_framework | Security & Compliance Framework | +40.0% | 1 |
| aws_cli_security_integration | AWS S3 Integration & Security | +33.3% | 1 |
| pgbackrest_enterprise_backup | Enterprise Backup Implementation | +30.0% | 1 |
| disaster_recovery_procedures | Business Continuity | +21.2% | 1 |
| backup_integrity_verification | Backup Integrity & Verification | +16.7% | 1 |
| wal_archiving_pitr | Point-in-Time Recovery | +15.0% | 1 |
| pg_consistent_snapshot_config | PostgreSQL Operations Excellence | +1.3% | 1 |

## Cost & Token Comparison

| Metric | Baseline | Harness |
|--------|----------|---------|
| Tasks with data | 1 | 1 |
| Total wall time | 134s | 2542s |
| Avg time / task | 134s | 2542s |
| Input tokens (total) | 30 | ~48,000 (est.) |
| Output tokens (total) | 4,096 | ~9,000 (est.) |
| Est. cost (USD) | $0.0615 | ~$0.2790 (est.) |
| Avg iterations | 1 | 6.0 |

> Harness token/cost figures are estimates based on 8,000 input + 1,500 output tokens per iteration. Actual usage varies.