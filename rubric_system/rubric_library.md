# Rubric Library

A curated collection of high-quality rubrics for common coding tasks. Each rubric includes:
- Criteria with weights and pass conditions
- Example scoring scenarios (pass/fail with evidence)
- Common failure patterns to watch for

---

## How to Use This Library

1. **Find a matching template** for your task type
2. **Adapt criteria** to your specific context
3. **Review example scorings** to calibrate your expectations
4. **Add task-specific criteria** as needed

Templates are organized by domain:
- [API Development](#api-development)
- [Authentication & Security](#authentication--security)
- [Database Operations](#database-operations)
- [React/Frontend Components](#reactfrontend-components)
- [Data Processing / ETL](#data-processing--etl)
- [CLI Tools](#cli-tools)
- [Testing](#testing)
- [Infrastructure / DevOps](#infrastructure--devops)

---

## API Development

### Template: REST Endpoint

```yaml
rubric:
  id: "api_rest_endpoint"
  version: "1.0"
  task_pattern: "Implement * endpoint|Create * API|Add * route"
  
  criteria:
    - id: api_status
      weight: 3
      category: correctness
      description: "Returns appropriate HTTP status codes"
      pass_condition: |
        - 200/201 for success
        - 400 for invalid input
        - 401 for missing auth
        - 403 for insufficient permissions
        - 404 for not found
        - 500 only for unexpected errors
      
    - id: api_validation
      weight: 3
      category: security
      description: "Validates all input before processing"
      pass_condition: |
        - Request body validated against schema
        - Query params validated for type/range
        - Path params validated
        - Validation errors return 400 with field-level messages
      
    - id: api_auth
      weight: 3
      category: security
      description: "Authentication enforced on protected endpoints"
      pass_condition: |
        - Auth middleware runs before handler
        - Token/session validated
        - User context available in handler
      
    - id: api_error_handling
      weight: 2
      category: error_handling
      description: "Errors handled gracefully with useful messages"
      pass_condition: |
        - All async operations in try/catch
        - Error responses include message and code
        - Stack traces not leaked to client
        - Errors logged server-side
      
    - id: api_response_format
      weight: 2
      category: functionality
      description: "Response format is consistent and documented"
      pass_condition: |
        - JSON responses with consistent structure
        - Pagination metadata for list endpoints
        - HATEOAS links where appropriate
      
    - id: api_idempotency
      weight: 1
      category: correctness
      description: "Idempotent operations are safe to retry"
      pass_condition: |
        - PUT/DELETE operations idempotent
        - POST with idempotency key support (optional)
```

#### Example Scoring: User Registration Endpoint

**Code Under Review:**
```typescript
app.post('/users', async (req, res) => {
  const { email, password, name } = req.body;
  
  if (!email || !password) {
    return res.status(400).json({ error: 'Missing fields' });
  }
  
  const user = await User.create({ email, password: hash(password), name });
  res.json(user);
});
```

**Scoring:**
| Criterion | Pass | Evidence |
|-----------|------|----------|
| api_status | ✗ | Returns 200 for creation (should be 201). No 409 for duplicate email. |
| api_validation | ✗ | Only checks presence, not format. No email regex, no password strength. Error message not field-specific. |
| api_auth | N/A | Registration endpoint, auth not required |
| api_error_handling | ✗ | No try/catch around User.create. DB errors will crash. |
| api_response_format | ✗ | Returns full user object including password hash |
| api_idempotency | ✗ | Duplicate email would throw DB error, not handled |

**Score: 0/15 (0%)** — All criteria failed

**Fixed Version:**
```typescript
app.post('/users', 
  validateBody(userSchema),  // Zod schema validation
  async (req, res) => {
    try {
      const { email, password, name } = req.body;
      
      const existing = await User.findByEmail(email);
      if (existing) {
        return res.status(409).json({ 
          error: 'email_exists',
          message: 'An account with this email already exists' 
        });
      }
      
      const user = await User.create({ 
        email, 
        password: await hash(password), 
        name 
      });
      
      res.status(201).json({
        id: user.id,
        email: user.email,
        name: user.name,
        createdAt: user.createdAt
      });
    } catch (err) {
      logger.error('User creation failed', { error: err, email: req.body.email });
      res.status(500).json({ error: 'internal_error', message: 'Unable to create account' });
    }
  }
);
```

**Rescoring:**
| Criterion | Pass | Evidence |
|-----------|------|----------|
| api_status | ✓ | 201 for success, 409 for duplicate, 500 for errors |
| api_validation | ✓ | Zod schema validates all fields before handler |
| api_auth | N/A | Registration endpoint |
| api_error_handling | ✓ | try/catch, logging, generic client message |
| api_response_format | ✓ | Returns only safe fields, consistent structure |
| api_idempotency | ✓ | Duplicate email returns 409, safe to retry |

**Score: 12/12 (100%)** — All applicable criteria passed

---

## Authentication & Security

### Template: OAuth2/OIDC Implementation

```yaml
rubric:
  id: "auth_oauth2"
  version: "1.0"
  task_pattern: "Implement OAuth|Add * authentication|PKCE|SSO"
  
  criteria:
    - id: auth_secrets
      weight: 3
      category: security
      description: "Secrets never hardcoded or logged"
      pass_condition: |
        - Client secrets from env vars or secret manager
        - No secrets in code, comments, or logs
        - No secrets in URLs or query params
      
    - id: auth_token_storage
      weight: 3
      category: security
      description: "Tokens stored securely"
      pass_condition: |
        - Access tokens: httpOnly cookie or secure memory
        - Refresh tokens: httpOnly cookie with strict path
        - Never in localStorage for sensitive apps
        - Never in URL parameters
      
    - id: auth_pkce
      weight: 3
      category: security
      description: "PKCE implemented correctly (if applicable)"
      pass_condition: |
        - Code verifier: crypto-random, 43-128 chars
        - Code challenge: SHA256(verifier), base64url encoded
        - Verifier stored securely during flow
        - Verifier sent with token exchange
      
    - id: auth_state
      weight: 3
      category: security
      description: "State parameter prevents CSRF"
      pass_condition: |
        - Random state generated per auth request
        - State validated on callback
        - State bound to user session
      
    - id: auth_token_validation
      weight: 3
      category: correctness
      description: "Tokens validated before use"
      pass_condition: |
        - Signature verified
        - Expiration checked
        - Issuer/audience validated
        - Token not revoked (if revocation supported)
      
    - id: auth_refresh
      weight: 2
      category: functionality
      description: "Token refresh handled gracefully"
      pass_condition: |
        - Refresh before expiry (not just on 401)
        - Concurrent requests don't trigger multiple refreshes
        - Refresh failure redirects to login
      
    - id: auth_logout
      weight: 2
      category: functionality
      description: "Logout clears all auth state"
      pass_condition: |
        - Tokens cleared from storage
        - Server-side session invalidated
        - Redirect to appropriate page
```

#### Example Scoring: Mobile App PKCE Flow

**Code Under Review:**
```javascript
async function login() {
  const verifier = Math.random().toString(36).substring(2);
  const challenge = btoa(verifier);
  
  localStorage.setItem('verifier', verifier);
  
  const authUrl = `https://auth.example.com/authorize?
    client_id=${CLIENT_ID}
    &redirect_uri=${REDIRECT_URI}
    &code_challenge=${challenge}
    &code_challenge_method=plain`;
    
  window.location.href = authUrl;
}

async function handleCallback(code) {
  const verifier = localStorage.getItem('verifier');
  
  const response = await fetch('https://auth.example.com/token', {
    method: 'POST',
    body: JSON.stringify({
      code,
      verifier,
      client_id: CLIENT_ID,
      client_secret: 'sk_live_abc123'  // For mobile app
    })
  });
  
  const { access_token, refresh_token } = await response.json();
  localStorage.setItem('access_token', access_token);
  localStorage.setItem('refresh_token', refresh_token);
}
```

**Scoring:**
| Criterion | Pass | Evidence |
|-----------|------|----------|
| auth_secrets | ✗ | Client secret hardcoded in code (`'sk_live_abc123'`). Mobile apps shouldn't have client secrets. |
| auth_token_storage | ✗ | Both tokens in localStorage. Refresh token especially sensitive. |
| auth_pkce | ✗ | Verifier uses Math.random (not crypto). Challenge is plain base64 not SHA256. Method is 'plain' not 'S256'. |
| auth_state | ✗ | No state parameter at all. CSRF vulnerable. |
| auth_token_validation | ? | Not shown in code, can't evaluate |
| auth_refresh | ? | Not shown in code |
| auth_logout | ? | Not shown in code |

**Score: 0/12 (0%)** for implemented criteria — Critical security failures

**Common Failure Patterns for OAuth:**
1. Using Math.random() instead of crypto.getRandomValues()
2. Plain challenge method instead of S256
3. Storing verifier/tokens in localStorage
4. Including client secrets in mobile/SPA apps
5. Missing state parameter
6. Not validating state on callback

---

## Database Operations

### Template: Database Migration

```yaml
rubric:
  id: "db_migration"
  version: "1.0"
  task_pattern: "migration|alter table|add column|schema change"
  
  criteria:
    - id: db_reversible
      weight: 3
      category: correctness
      description: "Migration is fully reversible"
      pass_condition: |
        - Down migration restores exact previous state
        - Data preservation strategy for destructive changes
        - Tested both directions
      
    - id: db_no_data_loss
      weight: 3
      category: data_integrity
      description: "No data loss for existing records"
      pass_condition: |
        - Column drops only after data migrated elsewhere
        - NOT NULL only with DEFAULT or backfill
        - Type changes preserve all values
      
    - id: db_locks
      weight: 3
      category: performance
      description: "Avoids long-running locks on large tables"
      pass_condition: |
        - No ALTER TABLE on tables > 1M rows without strategy
        - Uses online DDL or pt-online-schema-change
        - Index creation is CONCURRENTLY (Postgres)
      
    - id: db_idempotent
      weight: 2
      category: correctness
      description: "Migration is idempotent"
      pass_condition: |
        - IF NOT EXISTS for creates
        - IF EXISTS for drops
        - Safe to run multiple times
      
    - id: db_foreign_keys
      weight: 2
      category: data_integrity
      description: "Foreign key relationships maintained"
      pass_condition: |
        - New FKs have valid references
        - Cascading behavior explicitly specified
        - Orphan records handled before adding FK
```

#### Example Scoring: Add User Role Column

**Code Under Review:**
```sql
-- up.sql
ALTER TABLE users ADD COLUMN role VARCHAR(50) NOT NULL;
CREATE INDEX idx_users_role ON users(role);

-- down.sql  
ALTER TABLE users DROP COLUMN role;
```

**Scoring:**
| Criterion | Pass | Evidence |
|-----------|------|----------|
| db_reversible | ✓ | Down migration drops the column |
| db_no_data_loss | ✗ | NOT NULL without DEFAULT will fail for existing rows |
| db_locks | ✗ | ALTER TABLE + CREATE INDEX could lock large table. No CONCURRENTLY. |
| db_idempotent | ✗ | No IF NOT EXISTS, will fail on re-run |
| db_foreign_keys | N/A | No FK in this migration |

**Score: 3/11 (27%)**

**Fixed Version:**
```sql
-- up.sql
ALTER TABLE users ADD COLUMN IF NOT EXISTS role VARCHAR(50);
UPDATE users SET role = 'member' WHERE role IS NULL;
ALTER TABLE users ALTER COLUMN role SET NOT NULL;
ALTER TABLE users ALTER COLUMN role SET DEFAULT 'member';
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_users_role ON users(role);

-- down.sql
DROP INDEX CONCURRENTLY IF EXISTS idx_users_role;
ALTER TABLE users DROP COLUMN IF EXISTS role;
```

**Score: 11/11 (100%)**

---

## React/Frontend Components

### Template: Data-Fetching Component

```yaml
rubric:
  id: "react_data_component"
  version: "1.0"
  task_pattern: "React component|fetch data|display * list|* page"
  
  criteria:
    - id: react_loading
      weight: 3
      category: functionality
      description: "Loading state handled"
      pass_condition: |
        - Shows loading indicator during fetch
        - Prevents interaction while loading (if needed)
        - Loading state clears on success or error
      
    - id: react_error
      weight: 3
      category: error_handling
      description: "Error state handled gracefully"
      pass_condition: |
        - Catches fetch/render errors
        - Shows user-friendly error message
        - Offers retry option
        - Doesn't crash the app (Error Boundary or try/catch)
      
    - id: react_empty
      weight: 2
      category: functionality
      description: "Empty state handled"
      pass_condition: |
        - Distinguishes "no results" from "error"
        - Shows helpful empty state message
        - Suggests action if appropriate
      
    - id: react_types
      weight: 2
      category: code_quality
      description: "Props and state properly typed"
      pass_condition: |
        - TypeScript interface for props
        - Types for API response data
        - No 'any' types (or justified exceptions)
      
    - id: react_cleanup
      weight: 2
      category: correctness
      description: "Cleanup on unmount"
      pass_condition: |
        - Aborts in-flight requests on unmount
        - Clears timers/intervals
        - No state updates after unmount
      
    - id: react_a11y
      weight: 1
      category: accessibility
      description: "Accessible to screen readers"
      pass_condition: |
        - Semantic HTML elements
        - ARIA labels where needed
        - Focus management for dynamic content
        - Loading state announced
```

#### Example Scoring: User List Component

**Code Under Review:**
```tsx
function UserList() {
  const [users, setUsers] = useState([]);
  
  useEffect(() => {
    fetch('/api/users')
      .then(r => r.json())
      .then(data => setUsers(data));
  }, []);
  
  return (
    <div>
      {users.map(user => (
        <div key={user.id}>{user.name}</div>
      ))}
    </div>
  );
}
```

**Scoring:**
| Criterion | Pass | Evidence |
|-----------|------|----------|
| react_loading | ✗ | No loading state. Renders empty div during fetch. |
| react_error | ✗ | No .catch() on fetch. Network error crashes silently. |
| react_empty | ✗ | Empty array renders nothing. No "no users" message. |
| react_types | ✗ | No TypeScript types. `users` is `any[]`. |
| react_cleanup | ✗ | No AbortController. State update after unmount possible. |
| react_a11y | ✗ | Using div for list (should be ul/li). No ARIA. |

**Score: 0/13 (0%)**

**Fixed Version:**
```tsx
interface User {
  id: string;
  name: string;
  email: string;
}

interface UserListProps {
  roleFilter?: string;
}

function UserList({ roleFilter }: UserListProps) {
  const [users, setUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  
  useEffect(() => {
    const controller = new AbortController();
    
    async function fetchUsers() {
      try {
        setLoading(true);
        setError(null);
        
        const response = await fetch('/api/users', { 
          signal: controller.signal 
        });
        
        if (!response.ok) {
          throw new Error('Failed to load users');
        }
        
        const data = await response.json();
        setUsers(data);
      } catch (err) {
        if (err.name !== 'AbortError') {
          setError(err.message || 'Something went wrong');
        }
      } finally {
        setLoading(false);
      }
    }
    
    fetchUsers();
    return () => controller.abort();
  }, [roleFilter]);
  
  if (loading) {
    return (
      <div role="status" aria-live="polite">
        <span className="sr-only">Loading users...</span>
        <Spinner />
      </div>
    );
  }
  
  if (error) {
    return (
      <div role="alert">
        <p>Error: {error}</p>
        <button onClick={() => window.location.reload()}>
          Retry
        </button>
      </div>
    );
  }
  
  if (users.length === 0) {
    return (
      <div role="status">
        <p>No users found.</p>
      </div>
    );
  }
  
  return (
    <ul aria-label="User list">
      {users.map(user => (
        <li key={user.id}>
          <span>{user.name}</span>
          <span className="sr-only"> - {user.email}</span>
        </li>
      ))}
    </ul>
  );
}
```

**Score: 13/13 (100%)**

---

## Data Processing / ETL

### Template: Data Transformation Pipeline

```yaml
rubric:
  id: "etl_pipeline"
  version: "1.0"
  task_pattern: "process * data|transform|ETL|import|export|parse"
  
  criteria:
    - id: etl_empty_input
      weight: 3
      category: correctness
      description: "Handles empty input gracefully"
      pass_condition: |
        - Empty file/array returns empty result
        - Doesn't throw on empty input
        - Logs or reports empty input if relevant
      
    - id: etl_malformed
      weight: 3
      category: error_handling
      description: "Handles malformed records"
      pass_condition: |
        - Invalid records skipped or quarantined
        - Doesn't fail entire job on one bad record
        - Reports which records failed and why
      
    - id: etl_idempotent
      weight: 3
      category: correctness
      description: "Processing is idempotent"
      pass_condition: |
        - Running twice produces same output
        - Uses upsert or deduplication
        - Handles partial failures gracefully
      
    - id: etl_progress
      weight: 2
      category: functionality
      description: "Reports progress for large datasets"
      pass_condition: |
        - Progress logged/emitted periodically
        - Includes records processed / total
        - Estimated time remaining (optional)
      
    - id: etl_memory
      weight: 2
      category: performance
      description: "Memory-efficient for large datasets"
      pass_condition: |
        - Streams or batches instead of loading all in memory
        - Bounded memory usage regardless of input size
      
    - id: etl_validation
      weight: 2
      category: correctness
      description: "Output data validated"
      pass_condition: |
        - Schema validation on output
        - Counts reconciled (input vs output)
        - Critical fields never null
```

#### Example Scoring: CSV Import Script

**Code Under Review:**
```python
import csv

def import_users(filename):
    with open(filename) as f:
        reader = csv.DictReader(f)
        users = list(reader)
    
    for user in users:
        db.execute(
            "INSERT INTO users (email, name) VALUES (?, ?)",
            (user['email'], user['name'])
        )
    
    return len(users)
```

**Scoring:**
| Criterion | Pass | Evidence |
|-----------|------|----------|
| etl_empty_input | ✓ | Empty file returns empty list, processes 0 records |
| etl_malformed | ✗ | KeyError if 'email' or 'name' missing. Crashes on first bad row. |
| etl_idempotent | ✗ | INSERT will fail on duplicate. No upsert. |
| etl_progress | ✗ | No progress reporting |
| etl_memory | ✗ | `list(reader)` loads entire file into memory |
| etl_validation | ✗ | No validation of email format or required fields |

**Score: 3/15 (20%)**

**Fixed Version:**
```python
import csv
import logging
from dataclasses import dataclass
from typing import Iterator
import re

logger = logging.getLogger(__name__)

@dataclass
class ImportResult:
    total: int
    imported: int
    skipped: int
    errors: list[dict]

def validate_email(email: str) -> bool:
    return bool(re.match(r'^[^@]+@[^@]+\.[^@]+$', email))

def import_users(filename: str, batch_size: int = 1000) -> ImportResult:
    result = ImportResult(total=0, imported=0, skipped=0, errors=[])
    
    def process_batch(batch: list[dict]):
        for row in batch:
            try:
                email = row.get('email', '').strip()
                name = row.get('name', '').strip()
                
                if not email or not name:
                    result.errors.append({
                        'row': result.total,
                        'reason': 'Missing required field',
                        'data': row
                    })
                    result.skipped += 1
                    continue
                
                if not validate_email(email):
                    result.errors.append({
                        'row': result.total,
                        'reason': 'Invalid email format',
                        'data': row
                    })
                    result.skipped += 1
                    continue
                
                db.execute("""
                    INSERT INTO users (email, name) VALUES (?, ?)
                    ON CONFLICT (email) DO UPDATE SET name = ?
                """, (email, name, name))
                
                result.imported += 1
                
            except Exception as e:
                result.errors.append({
                    'row': result.total,
                    'reason': str(e),
                    'data': row
                })
                result.skipped += 1
    
    with open(filename) as f:
        reader = csv.DictReader(f)
        batch = []
        
        for row in reader:
            result.total += 1
            batch.append(row)
            
            if len(batch) >= batch_size:
                process_batch(batch)
                batch = []
                logger.info(f"Progress: {result.total} rows processed, "
                           f"{result.imported} imported, {result.skipped} skipped")
        
        if batch:
            process_batch(batch)
    
    logger.info(f"Import complete: {result.imported}/{result.total} imported")
    
    if result.errors:
        logger.warning(f"Errors: {len(result.errors)} rows failed")
    
    return result
```

**Score: 15/15 (100%)**

---

## CLI Tools

### Template: Command-Line Tool

```yaml
rubric:
  id: "cli_tool"
  version: "1.0"
  task_pattern: "CLI|command line|script|tool"
  
  criteria:
    - id: cli_help
      weight: 2
      category: functionality
      description: "Help text explains usage"
      pass_condition: |
        - --help flag works
        - Shows all options with descriptions
        - Includes examples
      
    - id: cli_args
      weight: 2
      category: correctness
      description: "Arguments validated"
      pass_condition: |
        - Required args enforced
        - Types validated
        - Clear error message for invalid args
      
    - id: cli_exit_codes
      weight: 2
      category: correctness
      description: "Exit codes indicate success/failure"
      pass_condition: |
        - 0 for success
        - Non-zero for failure
        - Different codes for different error types (optional)
      
    - id: cli_errors
      weight: 2
      category: error_handling
      description: "Errors reported clearly"
      pass_condition: |
        - User-friendly error messages
        - Stack traces only with --verbose
        - Suggests fix when possible
      
    - id: cli_stdin
      weight: 1
      category: functionality
      description: "Supports stdin/stdout piping"
      pass_condition: |
        - Can read from stdin (- or piped input)
        - Output suitable for piping
        - No extraneous output to stdout
```

---

## Testing

### Template: Unit Test Suite

```yaml
rubric:
  id: "test_suite"
  version: "1.0"
  task_pattern: "write tests|test *|unit test|spec"
  
  criteria:
    - id: test_coverage
      weight: 2
      category: correctness
      description: "Key paths covered"
      pass_condition: |
        - Happy path tested
        - Error cases tested
        - Edge cases tested
      
    - id: test_isolation
      weight: 3
      category: correctness
      description: "Tests are isolated"
      pass_condition: |
        - No shared mutable state
        - Each test can run independently
        - Order doesn't matter
      
    - id: test_assertions
      weight: 2
      category: correctness
      description: "Assertions are meaningful"
      pass_condition: |
        - Tests assert specific outcomes
        - No "assert true" without condition
        - Error messages helpful on failure
      
    - id: test_mocking
      weight: 2
      category: correctness
      description: "External dependencies mocked"
      pass_condition: |
        - Network calls mocked
        - Database mocked or uses test DB
        - Time/randomness controlled when relevant
      
    - id: test_naming
      weight: 1
      category: code_quality
      description: "Tests clearly named"
      pass_condition: |
        - Names describe behavior tested
        - "should..." or "when... then..." format
        - Grouped by feature/component
```

---

## Infrastructure / DevOps

### Template: CI/CD Pipeline

```yaml
rubric:
  id: "cicd_pipeline"
  version: "1.0"
  task_pattern: "CI|CD|pipeline|GitHub Action|deployment"
  
  criteria:
    - id: ci_secrets
      weight: 3
      category: security
      description: "Secrets handled securely"
      pass_condition: |
        - Secrets from secret manager, not env vars in code
        - No secrets in logs
        - Secrets not echoed in script output
      
    - id: ci_caching
      weight: 2
      category: performance
      description: "Dependencies cached"
      pass_condition: |
        - Node modules / pip packages cached
        - Cache key includes lockfile hash
        - Cache invalidation works correctly
      
    - id: ci_fail_fast
      weight: 2
      category: correctness
      description: "Fails fast on errors"
      pass_condition: |
        - Set -e or equivalent
        - Step failures stop pipeline
        - Clear indication of what failed
      
    - id: ci_idempotent
      weight: 2
      category: correctness
      description: "Pipeline is idempotent"
      pass_condition: |
        - Re-running produces same result
        - No side effects from failed runs
        - Deployments can be rolled back
```

---

## Using These Templates

### Programmatic Access

```python
from rubric_library import get_template, adapt_template

# Get a template
template = get_template("api_rest_endpoint")

# Adapt for specific task
rubric = adapt_template(template, 
    task="Create user registration endpoint",
    context="Express.js API with Postgres",
    additions=[{
        "id": "custom_001",
        "weight": 2,
        "description": "Sends welcome email after registration",
        "pass_condition": "Email queued with correct template"
    }],
    removals=["api_idempotency"]  # Not needed for this endpoint
)
```

### Template Selection Heuristics

| If task contains... | Use template |
|--------------------|--------------|
| endpoint, API, route | api_rest_endpoint |
| OAuth, auth, login, PKCE | auth_oauth2 |
| migration, ALTER, schema | db_migration |
| React, component, page | react_data_component |
| import, export, ETL, CSV | etl_pipeline |
| CLI, command, script | cli_tool |
| test, spec, unit | test_suite |
| CI, CD, pipeline, deploy | cicd_pipeline |
| design, UI, frontend, landing page, dashboard, app design | frontend_design |
| research, report, analysis, whitepaper, brief, document | knowledge_work_research |

---

## Knowledge Work Research Documents

### Template: Research Document

```yaml
rubric:
  id: "knowledge_work_research"
  version: "1.0"
  task_pattern: "research|report|analysis|whitepaper|brief|document|write.*about"
  
  criteria:
    # SOURCE QUALITY
    - id: src_001
      weight: 3
      category: source_quality
      description: "Source authority - sources from credible entities"
      pass_condition: |
        - Primary sources are peer-reviewed, official data, or recognized experts
        - Author credentials identifiable and relevant
        - No anonymous blogs or content farms for key claims
    
    - id: src_002
      weight: 3
      category: source_quality
      description: "Source relevance - sources directly address claims"
      pass_condition: |
        - Each source directly supports its cited claim
        - No tangential sources padding citation count
        - No citation drift
    
    - id: src_003
      weight: 3
      category: source_quality
      description: "Source currency - appropriately recent for domain"
      pass_condition: |
        - Fast-changing domains (AI, markets): <2 years
        - Medium domains (science, business): <5 years
        - Slow domains (history, theory): age-appropriate
        - Older sources explicitly justified
    
    - id: src_004
      weight: 2
      category: source_quality
      description: "Source diversity - multiple independent source types"
      pass_condition: |
        - Minimum 3 source types (academic, industry, govt, etc.)
        - No single org provides >40% of sources
        - Conflicting viewpoints acknowledged
    
    - id: src_005
      weight: 3
      category: source_quality
      description: "Source triangulation - key claims validated by multiple sources"
      pass_condition: |
        - Tier 1 claims (headline): 3+ independent sources
        - Tier 2 claims (supporting): 2+ independent sources
        - Tier 3 claims (background): 1 authoritative source OK
        - Sources genuinely independent

    # EVIDENCE & CLAIMS
    - id: evd_001
      weight: 3
      category: evidence
      description: "Claim-evidence alignment - every claim supported"
      pass_condition: |
        - No unsupported factual assertions
        - Evidence type matches claim type
        - Reader can trace claims to evidence
    
    - id: evd_002
      weight: 3
      category: evidence
      description: "Evidence strength calibration"
      pass_condition: |
        - Strong claims backed by strong evidence
        - Hedging language matches evidence quality
        - No overstatement beyond evidence support
    
    - id: evd_003
      weight: 2
      category: evidence
      description: "Counter-evidence acknowledged"
      pass_condition: |
        - Conflicting data addressed
        - Limitations noted
        - No cherry-picking favorable evidence
    
    - id: evd_004
      weight: 3
      category: evidence
      description: "Statistical rigor"
      pass_condition: |
        - Sample sizes reported
        - Confidence intervals included
        - Correlation not implied as causation

    # DATA VISUALIZATIONS
    - id: viz_001
      weight: 3
      category: visualization
      description: "Visualization accuracy"
      pass_condition: |
        - Y-axis starts at zero (or break indicated)
        - Scales linear unless log explicitly labeled
        - No distorting 3D effects
    
    - id: viz_002
      weight: 3
      category: visualization
      description: "Visualization clarity"
      pass_condition: |
        - Declarative title (not just "Sales by Region")
        - All axes labeled with units
        - Color-blind safe palette
        - WCAG 2.0 AA contrast (4.5:1)
    
    - id: viz_003
      weight: 2
      category: visualization
      description: "Appropriate chart selection"
      pass_condition: |
        - Comparison → bar chart
        - Trend → line chart
        - Part-to-whole → stacked bar (not pie >5 cats)
        - Distribution → histogram/box plot

    # FORWARD-LOOKING STATEMENTS
    - id: fwd_001
      weight: 3
      category: predictions
      description: "Hypothesis framing - predictions distinguished from facts"
      pass_condition: |
        - Future statements labeled as predictions
        - Confidence level indicated
        - Time horizon specified
        - Conditional language used
    
    - id: fwd_002
      weight: 3
      category: predictions
      description: "Assumption transparency"
      pass_condition: |
        - Key assumptions explicitly listed
        - Assumptions testable/falsifiable
        - Sensitivity analysis provided
    
    - id: fwd_003
      weight: 3
      category: predictions
      description: "Uncertainty quantification"
      pass_condition: |
        - Point estimates with ranges (CIs, scenarios)
        - Multiple scenarios for high-uncertainty predictions
        - Tail risks acknowledged

    # STRUCTURE
    - id: str_001
      weight: 3
      category: structure
      description: "Executive summary quality"
      pass_condition: |
        - BLUF in first paragraph
        - All major conclusions in summary
        - Summary stands alone
    
    - id: str_002
      weight: 3
      category: structure
      description: "Logical flow"
      pass_condition: |
        - Claims build without circular reasoning
        - Background precedes analysis
        - Evidence before conclusions

    # POLISH
    - id: pol_001
      weight: 3
      category: polish
      description: "Writing quality"
      pass_condition: |
        - No grammar/spelling errors
        - Clear, professional prose
        - Consistent terminology

  thresholds:
    pass_score: 0.85
    critical_required: true
```

**Max Score: 74 points** (see full rubric for detailed breakdown)

**Claim Triangulation Requirements:**
| Claim Tier | Description | Min Sources |
|------------|-------------|-------------|
| Tier 1 | Central thesis, key stats, controversial | 3 |
| Tier 2 | Supporting evidence, secondary data | 2 |
| Tier 3 | Background facts, established consensus | 1 |

**Source Currency by Domain:**
| Domain | Max Age |
|--------|---------|
| AI/ML, crypto | 12 months |
| Tech, markets | 24 months |
| Medicine, science | 36 months |
| Business strategy | 48 months |

For the complete rubric with all 28 criteria, examples, and detailed scoring guidance, see `knowledge_work_rubric.md`.

---

## Frontend Design (Web & Mobile)

### Template: Modern Frontend Design

```yaml
rubric:
  id: "frontend_design_2026"
  version: "1.0"
  task_pattern: "design|UI|frontend|app|component|landing page|dashboard"
  
  criteria:
    # COLOR SYSTEM
    - id: color_001
      weight: 3
      category: visual_design
      description: "Color palette is intentional, modern, and avoids AI clichés"
      pass_condition: |
        - NOT using default purple (#8B5CF6, #7C3AED, #6366F1, or similar)
        - Primary color is distinctive and purposeful
        - Palette follows 60-30-10 rule (dominant-secondary-accent)
        - Colors have semantic meaning (success=green, error=red, warning=amber)
        - Maximum 5-6 colors in active palette (excluding grays)
      
    - id: color_002
      weight: 3
      category: accessibility
      description: "Color contrast meets WCAG 2.1 AA standards"
      pass_condition: |
        - Body text: minimum 4.5:1 contrast ratio
        - Large text (18px+ or 14px bold): minimum 3:1 ratio
        - Interactive elements clearly distinguishable
        - Information not conveyed by color alone
      
    - id: color_003
      weight: 2
      category: visual_design
      description: "Uses modern color trends appropriately"
      pass_condition: |
        - Warm neutrals over stark whites (#F0EEE9 not #FFFFFF)
        - Off-blacks (#1A1A1A, #0F0F0F) instead of pure black
        - Gradients are subtle/ambient, not rainbow
    
    # TYPOGRAPHY
    - id: type_001
      weight: 3
      category: typography
      description: "Typography hierarchy is clear and consistent"
      pass_condition: |
        - Clear distinction between H1, H2, H3, body, caption
        - Size ratio between levels is noticeable (1.2-1.5x)
        - Maximum 2 font families (ideally 1 with multiple weights)
        - Line height 1.4-1.6x for body text
      
    - id: type_002
      weight: 3
      category: typography
      description: "Font choices are modern and readable"
      pass_condition: |
        - Uses modern sans-serif (Inter, SF Pro, DM Sans, Satoshi, Geist)
        - OR intentional serif choice for brand personality
        - Font renders well at all sizes (14px minimum for body)
      
    - id: type_003
      weight: 2
      category: typography
      description: "Typography feels intentional and branded"
      pass_condition: |
        - Headlines make visual impact (bold weights, appropriate size)
        - Consistent letter-spacing
        - Text alignment is intentional
    
    # SPACING & LAYOUT
    - id: space_001
      weight: 3
      category: layout
      description: "Spacing follows 8px grid system consistently"
      pass_condition: |
        - All spacing values are multiples of 8 (8, 16, 24, 32, 40, 48...)
        - 4px used only for micro-adjustments
        - No arbitrary values (13px, 17px, 22px)
        - Internal padding ≤ external margins
      
    - id: space_002
      weight: 3
      category: layout
      description: "Visual hierarchy through spacing"
      pass_condition: |
        - Related elements grouped closer (8-16px)
        - Unrelated elements have clear separation (24-48px)
        - Sections have breathing room (48-96px)
        - Gestalt principles applied (proximity, similarity)
      
    - id: space_003
      weight: 2
      category: layout
      description: "Layout adapts to content and context"
      pass_condition: |
        - Cards/containers have consistent padding (16-24px)
        - Responsive breakpoints handle edge cases
        - Content doesn't feel cramped OR lost in space
    
    # COMPONENTS & PATTERNS
    - id: comp_001
      weight: 2
      category: components
      description: "Interactive elements are clearly tappable/clickable"
      pass_condition: |
        - Touch targets minimum 44x44px (iOS) or 48dp (Android)
        - Buttons have clear affordance
        - Hover/focus/active states defined
        - Disabled states visually distinct
      
    - id: comp_002
      weight: 2
      category: components
      description: "Navigation is intuitive and consistent"
      pass_condition: |
        - Bottom navigation for mobile primary actions (max 5 items)
        - Current location clearly indicated
        - Back/close actions easily accessible
      
    - id: comp_003
      weight: 2
      category: components
      description: "Forms and inputs are user-friendly"
      pass_condition: |
        - Input fields have visible boundaries
        - Labels are visible (not just placeholders)
        - Error states are clear with helpful messages
        - Focus states are obvious
    
    # VISUAL POLISH
    - id: polish_001
      weight: 1
      category: visual_design
      description: "Consistent visual language throughout"
      pass_condition: |
        - Border radius consistent
        - Shadow depth consistent (elevation system)
        - Icon style unified
      
    - id: polish_002
      weight: 1
      category: visual_design
      description: "Micro-interactions and feedback present"
      pass_condition: |
        - Loading states for async operations
        - Success/error feedback on actions
        - Transitions are smooth (200-300ms)
      
    - id: polish_003
      weight: 1
      category: visual_design
      description: "Dark mode support (if applicable)"
      pass_condition: |
        - Not just inverted colors
        - Backgrounds use dark grays, not pure black
        - Reduced saturation on colors
    
    # ACCESSIBILITY
    - id: a11y_001
      weight: 2
      category: accessibility
      description: "Screen reader compatibility"
      pass_condition: |
        - Semantic HTML structure
        - Alt text for meaningful images
        - ARIA labels for interactive elements
        - Focus order is logical
      
    - id: a11y_002
      weight: 2
      category: accessibility
      description: "Keyboard and motor accessibility"
      pass_condition: |
        - All interactive elements keyboard accessible
        - Visible focus indicators
        - No keyboard traps
        - Click targets have adequate spacing

  thresholds:
    pass_score: 0.85
    critical_required: true
```

**Max Score: 37 points** (6 critical × 3 + 8 high × 2 + 3 standard × 1)

### Anti-Patterns to Avoid

**Color Anti-Patterns:**
- ❌ Default AI purple (`#8B5CF6`, `#7C3AED`, `#6366F1`)
- ❌ Pure black (`#000000`) on pure white (`#FFFFFF`)
- ❌ Saturated rainbow gradients
- ❌ Neon accents without purpose

**Layout Anti-Patterns:**
- ❌ Inconsistent spacing (random 13px, 17px gaps)
- ❌ Tiny touch targets (< 44px)
- ❌ Cards floating without clear grouping

**Typography Anti-Patterns:**
- ❌ More than 2 font families
- ❌ Thin/light weights on mobile
- ❌ Insufficient contrast (< 4.5:1)

### Example Scoring: Generic AI Dashboard

**Design:**
- Purple gradient header (#7C3AED → #6366F1)
- White background (#FFFFFF), black text (#000000)
- Random spacing (15px, 20px, 12px)
- System default font, no hierarchy

| Criterion | Pass | Evidence |
|-----------|------|----------|
| color_001 | ✗ | Uses exact "AI purple" gradient |
| color_002 | ✓ | Black on white meets contrast |
| color_003 | ✗ | Pure white/black, dated gradient |
| type_001 | ✗ | No clear hierarchy |
| type_002 | △ | System font readable but generic |
| type_003 | ✗ | No brand personality |
| space_001 | ✗ | 15px, 20px — not on 8px grid |
| space_002 | ✗ | Elements don't group logically |
| space_003 | ✗ | Inconsistent padding |
| comp_001 | ✓ | Buttons tappable size |
| comp_002 | ✓ | Basic navigation present |
| comp_003 | △ | Forms functional but bland |
| polish_001 | ✗ | Inconsistent border radius |
| polish_002 | ✗ | No loading states |
| polish_003 | N/A | No dark mode |
| a11y_001 | ✗ | Missing ARIA labels |
| a11y_002 | △ | Focus states weak |

**Score: 4/37 (10.8%)** — Fails critical criteria

### Example Scoring: Modern Finance App

**Design:**
- Primary: Deep teal (#0D6E6E)
- Background: Warm white (#FAFAF9)
- Text: Off-black (#1C1917)
- Accent: Coral (#F97316)
- Font: Inter with clear hierarchy
- 8px grid throughout

| Criterion | Pass | Evidence |
|-----------|------|----------|
| color_001 | ✓ | Distinctive teal, coral accent, 60-30-10 |
| color_002 | ✓ | 15.4:1 contrast ratio |
| color_003 | ✓ | Warm neutrals, sophisticated palette |
| type_001 | ✓ | H1 32px, H2 24px, Body 16px |
| type_002 | ✓ | Inter, readable at all sizes |
| type_003 | ✓ | Headlines impactful |
| space_001 | ✓ | All values 8/16/24/32/48 |
| space_002 | ✓ | Related items at 8px, sections at 48px |
| space_003 | ✓ | 16px card padding |
| comp_001 | ✓ | 48px buttons, clear states |
| comp_002 | ✓ | Bottom nav with indicator |
| comp_003 | ✓ | Labels, clear error states |
| polish_001 | ✓ | 16px radius, consistent elevation |
| polish_002 | ✓ | Skeleton loaders, 200ms transitions |
| polish_003 | ✓ | Dark mode with #0F0F0F bg |
| a11y_001 | ✓ | Proper structure, ARIA labels |
| a11y_002 | ✓ | Full keyboard nav, focus rings |

**Score: 37/37 (100%)** — Passes all criteria

### Modern Color Palettes (2025-2026)

**Warm Neutral (SaaS, Finance):**
```
Background:   #FAFAF8
Text Primary: #171717
Primary:      #0D6E6E (teal)
Accent:       #F59E0B (amber)
```

**Dark Mode Professional:**
```
Background:   #0A0A0A
Text Primary: #FAFAFA
Primary:      #3B82F6 (blue)
Accent:       #F472B6 (pink)
```

**Earthy Modern (Wellness, Eco):**
```
Background:   #F5F5F0
Text Primary: #1C1917
Primary:      #2D5A27 (forest)
Accent:       #B45309 (terra cotta)
```

### Recommended Fonts

**Free Modern Sans-Serif:**
- Inter (gold standard for UI)
- DM Sans (geometric, great small sizes)
- Satoshi (modern, sharp)
- Geist (Vercel's font, Swiss-inspired)
- Plus Jakarta Sans (friendly)

**System/Native:**
- SF Pro (iOS)
- Roboto (Android)

### Spacing Scale (8px Base)

```
4px   — micro (icon-label gap)
8px   — tight (related items)
16px  — default (component padding)
24px  — comfortable (between groups)
32px  — section gap
48px  — major section break
64px  — page section
96px  — major page break
```
