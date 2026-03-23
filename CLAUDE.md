# Rubric System

A generation-verification loop harness. Generates task-specific scoring rubrics grounded in web research, then iterates generation + verification until quality threshold is met.

## Quick Start

```bash
cd rubric_system
python rubric_harness.py "your task here" --max-iter 3 --json
```

## Key Files

- `rubric_system/rubric_harness.py` — Core loop engine
- `rubric_system/models.py` — All dataclasses and enums
- `rubric_system/scoring_engine.py` — 6 scoring methods
- `rubric_system/self_improve.py` — Self-improvement engine
- `rubric-loop-harness-spec.md` — Full system spec

## Custom Commands

- `/verify <task>` — Run the rubric gen-verify loop on any task
- `/verify-improve` — Analyze and improve criterion effectiveness

## Requirements

- Python 3.10+
- `anthropic` package
- `ANTHROPIC_API_KEY` environment variable set
