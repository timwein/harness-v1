# Rubric-Loop Harness Spec

## Overview

A harness for Claude Code that wraps any coding task or agent rollout in a **generation-verification loop with dynamic rubric creation**. The system:

1. **Generates task-specific rubrics** before execution begins
2. **Scores outputs** against rubrics after each iteration
3. **Iterates** until rubric score meets threshold or max iterations reached
4. **Surfaces diagnostics** on which rubric items failed and why

This is analogous to a GAN architecture but for code quality:
- Generator = Claude Code executing the task
- Discriminator = Rubric Scorer evaluating outputs
- Training signal = Rubric items passed/failed with reasoning

---

## Core Components

### 1. Rubric Generator (`rubric_gen`)

**Input**: Task description, context (files, prior attempts, domain)
**Output**: Structured rubric with weighted criteria

```yaml
rubric:
  task_summary: "Implement OAuth2 PKCE flow for mobile app"
  
  criteria:
    - id: "auth_001"
      category: "correctness"
      weight: 3  # 1-3 scale, 3 = critical
      description: "PKCE code verifier is cryptographically random (min 43 chars)"
      verification_method: "code_inspection"
      pass_condition: "Uses crypto.randomBytes or equivalent, length >= 43"
      
    - id: "auth_002"
      category: "correctness"
      weight: 3
      description: "Code challenge uses S256 transform (SHA256 + base64url)"
      verification_method: "code_inspection"
      pass_condition: "SHA256 hash of verifier, base64url encoded (no padding)"
      
    - id: "auth_003"
      category: "security"
      weight: 3
      description: "Verifier is not logged or persisted insecurely"
      verification_method: "code_inspection"
      pass_condition: "No console.log, localStorage, or unencrypted storage of verifier"
      
    - id: "auth_004"
      category: "functionality"
      weight: 2
      description: "Handles token refresh before expiry"
      verification_method: "logic_review"
      pass_condition: "Refresh triggered when access_token has < 5 min remaining"
      
    - id: "auth_005"
      category: "error_handling"
      weight: 2
      description: "Graceful handling of network failures during auth"
      verification_method: "code_inspection"
      pass_condition: "Try/catch with retry logic or user-facing error state"
      
    - id: "auth_006"
      category: "code_quality"
      weight: 1
      description: "Auth logic is encapsulated in dedicated module"
      verification_method: "structure_review"
      pass_condition: "Single file/class with clear interface, no auth logic in UI components"

  scoring:
    pass_threshold: 0.85  # Weighted score needed to pass
    critical_threshold: 1.0  # All weight=3 items must pass
```

**Rubric Generation Strategies** (configurable):

| Strategy | When to Use | How It Works |
|----------|-------------|--------------|
| `task_decomposition` | Complex tasks | Break task into subtasks, generate criteria per subtask |
| `failure_mode_analysis` | Security/reliability | Enumerate ways task could fail, create criteria to prevent each |
| `specification_extraction` | When specs exist | Parse requirements doc/ticket, convert to testable criteria |
| `exemplar_comparison` | When examples exist | Compare to known-good implementation, extract differentiating criteria |
| `domain_heuristics` | Domain-specific tasks | Apply domain best practices (e.g., OAuth, DB migrations, API design) |

---

### 2. Rubric Scorer (`rubric_score`)

**Input**: Rubric + generated output (code, agent trace, artifacts)
**Output**: Scored rubric with pass/fail per criterion + reasoning

```yaml
scored_rubric:
  overall_score: 0.72  # Weighted average
  critical_pass: false  # All weight=3 passed?
  iteration: 2
  
  results:
    - id: "auth_001"
      passed: true
      confidence: 0.95
      evidence: "Line 23: crypto.randomBytes(32).toString('base64url') produces 43+ chars"
      
    - id: "auth_002"
      passed: true
      confidence: 0.90
      evidence: "Line 28: createHash('sha256').update(verifier).digest('base64url')"
      
    - id: "auth_003"
      passed: false
      confidence: 0.85
      evidence: "Line 45: console.log('Verifier:', verifier) - SECURITY ISSUE"
      fix_hint: "Remove debug logging of sensitive values"
      
    - id: "auth_004"
      passed: false
      confidence: 0.70
      evidence: "No proactive refresh logic found. Only refreshes on 401 response."
      fix_hint: "Add timer or check remaining TTL before API calls"
      
    # ...

  failure_summary:
    - "CRITICAL: Verifier logged to console (auth_003)"
    - "Token refresh is reactive, not proactive (auth_004)"
    
  recommended_focus: "auth_003"  # Highest-weight failing item
```

