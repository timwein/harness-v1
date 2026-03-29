# Rubric: bash_backup

**Domain:** bash_scripting
**Total Points:** 44
**Pass Threshold:** 0.85

## Criterion 1: bash_correctness
**Category:** functionality
**Max Points:** N/A
**Description:** Script performs correct pg_dump → compress → upload → rotate pipeline with specific parameters
**Pass Condition:** Uses pg_dump with --verbose, --no-password, and --format=custom flags. Compresses output using gzip with -9 (best compression). Uploads to S3 using 'aws s3 cp' with --storage-class and --metadata parameters. Implements both time-based rotation (deletes backups older than N days using AWS CLI list and delete operations) AND count-based rotation (keeps only N most recent backups when total exceeds limit).

## Criterion 2: bash_safety
**Category:** reliability
**Max Points:** N/A
**Description:** Script is safe — set -euo pipefail, no secrets in code, cleanup on failure
**Pass Condition:** Includes 'set -euo pipefail' at script start. Implements trap 'cleanup_function' EXIT ERR to remove temporary files on any exit. No database passwords appear in script text (checked via grep). Uses either .pgpass file (with 0600 permissions check) or PGPASSWORD environment variable. All temporary files created in /tmp with random suffixes and explicitly removed in cleanup function.

## Criterion 3: bash_logging
**Category:** observability
**Max Points:** N/A
**Description:** Structured logging with timestamps and multiple severity levels
**Pass Condition:** Defines log() function that prefixes messages with ISO 8601 timestamp (YYYY-MM-DDTHH:MM:SS format). Logs to both a specified file and stdout/stderr using tee. Implements at least log_info() and log_error() functions. Must log: script start time, backup file size in MB (calculated via 'du -m'), total operation duration in seconds (using $SECONDS or date arithmetic), and S3 upload confirmation with final URL.

## Criterion 4: bash_notifications
**Category:** alerting
**Max Points:** N/A
**Description:** Error notifications sent via configurable method with required failure details
**Pass Condition:** On script failure (trap ERR): constructs notification message containing backup filename, complete error message from failed command, ISO 8601 timestamp, and hostname (from 'hostname' command). Supports exactly one of: sendmail/mail command with subject line, curl POST to Slack webhook with JSON payload, or curl POST to custom URL with form data. Notification method selected via NOTIFICATION_METHOD environment variable (values: email|slack|webhook).

## Criterion 5: bash_configurability
**Category:** usability
**Max Points:** N/A
**Description:** Script is configurable via environment variables with sensible defaults
**Pass Condition:** Accepts --help flag that prints usage information and exits. Uses environment variables: DB_NAME (required), S3_BUCKET (required), RETENTION_DAYS (default: 7), BACKUP_PREFIX (default: 'backup'). Script validates required variables are set and non-empty using parameter expansion or explicit checks. Prints error message and exits with code 1 if required variables are missing.
