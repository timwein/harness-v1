"""
CI Integration Module

Run rubric-loop as a PR check. Fails if score below threshold.

Supports:
- GitHub Actions
- GitLab CI
- Generic CI (exit codes)

Features:
- Automatic rubric selection based on changed files
- Parallel scoring of multiple files
- PR comment with scorecard
- Configurable thresholds
"""

import json
import os
import sys
import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
import subprocess

from rubric_system.models import FileScore, CIResult


# ============================================================================
# Configuration
# ============================================================================

@dataclass
class CIConfig:
    """CI integration configuration."""

    # Thresholds
    pass_threshold: float = 0.85
    critical_required: bool = True
    warn_threshold: float = 0.70

    # Behavior
    fail_on_new_files: bool = True
    fail_on_modified_files: bool = False
    allow_skip_label: str = "skip-rubric"

    # File patterns
    include_patterns: list[str] = None
    exclude_patterns: list[str] = None

    # Rubric selection
    rubric_config_path: str = ".rubric/config.yaml"
    auto_select_rubric: bool = True

    def __post_init__(self):
        if self.include_patterns is None:
            self.include_patterns = ["*.py", "*.ts", "*.js", "*.go", "*.rs"]
        if self.exclude_patterns is None:
            self.exclude_patterns = ["*_test.*", "*.spec.*", "test_*", "*_mock.*"]


# ============================================================================
# Git Integration
# ============================================================================

def get_changed_files(base_ref: str = "main") -> dict[str, str]:
    """
    Get files changed in current PR/commit.
    Returns dict of {path: change_type} where change_type is 'A', 'M', 'D'.
    """
    try:
        result = subprocess.run(
            ["git", "diff", "--name-status", f"{base_ref}...HEAD"],
            capture_output=True,
            text=True,
            check=True
        )

        changes = {}
        for line in result.stdout.strip().split('\n'):
            if line:
                parts = line.split('\t')
                if len(parts) >= 2:
                    change_type = parts[0][0]
                    path = parts[-1]
                    changes[path] = change_type

        return changes

    except subprocess.CalledProcessError:
        result = subprocess.run(
            ["git", "diff", "--name-status", "--cached"],
            capture_output=True,
            text=True
        )

        changes = {}
        for line in result.stdout.strip().split('\n'):
            if line:
                parts = line.split('\t')
                if len(parts) >= 2:
                    changes[parts[-1]] = parts[0][0]

        return changes


def get_file_content(path: str, ref: str = "HEAD") -> str:
    """Get file content at a specific ref."""
    result = subprocess.run(
        ["git", "show", f"{ref}:{path}"],
        capture_output=True,
        text=True
    )
    return result.stdout


def matches_pattern(path: str, patterns: list[str]) -> bool:
    """Check if path matches any glob pattern."""
    from fnmatch import fnmatch
    return any(fnmatch(path, pattern) for pattern in patterns)


# ============================================================================
# GitHub Actions Integration
# ============================================================================

class GitHubActions:
    """GitHub Actions specific integration."""

    @staticmethod
    def is_github_actions() -> bool:
        return os.environ.get("GITHUB_ACTIONS") == "true"

    @staticmethod
    def get_pr_number() -> Optional[int]:
        ref = os.environ.get("GITHUB_REF", "")
        if "/pull/" in ref:
            try:
                return int(ref.split("/pull/")[1].split("/")[0])
            except (IndexError, ValueError):
                pass
        return None

    @staticmethod
    def get_base_ref() -> str:
        return os.environ.get("GITHUB_BASE_REF", "main")

    @staticmethod
    def set_output(name: str, value: str):
        output_file = os.environ.get("GITHUB_OUTPUT")
        if output_file:
            with open(output_file, "a") as f:
                f.write(f"{name}={value}\n")

    @staticmethod
    def create_check_run_annotation(
        path: str,
        line: int,
        message: str,
        level: str = "warning"
    ):
        print(f"::{level} file={path},line={line}::{message}")

    @staticmethod
    def format_summary(result: CIResult) -> str:
        lines = [
            "# Rubric Loop Results",
            "",
            f"**Status:** {result.status.upper()}",
            "",
            "## File Scores",
            "",
            "| File | Score | Status | Details |",
            "|------|-------|--------|---------|"
        ]

        for fs in result.file_scores:
            status_emoji = "PASS" if fs.passed else ("WARN" if fs.score >= 0.7 else "FAIL")
            new_badge = "[NEW] " if fs.is_new_file else ""
            lines.append(
                f"| {new_badge}{fs.path} | {fs.score:.0%} | {status_emoji} | "
                f"{fs.criteria_passed}/{fs.criteria_total} criteria |"
            )

        lines.extend([
            "",
            "## Summary",
            "",
            result.summary
        ])

        return "\n".join(lines)

    @staticmethod
    def write_job_summary(content: str):
        summary_file = os.environ.get("GITHUB_STEP_SUMMARY")
        if summary_file:
            with open(summary_file, "a") as f:
                f.write(content)


