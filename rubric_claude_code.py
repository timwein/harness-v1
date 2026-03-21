#!/usr/bin/env python3
"""
Claude Code Integration for Rubric Loop

This module provides integration points for Claude Code:
1. As a CLI tool that Claude Code can invoke
2. As a library that can be imported into custom scripts
3. Output formatting optimized for Claude Code's display

Usage from Claude Code:
    /run python rubric_claude_code.py "Implement rate limiting"
    /run python rubric_claude_code.py --file src/auth.ts --task "Add PKCE support"
"""

import asyncio
import json
import sys
import argparse
from pathlib import Path
from typing import Optional

from rubric_harness import RubricLoop, LoopResult, Rubric
from rubric_system.models import Iteration, CriterionScore


def format_for_claude_code(result: LoopResult) -> str:
    """Format result for optimal display in Claude Code."""
    lines = []

    # Header
    status = "PASSED" if result.success else "NEEDS WORK"
    lines.append(f"## Rubric Loop Result: {status}")
    lines.append("")
    lines.append(f"**Task:** {result.rubric.task}")
    lines.append(f"**Score:** {result.final_percentage:.0%} ({result.final_score:.1f}/{result.rubric.total_points}) | **Iterations:** {result.iterations}")
    lines.append("")

    # Scorecard table
    lines.append("### Scorecard")
    lines.append("")
    lines.append("| Status | Criterion | Score | Evidence |")
    lines.append("|--------|-----------|-------|----------|")

    last_scores = result.history[-1].criterion_scores
    for cs in last_scores:
        status_icon = "PASS" if cs.percentage >= 0.8 else "WARN" if cs.percentage >= 0.5 else "FAIL"
        evidence = cs.evidence[:50] + "..." if len(cs.evidence) > 50 else cs.evidence
        evidence = evidence.replace("|", "\\|").replace("\n", " ")
        lines.append(f"| {status_icon} | {cs.criterion_id} | {cs.points_earned:.1f}/{cs.max_points} | {evidence} |")

    lines.append("")

    # Sub-scores for underperforming criteria
    low_criteria = [cs for cs in last_scores if cs.percentage < 0.8]
    if low_criteria:
        lines.append("### Improvements Needed")
        lines.append("")
        for cs in low_criteria:
            lines.append(f"**{cs.criterion_id}** ({cs.points_earned:.1f}/{cs.max_points})")
            for hint in cs.improvement_hints[:3]:
                lines.append(f"  - {hint}")
            for p in cs.penalties_applied[:3]:
                lines.append(f"  - Fix: {p['violation']} (+{abs(p['penalty']):.1f} pts)")
            lines.append("")

    # Content output
    lines.append("### Generated Content")
    lines.append("")
    lines.append("```")
    lines.append(result.output[:3000])
    if len(result.output) > 3000:
        lines.append("... (truncated)")
    lines.append("```")

    return "\n".join(lines)


def format_rubric_for_approval(rubric: Rubric) -> str:
    """Format rubric for user approval."""
    lines = []
    lines.append("## Generated Rubric")
    lines.append("")
    lines.append(f"**Task:** {rubric.task}")
    lines.append(f"**Domain:** {rubric.domain}")
    lines.append(f"**Total Points:** {rubric.total_points}")
    lines.append(f"**Pass Threshold:** {rubric.pass_threshold:.0%}")
    lines.append("")

    for c in rubric.criteria:
        lines.append(f"- `{c.id}` ({c.scoring.max_points} pts): {c.description}")

    lines.append("")
    lines.append("---")
    lines.append("*Reply with modifications or 'proceed' to start the loop.*")

    return "\n".join(lines)


