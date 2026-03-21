---
name: Rubric Loop
description: Generation-verification loop for quality assurance. Use when implementing features with quality requirements, verification needs, or when user requests "production quality", "make sure it's right", or mentions rubrics/criteria.
version: 1.0
triggers:
  - "make sure it's right"
  - "verify it works"
  - "with tests"
  - "production quality"
  - "rubric"
  - "criteria"
  - "quality assurance"
  - "verify"
  - "validation"
---

# Rubric Loop Skill

> Use this skill when the user wants to implement something with quality assurance, verification, or when they say things like "make sure it's right", "verify it works", "with tests", "production quality", or explicitly mentions rubrics/criteria.

## Overview

This skill implements a **generation-verification loop** where:
1. You create success criteria (rubric) before writing code
2. You score your output against the rubric
3. You iterate until the rubric passes or max iterations reached

This is analogous to a GAN: Generator (code) ↔ Discriminator (rubric scorer)

---

## Step 1: Generate Rubric

Before writing ANY code, generate a rubric. Use this template:

```yaml
rubric:
  task: "{one-line task summary}"
  
  criteria:
    # CRITICAL (weight: 3) - Must all pass
    - id: "{prefix}_001"
      weight: 3
      category: correctness | security | data_integrity
      description: "{what must be true}"
      pass_condition: "{specific, testable condition}"
      
    # HIGH (weight: 2) - Should pass for quality
    - id: "{prefix}_002"  
      weight: 2
      category: functionality | error_handling | performance
      description: "{what must be true}"
      pass_condition: "{specific, testable condition}"
      
    # STANDARD (weight: 1) - Nice to have
    - id: "{prefix}_003"
      weight: 1
      category: code_quality | maintainability | documentation
      description: "{what must be true}"
      pass_condition: "{specific, testable condition}"

  thresholds:
    pass_score: 0.85  # Weighted average needed
    critical_required: true  # All weight=3 must pass
```

### Rubric Generation Strategies

Use these strategies based on task type:

**1. Failure Mode Analysis** (for critical/security tasks)
- List ways the code could fail or be exploited
- Create criterion to prevent each failure mode
- Example: "What if the user sends malformed input?" → criterion for input validation

**2. Specification Extraction** (when requirements exist)
- Parse the explicit requirements
- Convert each into testable criterion
- Example: "Must support pagination" → criterion for limit/offset params

**3. Domain Heuristics** (for common patterns)
- Apply best practices for the domain
- See domain templates below

**4. Edge Case Enumeration** (for data processing)
- List boundary conditions
- Create criterion for each
- Example: "Empty list, single item, duplicates, nulls"

---

## Step 2: Present Rubric to User

Show the rubric and ask for approval:

```
📋 **Generated Rubric** for: {task}

**Critical (must pass):**
- [ ] {id}: {description}

**High Priority:**
- [ ] {id}: {description}

**Standard:**
- [ ] {id}: {description}

Pass threshold: 85% weighted score
Max iterations: 5

👉 **Should I proceed with this rubric, or would you like to adjust any criteria?**
```

Wait for user confirmation before proceeding.

---

## Step 3: Implementation Loop

```
for iteration in 1..max_iterations:
    
    # Generate attempt
    if iteration == 1:
        Write code to satisfy ALL rubric criteria
    else:
        Focus on fixing: {highest_weight_failing_criterion}
        Review prior attempt and fix specific issues
    
    # Score attempt
    For each criterion:
        - passed: true/false
        - confidence: 0.0-1.0
        - evidence: specific code reference or reasoning
        - fix_hint: if failed, what to change
    
    # Calculate score
    score = sum(passed * weight) / sum(weight)
    critical_pass = all weight=3 criteria passed
    
    # Check termination
    if score >= 0.85 AND critical_pass:
        BREAK → Success
    
    # Report progress
    Show: "Iteration {n}: Score {score} | Failed: {failing_ids}"
```

---

## Step 4: Scoring Each Criterion

For each rubric item, determine pass/fail:

### Code Inspection (most common)
- Read the code and check if condition is met
- Quote specific lines as evidence
- Be strict on critical items, lenient on standard

### Logic Review
- Trace through code paths mentally
- Check if all branches satisfy the condition
- Consider edge cases

### Static Analysis (if tools available)
```bash
# TypeScript
npx tsc --noEmit

# ESLint
npx eslint {file}

# Python type check
mypy {file}
```

### Test Execution (if tests exist)
```bash
npm test
pytest
```

---

## Step 5: Iteration Focus

When iterating, focus on the highest-weight failing criterion:

```
🔄 **Iteration 2/5** (focusing on {criterion_id})

Previous attempt failed because:
- {evidence from scoring}

Fix approach:
- {specific change to make}

[Then show updated code]
```

---

## Step 6: Final Report

On completion (success or max iterations):