**Scoring Methods** (per criterion type):

| Verification Method | Implementation |
|--------------------|----------------|
| `code_inspection` | AST parsing + pattern matching + LLM review |
| `logic_review` | LLM traces through code paths |
| `structure_review` | File/folder structure analysis |
| `test_execution` | Run existing tests, check coverage |
| `static_analysis` | Invoke linter/type-checker, parse output |
| `runtime_probe` | Execute code in sandbox, observe behavior |

---

### 3. Loop Controller (`rubric_loop`)

**Input**: Task, config (max_iterations, pass_threshold, etc.)
**Output**: Final output + rubric history + diagnostics

```python
# Pseudocode for loop controller

class RubricLoop:
    def __init__(self, config: LoopConfig):
        self.max_iterations = config.max_iterations  # default: 5
        self.pass_threshold = config.pass_threshold  # default: 0.85
        self.critical_required = config.critical_required  # default: True
        self.rubric_refresh_interval = config.rubric_refresh_interval  # default: 3
        
    async def run(self, task: str, context: dict) -> LoopResult:
        # Phase 1: Generate initial rubric
        rubric = await self.generate_rubric(task, context)
        
        history = []
        for i in range(self.max_iterations):
            # Phase 2: Generate solution attempt
            attempt = await self.generate_attempt(
                task=task,
                rubric=rubric,
                prior_attempts=history,
                focus=history[-1].recommended_focus if history else None
            )
            
            # Phase 3: Score attempt against rubric
            scored = await self.score_attempt(attempt, rubric)
            history.append(scored)
            
            # Phase 4: Check termination conditions
            if self.should_terminate(scored):
                return LoopResult(
                    success=True,
                    output=attempt,
                    iterations=i + 1,
                    final_score=scored.overall_score,
                    rubric=rubric,
                    history=history
                )
            
            # Phase 5: Optionally refresh rubric
            if (i + 1) % self.rubric_refresh_interval == 0:
                rubric = await self.refine_rubric(rubric, history)
        
        # Max iterations reached
        return LoopResult(
            success=False,
            output=history[-1].attempt,
            iterations=self.max_iterations,
            final_score=history[-1].overall_score,
            rubric=rubric,
            history=history,
            failure_reason="Max iterations reached without meeting threshold"
        )
    
    def should_terminate(self, scored: ScoredRubric) -> bool:
        if self.critical_required and not scored.critical_pass:
            return False
        return scored.overall_score >= self.pass_threshold
```

**Loop Behaviors**:

| Behavior | Description | Config |
|----------|-------------|--------|
| **Focused Iteration** | Each iteration targets highest-weight failing criterion | `focus_mode: "highest_weight"` |
| **Rubric Refinement** | After N failures, rubric generator adds more specific criteria | `rubric_refresh_interval: 3` |
| **Early Exit** | Stop if no progress for M iterations | `stall_threshold: 2` |
| **Escalation** | If stuck, flag for human review | `escalate_on_stall: true` |
| **Parallel Attempts** | Generate N attempts per iteration, score all, keep best | `parallel_attempts: 3` |

---

### 4. Claude Code Integration

#### Option A: Slash Command (Recommended for Interactive Use)

```
/rubric-loop [task description]
```

**Behavior**:
1. Reads task from argument or current context (selected code, open file, prior conversation)
2. Generates rubric, shows to user for approval/edit
3. Runs loop with progress updates
4. On completion, shows final code + rubric scorecard

**Example Session**:
```
User: /rubric-loop Implement rate limiting middleware for Express

Claude Code:
📋 Generated Rubric (5 criteria):
  ├─ [CRITICAL] rate_001: Uses sliding window or token bucket algorithm
  ├─ [CRITICAL] rate_002: Limits are per-client (IP or API key)
  ├─ [HIGH] rate_003: Returns 429 with Retry-After header
  ├─ [MEDIUM] rate_004: Configurable limits via environment
  └─ [LOW] rate_005: Logs rate limit events for monitoring

Threshold: 0.85 | Max iterations: 5

[Approve rubric? y/n/edit]

User: y

Claude Code:
🔄 Iteration 1/5...
  ├─ Generating attempt...
  ├─ Scoring against rubric...
  └─ Score: 0.65 | Failed: rate_002, rate_003

🔄 Iteration 2/5 (focusing on rate_002)...
  ├─ Generating attempt...
  ├─ Scoring against rubric...
  └─ Score: 0.88 | All critical passed ✓

✅ Loop complete!
  Final score: 0.88
  Iterations: 2
  
[View code] [View rubric history] [Save rubric for reuse]
```

