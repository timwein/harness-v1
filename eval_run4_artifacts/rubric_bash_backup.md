# Bash Backup — Rubric

**Task:** Write a bash script that backs up a PostgreSQL database to S3 with rotation, logging, and error notifications
**Domain:** bash_scripting
**Total Points:** 44
**Pass Threshold:** 85%

---

## bash_correctness

**Category:** functionality

**Description:** Script performs correct pg_dump → compress → upload → rotate pipeline

**Pass Condition:** Uses pg_dump with appropriate flags. Compresses output (gzip/zstd). Uploads to S3 with aws cli. Rotates old backups by age or count.

**Scoring Method:** WEIGHTED_COMPONENTS (max 12 pts)

| Sub-attribute | Description | Weight | Measurement |
|---|---|---|---|
| dump_command | pg_dump with correct flags (--format, --no-owner, etc.) | 0.30 | 1.0 if pg_dump with appropriate format flags, 0.5 if basic, 0.0 if wrong |
| compression | Output compressed before upload | 0.20 | 1.0 if compressed (gzip/zstd), 0.0 if raw SQL upload |
| s3_upload | aws s3 cp/sync with correct path and options | 0.25 | 1.0 if correct aws s3 cp with proper path, 0.0 if wrong |
| rotation | Deletes backups older than N days or keeps last N | 0.25 | 1.0 if implemented correctly, 0.5 if partially, 0.0 if missing |

**Pass Examples:** pg_dump -Fc | gzip > backup.gz && aws s3 cp ... && find/delete old

**Fail Examples:** pg_dump with no compression, no rotation logic

---

## bash_safety

**Category:** reliability

**Description:** Script is safe — set -euo pipefail, no secrets in code, cleanup on failure

**Pass Condition:** set -euo pipefail. Trap for cleanup. No hardcoded passwords. Uses .pgpass or env vars. Temp files cleaned up.

**Scoring Method:** PENALTY_BASED (max 10 pts)

| Penalty | Points Deducted |
|---|---|
| no_set_e | -2.0 |
| no_pipefail | -1.5 |
| hardcoded_password | -3.0 |
| no_trap_cleanup | -1.5 |
| no_temp_file_cleanup | -1.0 |
| unquoted_variables | -1.0 |
| no_lockfile | -0.5 |

**Pass Examples:** set -euo pipefail, trap cleanup EXIT, reads creds from env

**Fail Examples:** No error handling, password in script, temp files left behind

---

## bash_logging

**Category:** observability

**Description:** Comprehensive logging with timestamps and log levels

**Pass Condition:** Timestamped log function. Logs start/success/failure/rotation. Writes to file AND stdout. Includes backup size and duration.

**Scoring Method:** WEIGHTED_COMPONENTS (max 8 pts)

| Sub-attribute | Description | Weight | Measurement |
|---|---|---|---|
| log_function | Dedicated log function with timestamps | 0.30 | 1.0 if log() function with ISO timestamps, 0.5 if echo with date, 0.0 if plain echo |
| log_completeness | Logs all key events (start, size, duration, rotate, done) | 0.35 | % of key events logged |
| log_destination | Writes to both file and stdout | 0.35 | 1.0 if tee to file + stdout, 0.5 if one, 0.0 if neither |

**Pass Examples:** `log() { echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] [$1] $2" | tee -a $LOG; }`

**Fail Examples:** Random echo statements with no timestamps

---

## bash_notifications

**Category:** alerting

**Description:** Error notifications via practical channel (email, Slack, PagerDuty)

**Pass Condition:** On failure: sends notification with error details and context. Configurable notification channel. Includes backup name, error message, timestamp.

**Scoring Method:** WEIGHTED_COMPONENTS (max 8 pts)

| Sub-attribute | Description | Weight | Measurement |
|---|---|---|---|
| notification_impl | Actually sends notification on failure | 0.40 | 1.0 if implemented (curl to Slack, mail, etc.), 0.0 if TODO/placeholder |
| error_context | Notification includes useful context (timestamp, db, error) | 0.35 | 1.0 if rich context, 0.5 if basic, 0.0 if just 'backup failed' |
| configurability | Channel/endpoint configurable via env var | 0.25 | 1.0 if configurable, 0.5 if hardcoded but works, 0.0 if neither |

**Pass Examples:** Slack webhook with formatted message including db name, error, and log tail

**Fail Examples:** # TODO: add notifications

---

## bash_configurability

**Category:** usability

**Description:** Script is configurable via environment variables with sensible defaults

**Pass Condition:** Key params via env vars: DB_NAME, S3_BUCKET, RETENTION_DAYS, etc. Defaults provided. Usage/help flag. Validates required vars.

**Scoring Method:** WEIGHTED_COMPONENTS (max 6 pts)

| Sub-attribute | Description | Weight | Measurement |
|---|---|---|---|
| env_var_config | Key params from env vars with defaults | 0.40 | % of configurable params using env vars with fallback defaults |
| validation | Validates required vars exist before starting | 0.30 | 1.0 if checks all required vars, 0.5 if some, 0.0 if none |
| help_flag | --help flag with usage instructions | 0.30 | 1.0 if --help works, 0.0 if no help |

**Pass Examples:** `DB_NAME=${DB_NAME:?'DB_NAME required'}, RETENTION=${RETENTION_DAYS:-30}`

**Fail Examples:** Hardcoded db name, bucket, and retention in script body