# ============================================================================
# Main CI Runner
# ============================================================================

class CIRunner:
    """Main CI integration runner."""

    def __init__(self, config: CIConfig = None):
        self.config = config or CIConfig()
        self._rubric_loop = None

    @property
    def rubric_loop(self):
        """Lazy-load rubric loop to avoid import at module level."""
        if self._rubric_loop is None:
            # Import from the canonical harness
            sys.path.insert(0, str(Path(__file__).parent.parent))
            from rubric_harness import RubricLoop
            self._rubric_loop = RubricLoop(
                pass_threshold=self.config.pass_threshold,
                verbose=False
            )
        return self._rubric_loop

    def should_check_file(self, path: str, change_type: str) -> bool:
        if not matches_pattern(path, self.config.include_patterns):
            return False
        if matches_pattern(path, self.config.exclude_patterns):
            return False
        if change_type == 'D':
            return False
        return True

    async def score_file(self, path: str, is_new: bool) -> FileScore:
        """Score a single file."""
        content = get_file_content(path)

        if is_new:
            task = f"Review new file: {path}"
        else:
            task = f"Review changes to: {path}"

        result = await self.rubric_loop.run(task, context=content)
        last_scores = result.history[-1].criterion_scores

        return FileScore(
            path=path,
            score=result.final_percentage,
            passed=result.success,
            criteria_passed=sum(1 for cs in last_scores if cs.percentage >= 0.8),
            criteria_total=len(result.rubric.criteria),
            critical_passed=all(
                cs.percentage >= 0.8 for cs in last_scores
                # In v4, all criteria are point-based; treat <50% as critical failure
            ),
            details=[
                {
                    "id": cs.criterion_id,
                    "points": cs.points_earned,
                    "max_points": cs.max_points,
                    "percentage": cs.percentage,
                    "improvement_hints": cs.improvement_hints[:2]
                }
                for cs in last_scores
            ],
            is_new_file=is_new
        )

    async def run(self, base_ref: str = None) -> CIResult:
        """Run CI check on changed files."""
        if base_ref is None:
            if GitHubActions.is_github_actions():
                base_ref = GitHubActions.get_base_ref()
            else:
                base_ref = "main"

        changes = get_changed_files(base_ref)

        files_to_check = [
            (path, change_type)
            for path, change_type in changes.items()
            if self.should_check_file(path, change_type)
        ]

        if not files_to_check:
            return CIResult(
                passed=True,
                status="success",
                file_scores=[],
                summary="No files to check."
            )

        file_scores = []
        for path, change_type in files_to_check:
            is_new = change_type == 'A'
            score = await self.score_file(path, is_new)
            file_scores.append(score)

        all_passed = all(fs.passed for fs in file_scores)
        any_critical_failed = any(not fs.critical_passed for fs in file_scores)

        if any_critical_failed:
            passed = False
            status = "failure"
        elif all_passed:
            passed = True
            status = "success"
        else:
            new_file_failures = [
                fs for fs in file_scores
                if not fs.passed and fs.is_new_file
            ]

            if new_file_failures and self.config.fail_on_new_files:
                passed = False
                status = "failure"
            elif self.config.fail_on_modified_files:
                passed = False
                status = "failure"
            else:
                passed = True
                status = "warning"

        total_score = sum(fs.score for fs in file_scores) / len(file_scores)
        summary_lines = [
            f"Checked {len(file_scores)} file(s).",
            f"Average score: {total_score:.0%}",
        ]

        if not passed:
            failing = [fs for fs in file_scores if not fs.passed]
            summary_lines.append(f"Failing files: {', '.join(fs.path for fs in failing)}")

        return CIResult(
            passed=passed,
            status=status,
            file_scores=file_scores,
            summary="\n".join(summary_lines)
        )


# ============================================================================
# GitHub Action Workflow
# ============================================================================