#### Option B: Project Skill File (For Repeatable Patterns)

Create `.claude/skills/rubric-loop.md` in project:

```markdown
# Rubric Loop Skill

When the user asks to implement something with quality checks, verification, 
or "make sure it's right", use this rubric-loop pattern:

## Step 1: Generate Rubric

Before writing any code, generate a rubric using this template:

<rubric_template>
Task: {task_summary}

Critical (must pass):
- [ ] {criterion}: {pass_condition}

High Priority:
- [ ] {criterion}: {pass_condition}

Standard:
- [ ] {criterion}: {pass_condition}
</rubric_template>

Use these strategies to generate criteria:
- Failure mode analysis: What could go wrong?
- Specification extraction: What does the task explicitly require?
- Domain heuristics: What are best practices for this type of task?

## Step 2: Show Rubric to User

Present the rubric and ask:
"Here's my success criteria for this task. Should I proceed, or would you 
like to adjust any criteria?"

## Step 3: Implement with Self-Scoring

After each implementation attempt:
1. Score each rubric item (pass/fail with evidence)
2. If score < 0.85 or any critical item fails, iterate
3. Focus iteration on highest-weight failing item
4. Max 5 iterations before asking user for guidance

## Step 4: Report Results

Show final scorecard:
- Which criteria passed/failed
- Evidence for each
- Confidence level
- Suggestions if not fully passing
```

#### Option C: Python Harness (For Programmatic Use)

