# Rubric: bash_scripting

**Task:** Write a bash script that backs up a PostgreSQL database to S3 with rotation, logging, and error notifications

**Domain:** bash_scripting
**Total Points:** 44
**Pass Threshold:** 85%
**Criteria Count:** 5
**Generated:** 2026-03-31 05:57:24 UTC

---

## 1. bash_correctness

**Category:** functionality
**Description:** Script performs correct pg_dump → compress → upload → rotate pipeline

**Pass Condition:** Uses pg_dump with appropriate flags. Compresses output (gzip/zstd). Uploads to S3 with aws cli. Rotates old backups by age or count.

**Scoring Method:** `weighted_components`
**Max Points:** 12

### Sub-Attributes

| Sub-ID | Weight | Description | Measurement |
|--------|--------|-------------|-------------|
| `dump_command` | 30% | pg_dump with correct flags (--format, --no-owner, etc.) | 1.0 if pg_dump with appropriate format flags, 0.5 if basic, 0.0 if wrong |
| `compression` | 20% | Output compressed before upload | 1.0 if compressed (gzip/zstd), 0.0 if raw SQL upload |
| `s3_upload` | 25% | aws s3 cp/sync with correct path and options | 1.0 if correct aws s3 cp with proper path, 0.0 if wrong |
| `rotation` | 25% | Deletes backups older than N days or keeps last N | 1.0 if implemented correctly, 0.5 if partially, 0.0 if missing |

### Pass Examples

- pg_dump -Fc | gzip > backup.gz && aws s3 cp ... && find/delete old

### Fail Examples

- pg_dump with no compression, no rotation logic

---

## 2. bash_safety

**Category:** reliability
**Description:** Script is safe — set -euo pipefail, no secrets in code, cleanup on failure

**Pass Condition:** set -euo pipefail. Trap for cleanup. No hardcoded passwords. Uses .pgpass or env vars. Temp files cleaned up.

**Scoring Method:** `penalty_based`
**Max Points:** 10

### Penalties

- **no_set_e:** -2.0 pts
- **no_pipefail:** -1.5 pts
- **hardcoded_password:** -3.0 pts
- **no_trap_cleanup:** -1.5 pts
- **no_temp_file_cleanup:** -1.0 pts
- **unquoted_variables:** -1.0 pts
- **no_lockfile:** -0.5 pts

### Pass Examples

- set -euo pipefail, trap cleanup EXIT, reads creds from env

### Fail Examples

- No error handling, password in script, temp files left behind

---

## 3. bash_logging

**Category:** observability
**Description:** Comprehensive logging with timestamps and log levels

**Pass Condition:** Timestamped log function. Logs start/success/failure/rotation. Writes to file AND stdout. Includes backup size and duration.

**Scoring Method:** `weighted_components`
**Max Points:** 8

### Sub-Attributes

| Sub-ID | Weight | Description | Measurement |
|--------|--------|-------------|-------------|
| `log_function` | 30% | Dedicated log function with timestamps | 1.0 if log() function with ISO timestamps, 0.5 if echo with date, 0.0 if plain echo |
| `log_completeness` | 35% | Logs all key events (start, size, duration, rotate, done) | % of key events logged |
| `log_destination` | 35% | Writes to both file and stdout | 1.0 if tee to file + stdout, 0.5 if one, 0.0 if neither |

### Pass Examples

- log() { echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] [$1] $2" | tee -a $LOG; }

### Fail Examples

- Random echo statements with no timestamps

---

## 4. bash_notifications

**Category:** alerting
**Description:** Error notifications via practical channel (email, Slack, PagerDuty)

**Pass Condition:** On failure: sends notification with error details and context. Configurable notification channel. Includes backup name, error message, timestamp.

**Scoring Method:** `weighted_components`
**Max Points:** 8

### Sub-Attributes

| Sub-ID | Weight | Description | Measurement |
|--------|--------|-------------|-------------|
| `notification_impl` | 40% | Actually sends notification on failure | 1.0 if implemented (curl to Slack, mail, etc.), 0.0 if TODO/placeholder |
| `error_context` | 35% | Notification includes useful context (timestamp, db, error) | 1.0 if rich context, 0.5 if basic, 0.0 if just 'backup failed' |
| `configurability` | 25% | Channel/endpoint configurable via env var | 1.0 if configurable, 0.5 if hardcoded but works, 0.0 if neither |

### Pass Examples

- Slack webhook with formatted message including db name, error, and log tail

### Fail Examples

- # TODO: add notifications

---

## 5. bash_configurability

**Category:** usability
**Description:** Script is configurable via environment variables with sensible defaults

**Pass Condition:** Key params via env vars: DB_NAME, S3_BUCKET, RETENTION_DAYS, etc. Defaults provided. Usage/help flag. Validates required vars.

**Scoring Method:** `weighted_components`
**Max Points:** 6

### Sub-Attributes

| Sub-ID | Weight | Description | Measurement |
|--------|--------|-------------|-------------|
| `env_var_config` | 40% | Key params from env vars with defaults | % of configurable params using env vars with fallback defaults |
| `validation` | 30% | Validates required vars exist before starting | 1.0 if checks all required vars, 0.5 if some, 0.0 if none |
| `help_flag` | 30% | --help flag with usage instructions | 1.0 if --help works, 0.0 if no help |

### Pass Examples

- DB_NAME=${DB_NAME:?'DB_NAME required'}, RETENTION=${RETENTION_DAYS:-30}

### Fail Examples

- Hardcoded db name, bucket, and retention in script body

---