class ClaudeCodeRubricLoop(RubricLoop):
    """Extended RubricLoop with Claude Code-specific features."""

    def __init__(self, **kwargs):
        kwargs.setdefault("verbose", False)
        super().__init__(**kwargs)
        self._progress_callback = None

    def set_progress_callback(self, callback):
        """Set callback for progress updates."""
        self._progress_callback = callback

    def _log(self, msg: str):
        if self._progress_callback:
            self._progress_callback(msg)
        elif self.verbose:
            print(msg)

    async def run_with_approval(
        self,
        task: str,
        context: str = "",
        auto_approve: bool = False
    ) -> LoopResult:
        """Run with rubric approval step."""
        from rubric_harness import detect_domain, build_knowledge_work_rubric

        domain, confidence = detect_domain(task)

        if domain == "knowledge_work_research":
            rubric = build_knowledge_work_rubric(task)
        else:
            rubric = build_knowledge_work_rubric(task)  # Default

        if not auto_approve:
            print(format_rubric_for_approval(rubric))
            response = input("\n> ").strip().lower()
            if response not in ["proceed", "yes", "y", "ok", ""]:
                print("Rubric not approved. Exiting.")
                sys.exit(0)

        return await self._run_with_rubric(rubric)

    async def _run_with_rubric(self, rubric: Rubric) -> LoopResult:
        """Run loop with pre-generated rubric."""
        history = []

        for i in range(1, self.max_iterations + 1):
            print(f"\rIteration {i}/{self.max_iterations}...", end="", flush=True)

            focus_areas = []
            if history:
                focus_areas = self._get_focus_areas(history[-1].criterion_scores)

            content = await self.generate_content(rubric, history, focus_areas)
            total, max_total, criterion_scores = await self.score_content(content, rubric)
            percentage = total / max_total if max_total > 0 else 0

            history.append(Iteration(
                number=i,
                attempt=content,
                total_score=total,
                max_score=max_total,
                percentage=percentage,
                criterion_scores=criterion_scores,
                focus_areas=[f"{f[0]}.{f[1]}" for f in focus_areas]
            ))

            print(f"\rIteration {i}: {percentage:.0%}          ")

            if percentage >= self.pass_threshold:
                return LoopResult(
                    success=True,
                    output=content,
                    iterations=i,
                    final_score=total,
                    final_percentage=percentage,
                    rubric=rubric,
                    history=history
                )

        final = history[-1]
        return LoopResult(
            success=False,
            output=final.attempt,
            iterations=self.max_iterations,
            final_score=final.total_score,
            final_percentage=final.percentage,
            rubric=rubric,
            history=history,
            improvement_summary=[
                f"{cs.criterion_id}: +{cs.max_points - cs.points_earned:.1f} pts available"
                for cs in sorted(final.criterion_scores, key=lambda x: x.percentage)
                if cs.percentage < 0.8
            ]
        )


async def main():
    parser = argparse.ArgumentParser(
        description="Rubric Loop for Claude Code",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python rubric_claude_code.py "Implement rate limiting middleware"
  python rubric_claude_code.py --file src/auth.ts --task "Add PKCE support"
  python rubric_claude_code.py --auto-approve "Create user signup endpoint"
        """
    )
    parser.add_argument("task", nargs="?", help="Task description")
    parser.add_argument("--file", "-f", help="File to work on (provides context)")
    parser.add_argument("--auto-approve", "-y", action="store_true", help="Skip rubric approval")
    parser.add_argument("--threshold", "-t", type=float, default=0.85, help="Pass threshold (default: 0.85)")
    parser.add_argument("--max-iter", "-n", type=int, default=5, help="Max iterations (default: 5)")
    parser.add_argument("--output", "-o", help="Output file for result JSON")
    parser.add_argument("--code-only", action="store_true", help="Output only the final content")

    args = parser.parse_args()

    if args.task:
        task = args.task
    elif not sys.stdin.isatty():
        task = sys.stdin.read().strip()
    else:
        task = input("Task: ")

    context = ""
    if args.file:
        file_path = Path(args.file)
        if file_path.exists():
            context = f"Working on file: {args.file}\n\nCurrent content:\n```\n{file_path.read_text()}\n```"

    loop = ClaudeCodeRubricLoop(
        pass_threshold=args.threshold,
        max_iterations=args.max_iter
    )

    result = await loop.run_with_approval(
        task=task,
        context=context,
        auto_approve=args.auto_approve
    )

    if args.code_only:
        print(result.output)
    else:
        print("\n" + format_for_claude_code(result))

    if args.output:
        with open(args.output, "w") as f:
            json.dump({
                "success": result.success,
                "iterations": result.iterations,
                "final_score": result.final_score,
                "final_percentage": result.final_percentage,
                "output": result.output,
                "rubric": {
                    "task": result.rubric.task,
                    "domain": result.rubric.domain,
                    "total_points": result.rubric.total_points,
                    "criteria": [
                        {
                            "id": c.id,
                            "category": c.category,
                            "description": c.description,
                            "max_points": c.scoring.max_points
                        }
                        for c in result.rubric.criteria
                    ]
                },
                "history": [
                    {
                        "iteration": it.number,
                        "score": it.total_score,
                        "max_score": it.max_score,
                        "percentage": it.percentage,
                        "criterion_scores": [
                            {
                                "id": cs.criterion_id,
                                "points": cs.points_earned,
                                "max": cs.max_points,
                                "percentage": cs.percentage
                            }
                            for cs in it.criterion_scores
                        ]
                    }
                    for it in result.history
                ]
            }, f, indent=2)
        print(f"\nSaved to {args.output}")

    sys.exit(0 if result.success else 1)


if __name__ == "__main__":
    asyncio.run(main())