```python
# rubric_loop/harness.py

from anthropic import Anthropic
from dataclasses import dataclass
from typing import Optional
import yaml

@dataclass
class RubricCriterion:
    id: str
    category: str
    weight: int  # 1-3
    description: str
    verification_method: str
    pass_condition: str

@dataclass
class Rubric:
    task_summary: str
    criteria: list[RubricCriterion]
    pass_threshold: float = 0.85
    
@dataclass
class ScoredCriterion:
    criterion: RubricCriterion
    passed: bool
    confidence: float
    evidence: str
    fix_hint: Optional[str] = None

@dataclass  
class LoopResult:
    success: bool
    output: str
    iterations: int
    final_score: float
    rubric: Rubric
    history: list[dict]
    failure_reason: Optional[str] = None


class RubricLoopHarness:
    def __init__(
        self,
        client: Anthropic,
        model: str = "claude-sonnet-4-20250514",
        max_iterations: int = 5,
        pass_threshold: float = 0.85,
    ):
        self.client = client
        self.model = model
        self.max_iterations = max_iterations
        self.pass_threshold = pass_threshold
        
    async def generate_rubric(self, task: str, context: str = "") -> Rubric:
        """Generate task-specific rubric."""
        prompt = f"""Generate a rubric for evaluating this task:

Task: {task}

Context: {context}

Output a YAML rubric with 4-8 criteria. Each criterion needs:
- id: short identifier (e.g., "auth_001")
- category: correctness | security | functionality | error_handling | code_quality
- weight: 1 (nice-to-have) | 2 (important) | 3 (critical)
- description: what must be true
- verification_method: code_inspection | logic_review | test_execution | static_analysis
- pass_condition: specific, testable condition

Include at least 2 critical (weight=3) criteria.
"""
        response = self.client.messages.create(
            model=self.model,
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}]
        )
        
        # Parse YAML from response
        rubric_yaml = self._extract_yaml(response.content[0].text)
        return self._parse_rubric(rubric_yaml)
    
    async def score_attempt(
        self, 
        attempt: str, 
        rubric: Rubric,
        context: str = ""
    ) -> tuple[float, list[ScoredCriterion]]:
        """Score an attempt against the rubric."""
        criteria_text = "\n".join([
            f"- {c.id} (weight={c.weight}): {c.description}\n  Pass if: {c.pass_condition}"
            for c in rubric.criteria
        ])
        
        prompt = f"""Score this code against the rubric:

CODE:
```
{attempt}
```

RUBRIC:
{criteria_text}

For each criterion, output:
- id
- passed: true/false
- confidence: 0.0-1.0
- evidence: quote specific code or explain reasoning
- fix_hint: if failed, suggest specific fix

Output as YAML list.
"""
        response = self.client.messages.create(
            model=self.model,
            max_tokens=3000,
            messages=[{"role": "user", "content": prompt}]
        )
        
        scores_yaml = self._extract_yaml(response.content[0].text)
        scored = self._parse_scores(scores_yaml, rubric)
        
        # Calculate weighted score
        total_weight = sum(c.weight for c in rubric.criteria)
        earned_weight = sum(
            c.criterion.weight for c in scored if c.passed
        )
        overall_score = earned_weight / total_weight
        
        return overall_score, scored
    
    async def generate_attempt(
        self,
        task: str,
        rubric: Rubric,
        prior_attempts: list[dict] = None,
        focus: Optional[str] = None
    ) -> str:
        """Generate a solution attempt."""
        rubric_text = "\n".join([
            f"- [{c.weight}/3] {c.description}"
            for c in rubric.criteria
        ])
        
        history_text = ""
        if prior_attempts:
            history_text = "\n\nPRIOR ATTEMPTS:\n"
            for i, attempt in enumerate(prior_attempts):
                history_text += f"\nAttempt {i+1} (score: {attempt['score']:.2f}):\n"
                for s in attempt['scores']:
                    status = "✓" if s.passed else "✗"
                    history_text += f"  {status} {s.criterion.id}: {s.evidence[:100]}\n"
        
        focus_text = ""
        if focus:
            focus_text = f"\n\nFOCUS: Prioritize fixing criterion '{focus}' in this attempt."
        
        prompt = f"""Implement this task:

TASK: {task}

SUCCESS CRITERIA (rubric):
{rubric_text}
{history_text}
{focus_text}

Write complete, working code that satisfies all criteria.
"""
        response = self.client.messages.create(
            model=self.model,
            max_tokens=4000,
            messages=[{"role": "user", "content": prompt}]
        )
        
        return self._extract_code(response.content[0].text)
    
    async def run(self, task: str, context: str = "") -> LoopResult:
        """Run the full rubric loop."""
        rubric = await self.generate_rubric(task, context)
        history = []
        
        for i in range(self.max_iterations):
            # Determine focus from prior iteration
            focus = None
            if history:
                # Find highest-weight failing criterion
                failed = [s for s in history[-1]['scores'] if not s.passed]
                if failed:
                    failed.sort(key=lambda s: s.criterion.weight, reverse=True)
                    focus = failed[0].criterion.id
            
            # Generate attempt
            attempt = await self.generate_attempt(
                task, rubric, history, focus
            )
            
            # Score attempt
            score, scored = await self.score_attempt(attempt, rubric, context)
            
            history.append({
                'iteration': i + 1,
                'attempt': attempt,
                'score': score,
                'scores': scored
            })
            
            # Check termination
            critical_pass = all(
                s.passed for s in scored if s.criterion.weight == 3
            )
            
            if score >= self.pass_threshold and critical_pass:
                return LoopResult(
                    success=True,
                    output=attempt,
                    iterations=i + 1,
                    final_score=score,
                    rubric=rubric,
                    history=history
                )
        
        # Max iterations reached
        return LoopResult(
            success=False,
            output=history[-1]['attempt'],
            iterations=self.max_iterations,
            final_score=history[-1]['score'],
            rubric=rubric,
            history=history,
            failure_reason=f"Score {history[-1]['score']:.2f} below threshold {self.pass_threshold}"
        )
    
    # Helper methods
    def _extract_yaml(self, text: str) -> str:
        """Extract YAML block from response."""
        if "```yaml" in text:
            return text.split("```yaml")[1].split("```")[0]
        if "```" in text:
            return text.split("```")[1].split("```")[0]
        return text
    
    def _extract_code(self, text: str) -> str:
        """Extract code block from response."""
        if "```" in text:
            parts = text.split("```")
            if len(parts) >= 2:
                code = parts[1]
                # Remove language identifier
                if code.startswith(("python", "typescript", "javascript")):
                    code = "\n".join(code.split("\n")[1:])
                return code.strip()
        return text
    
    def _parse_rubric(self, yaml_text: str) -> Rubric:
        """Parse YAML into Rubric object."""
        data = yaml.safe_load(yaml_text)
        criteria = [
            RubricCriterion(**c) for c in data.get('criteria', data)
        ]
        return Rubric(
            task_summary=data.get('task_summary', ''),
            criteria=criteria,
            pass_threshold=data.get('scoring', {}).get('pass_threshold', 0.85)
        )
    
    def _parse_scores(
        self, 
        yaml_text: str, 
        rubric: Rubric
    ) -> list[ScoredCriterion]:
        """Parse YAML scores into ScoredCriterion objects."""
        data = yaml.safe_load(yaml_text)
        criterion_map = {c.id: c for c in rubric.criteria}
        
        scored = []
        for item in data:
            criterion = criterion_map.get(item['id'])
            if criterion:
                scored.append(ScoredCriterion(
                    criterion=criterion,
                    passed=item['passed'],
                    confidence=item.get('confidence', 0.8),
                    evidence=item.get('evidence', ''),
                    fix_hint=item.get('fix_hint')
                ))
        return scored