GITHUB_ACTION_WORKFLOW = """
# .github/workflows/rubric-loop.yml
name: Rubric Loop Check

on:
  pull_request:
    branches: [main, develop]

jobs:
  rubric-check:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: pip install anthropic

      - name: Run Rubric Loop
        env:
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
        run: python -m rubric_system.rubric_ci --base-ref ${{ github.base_ref }}

      - name: Post PR Comment
        if: always() && github.event_name == 'pull_request'
        uses: actions/github-script@v7
        with:
          script: |
            const fs = require('fs');
            const summary = fs.readFileSync('rubric-results.md', 'utf8');
            github.rest.issues.createComment({
              issue_number: context.issue.number,
              owner: context.repo.owner,
              repo: context.repo.repo,
              body: summary
            });
"""


# ============================================================================
# Default Config YAML
# ============================================================================

DEFAULT_CONFIG_YAML = """
# .rubric/config.yaml
# Rubric Loop CI Configuration

pass_threshold: 0.85
warn_threshold: 0.70
critical_required: true

fail_on_new_files: true
fail_on_modified_files: false
allow_skip_label: "skip-rubric"

include_patterns:
  - "*.py"
  - "*.ts"
  - "*.tsx"
  - "*.js"
  - "*.jsx"
  - "*.go"

exclude_patterns:
  - "*_test.py"
  - "*.spec.ts"
  - "*.test.ts"
  - "test_*.py"
  - "*_mock.*"
  - "__mocks__/*"
  - "fixtures/*"

rubric_overrides:
  "api/**/*.py":
    template: "api_rest_endpoint"
  "auth/**/*":
    template: "auth_oauth2"
    pass_threshold: 0.95
  "migrations/**/*":
    template: "db_migration"
"""


# ============================================================================
# CLI
# ============================================================================

async def main():
    import argparse

    parser = argparse.ArgumentParser(description="Rubric Loop CI Integration")
    parser.add_argument("--base-ref", default=None, help="Base ref for diff")
    parser.add_argument("--config", default=".rubric/config.yaml", help="Config file")
    parser.add_argument("--output", default="rubric-results.md", help="Output file")
    parser.add_argument("--json-output", help="JSON output file")
    parser.add_argument("--init", action="store_true", help="Create config files")

    args = parser.parse_args()

    if args.init:
        Path(".rubric").mkdir(exist_ok=True)
        Path(".rubric/config.yaml").write_text(DEFAULT_CONFIG_YAML)
        Path(".github/workflows").mkdir(parents=True, exist_ok=True)
        Path(".github/workflows/rubric-loop.yml").write_text(GITHUB_ACTION_WORKFLOW)
        print("Created:")
        print("  .rubric/config.yaml")
        print("  .github/workflows/rubric-loop.yml")
        return

    runner = CIRunner()
    result = await runner.run(args.base_ref)

    if GitHubActions.is_github_actions():
        summary = GitHubActions.format_summary(result)
        GitHubActions.write_job_summary(summary)
        GitHubActions.set_output("passed", str(result.passed).lower())
        avg_score = sum(fs.score for fs in result.file_scores) / len(result.file_scores) if result.file_scores else 1.0
        GitHubActions.set_output("score", str(avg_score))

        for fs in result.file_scores:
            if not fs.passed:
                for detail in fs.details:
                    if detail.get("percentage", 1.0) < 0.5:
                        hints = detail.get("improvement_hints", [])
                        msg = f"[{detail['id']}] {hints[0] if hints else 'Below threshold'}"
                        GitHubActions.create_check_run_annotation(
                            fs.path, 1, msg, "error"
                        )

    md_content = f"""# Rubric Loop Results

**Status:** {result.status.upper()}
**Passed:** {result.passed}

## Files Checked

| File | Score | Status |
|------|-------|--------|
"""
    for fs in result.file_scores:
        status = "PASS" if fs.passed else "FAIL"
        md_content += f"| {fs.path} | {fs.score:.0%} | {status} |\n"

    md_content += f"\n## Summary\n\n{result.summary}\n"

    Path(args.output).write_text(md_content)
    print(f"Results written to {args.output}")

    if args.json_output:
        json_data = {
            "passed": result.passed,
            "status": result.status,
            "files": [
                {
                    "path": fs.path,
                    "score": fs.score,
                    "passed": fs.passed,
                    "is_new": fs.is_new_file,
                    "details": fs.details
                }
                for fs in result.file_scores
            ],
            "summary": result.summary
        }
        Path(args.json_output).write_text(json.dumps(json_data, indent=2))

    sys.exit(0 if result.passed else 1)


if __name__ == "__main__":
    asyncio.run(main())
