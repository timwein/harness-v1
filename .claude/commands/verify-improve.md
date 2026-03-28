---
description: Run the self-improvement cycle on the rubric harness — analyzes accumulated criterion effectiveness data and proposes source code edits to scoring rubric factories and measurement prompts
---

Run the rubric harness self-improvement cycle.

## Instructions

1. Change to the rubric_system/ directory
2. Run self-improvement in dry-run mode first:
```bash
cd rubric_system
python -m rubric_system.self_improve propose 2>&1
```

3. Report what proposals were generated:
   - Which functions/criteria are targeted
   - What the proposed changes are
   - The rationale (what performance data drove this)

4. Ask if the user wants to apply the proposals. If yes:
```bash
python -m rubric_system.self_improve auto --max-edits 3 2>&1
```

5. If edits were applied, show a git diff of what changed.

$ARGUMENTS