# CLI interface for Claude Code
if __name__ == "__main__":
    import asyncio
    import sys
    
    async def main():
        client = Anthropic()
        harness = RubricLoopHarness(client)
        
        task = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else input("Task: ")
        
        print(f"\n🎯 Task: {task}\n")
        print("📋 Generating rubric...")
        
        result = await harness.run(task)
        
        print(f"\n{'✅' if result.success else '❌'} Loop complete!")
        print(f"   Iterations: {result.iterations}")
        print(f"   Final score: {result.final_score:.2f}")
        
        print("\n📊 Rubric Results:")
        for item in result.history[-1]['scores']:
            status = "✓" if item.passed else "✗"
            print(f"   {status} [{item.criterion.weight}/3] {item.criterion.id}: {item.criterion.description[:50]}...")
        
        if not result.success:
            print(f"\n⚠️  {result.failure_reason}")
        
        print("\n📄 Final Output:")
        print(result.output[:500] + "..." if len(result.output) > 500 else result.output)
    
    asyncio.run(main())
```

---

## Configuration Schema

```yaml
# .claude/rubric-loop.yaml

defaults:
  max_iterations: 5
  pass_threshold: 0.85
  critical_required: true
  parallel_attempts: 1
  rubric_refresh_interval: 3
  model: "claude-sonnet-4-20250514"
  
rubric_generation:
  strategies:
    - failure_mode_analysis
    - domain_heuristics
  min_criteria: 4
  max_criteria: 10
  required_categories:
    - correctness
    - error_handling
    
scoring:
  verification_methods:
    code_inspection:
      enabled: true
    static_analysis:
      enabled: true
      tools: ["eslint", "mypy"]
    test_execution:
      enabled: false  # Requires test runner setup
      
loop_behavior:
  focus_mode: "highest_weight"  # or "sequential" or "random"
  stall_detection:
    enabled: true
    threshold: 2  # iterations without improvement
    action: "escalate"  # or "refine_rubric" or "abort"
    
output:
  save_history: true
  history_path: ".claude/rubric-history/"
  reuse_rubrics: true  # Cache rubrics for similar tasks
```

---

## Domain-Specific Rubric Templates

### API Implementation
```yaml
criteria:
  - id: api_001
    category: correctness
    weight: 3
    description: "All endpoints return correct HTTP status codes"
    pass_condition: "200/201 for success, 400 for bad input, 401/403 for auth, 404 for not found, 500 for server error"
    
  - id: api_002
    category: security
    weight: 3
    description: "Authentication required on protected endpoints"
    pass_condition: "Middleware checks auth token before handler executes"
    
  - id: api_003
    category: functionality
    weight: 2
    description: "Request validation with clear error messages"
    pass_condition: "Zod/Joi schema validation with field-level error messages"
```

### Database Migration
```yaml
criteria:
  - id: db_001
    category: correctness
    weight: 3
    description: "Migration is reversible"
    pass_condition: "Down migration restores previous schema exactly"
    
  - id: db_002
    category: safety
    weight: 3
    description: "No data loss on existing records"
    pass_condition: "Column drops only after data migrated, NOT NULL only with defaults"
```

### React Component
```yaml
criteria:
  - id: react_001
    category: correctness
    weight: 3
    description: "Component renders without errors"
    pass_condition: "No console errors, handles null/undefined props"
    
  - id: react_002
    category: functionality
    weight: 2
    description: "Loading and error states handled"
    pass_condition: "Shows skeleton/spinner during load, error boundary or fallback UI"
```

---

## Future Extensions

1. **Rubric Learning**: Save scored rubrics, learn which criteria predict actual bugs/issues
2. **Cross-Task Transfer**: Reuse rubric patterns across similar tasks
3. **Human-in-the-Loop**: Escalate to human when stuck, incorporate feedback into rubric
4. **Test Generation**: Generate unit tests from rubric criteria
5. **CI Integration**: Run rubric-loop as PR check, fail if score below threshold
6. **Metrics Dashboard**: Track rubric scores over time, identify recurring failure patterns
