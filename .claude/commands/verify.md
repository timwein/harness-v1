---
description: Run the rubric gen-verify loop on any task — generates a bespoke scoring rubric grounded in web research of domain best practices, then iterates generation-verification until quality threshold is met
---

Run the rubric generation-verification harness on this task.

## Task
$ARGUMENTS

## Instructions

1. Change to the rubric_system/ directory
2. Run the harness:
```bash
cd rubric_system
python rubric_harness.py "$ARGUMENTS" --max-iter 5 --json 2>&1
```

3. Parse the JSON output and report:
   - **Pass/Fail** and overall score (e.g. "PASSED 87.3%")
   - **Per-criterion breakdown**: for each criterion, show points earned / max points and percentage
   - **Weakest areas**: highlight the 2-3 criteria with lowest scores and what specifically scored low
   - **Rubric used**: note whether it was generated (with research) or pre-built, and the domain
   - If it failed, note how close it got and the biggest point gaps

4. If the run fails with an import error, try: `PYTHONPATH=. python rubric_harness.py "$ARGUMENTS" --max-iter 5 --json`

## Flags you can append to $ARGUMENTS
- `--max-iter 5` for more iterations (default 5)
- `--threshold 0.90` for a higher quality bar (default 0.85)
- `--no-research` to skip web research (faster, less grounded)
- `--rubric <name>` to use a pre-built rubric (run --list-rubrics to see options)
- `--self-improve` to analyze criterion effectiveness after the run
- `--explain` to just show rubric resolution without running the loop
- `--seed ./draft.md` to warm-start from an existing draft (skips initial generation, scores the draft directly)
- `--context ./notes.md ./summary.txt` for supplementary context files injected into rubric generation and edit prompts

## Examples
- `/verify Write a cold outreach email to a Series B SaaS founder`
- `/verify Write a bash script that backs up PostgreSQL to S3 --threshold 0.90`
- `/verify --list-rubrics`
- `/verify Design a REST API for user auth --no-research --max-iter 5`
- `/verify "Write a forensic analysis memo" --seed ./memo_v1.md --context ./chat_summary.txt`
- `/verify "Write a product spec" --context ./cowork_notes.md ./prior_decisions.md`