```
{'✅' if success else '⚠️'} **Rubric Loop Complete**

| Criterion | Weight | Status | Evidence |
|-----------|--------|--------|----------|
| {id} | {weight}/3 | ✓/✗ | {brief evidence} |

**Final Score:** {score:.0%}
**Iterations:** {n}

{if not success}
**Remaining Issues:**
- {failing criterion}: {fix_hint}

**Recommendation:** {next steps}
```

---

## Domain Templates

### API Endpoint
```yaml
criteria:
  - id: api_001
    weight: 3
    description: "Correct HTTP status codes"
    pass_condition: "200/201 success, 400 bad input, 401/403 auth, 404 not found, 500 server error"
    
  - id: api_002
    weight: 3
    description: "Input validation"
    pass_condition: "All user input validated before processing"
    
  - id: api_003
    weight: 2
    description: "Error responses include message"
    pass_condition: "JSON response with 'error' field explaining issue"
    
  - id: api_004
    weight: 2
    description: "Async errors handled"
    pass_condition: "try/catch around await, errors don't crash server"
```

### Database Query
```yaml
criteria:
  - id: db_001
    weight: 3
    description: "SQL injection prevented"
    pass_condition: "Parameterized queries or ORM, no string concatenation"
    
  - id: db_002
    weight: 3
    description: "Transaction for multi-step operations"
    pass_condition: "BEGIN/COMMIT/ROLLBACK or ORM transaction wrapper"
    
  - id: db_003
    weight: 2
    description: "Indexes used for filtered columns"
    pass_condition: "WHERE clause columns have indexes"
```

### React Component
```yaml
criteria:
  - id: react_001
    weight: 3
    description: "Handles loading state"
    pass_condition: "Shows loading indicator while data fetching"
    
  - id: react_002
    weight: 3
    description: "Handles error state"
    pass_condition: "Catches errors and shows user-friendly message"
    
  - id: react_003
    weight: 2
    description: "Props have TypeScript types"
    pass_condition: "Interface or type for all props"
    
  - id: react_004
    weight: 1
    description: "Accessible"
    pass_condition: "Semantic HTML, aria labels where needed"
```

### Authentication Flow
```yaml
criteria:
  - id: auth_001
    weight: 3
    description: "Secrets not hardcoded"
    pass_condition: "All secrets from env vars or secret manager"
    
  - id: auth_002
    weight: 3
    description: "Tokens stored securely"
    pass_condition: "httpOnly cookies or secure storage, not localStorage for sensitive"
    
  - id: auth_003
    weight: 3
    description: "Token validation on protected routes"
    pass_condition: "Middleware verifies token before handler"
    
  - id: auth_004
    weight: 2
    description: "Handles token expiry"
    pass_condition: "Refresh flow or redirect to login"
```

### Data Processing / ETL
```yaml
criteria:
  - id: etl_001
    weight: 3
    description: "Handles empty input"
    pass_condition: "Returns empty result or appropriate default, no crash"
    
  - id: etl_002
    weight: 3
    description: "Handles malformed records"
    pass_condition: "Skips or logs bad records, doesn't fail entire job"
    
  - id: etl_003
    weight: 2
    description: "Idempotent"
    pass_condition: "Running twice produces same result"
    
  - id: etl_004
    weight: 2
    description: "Progress reporting"
    pass_condition: "Logs or emits progress for long operations"
```

---

## Configuration

Default settings (can be overridden by user):

```yaml
max_iterations: 5
pass_threshold: 0.85
critical_required: true
show_rubric_first: true  # Ask for approval before coding
verbose_scoring: true    # Show evidence for each criterion
```

---

## Example Session

**User:** Implement a function to parse CSV files with error handling

**Claude Code:**
```
📋 **Generated Rubric** for: CSV parser with error handling

**Critical:**
- [ ] csv_001: Handles files with different delimiters (comma, tab, semicolon)
- [ ] csv_002: Handles quoted fields containing delimiters
- [ ] csv_003: Handles empty file gracefully

**High Priority:**
- [ ] csv_004: Reports line number for parse errors
- [ ] csv_005: Handles files with/without headers

**Standard:**
- [ ] csv_006: Supports streaming for large files

Pass threshold: 85% | Max iterations: 5

👉 Should I proceed with this rubric?
```

**User:** Yes, but add handling for different encodings

**Claude Code:**
```
Added criterion:
- [ ] csv_007 (weight: 2): Handles UTF-8 and Latin-1 encodings

Proceeding with implementation...

🔄 Iteration 1/5...
[Shows code]

📊 Scoring:
✓ csv_001: Uses delimiter parameter with auto-detect
✓ csv_002: Uses csv module which handles quoting
✓ csv_003: Returns empty list for empty file
✓ csv_004: Catches exceptions with line context
✓ csv_005: header=True/False parameter
✗ csv_006: Reads entire file into memory
✓ csv_007: encoding parameter, tries UTF-8 then Latin-1

Score: 0.88 (6/7 passed, all critical passed)

✅ Rubric passed! Final score: 88%
```
