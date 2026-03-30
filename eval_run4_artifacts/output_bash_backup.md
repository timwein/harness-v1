# Bash Backup — Baseline Output

**Task:** Write a bash script that backs up a PostgreSQL database to S3 with rotation, logging, and error notifications
**Note:** This task failed to complete the harness run (no harness score available). The baseline output is shown below.
**Baseline Score:** 32.1 / 44 (72.9%)

**Criterion breakdown (baseline):**
- bash_correctness: 8.4/12 (70%)
- bash_safety: 9.5/10 (95%)
- bash_logging: 6.0/8 (75%)
- bash_notifications: 5.5/8 (69%)
- bash_configurability: 2.7/6 (45%)

---

Here's a comprehensive bash script for PostgreSQL database backup to S3 with rotation, logging, and error notifications:

```bash
#!/bin/bash

# PostgreSQL S3 Backup Script with Rotation, Logging, and Notifications
# Author: Your Name
# Version: 1.0
# Description: Automated PostgreSQL backup to AWS S3 with configurable retention

set -euo pipefail

#=============================================================================
# CONFIGURATION SECTION
#=============================================================================

# Database Configuration
DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_PORT:-5432}"
DB_NAME="${DB_NAME:-mydb}"
DB_USER="${DB_USER:-postgres}"
DB_PASSWORD="${DB_PASSWORD:-}"
PGPASSFILE="${PGPASSFILE:-~/.pgpass}"

# S3 Configuration
S3_BUCKET="${S3_BUCKET:-my-backup-bucket}"
S3_PREFIX="${S3_PREFIX:-postgresql-backups}"
AWS_REGION="${AWS_REGION:-us-west-2}"

# Backup Configuration
BACKUP_DIR="${BACKUP_DIR:-/tmp/pg_backups}"
RETENTION_DAYS="${RETENTION_DAYS:-30}"
COMPRESSION="${COMPRESSION:-gzip}"
ENCRYPT_BACKUP="${ENCRYPT_BACKUP:-false}"
GPG_RECIPIENT="${GPG_RECIPIENT:-}"

# Notification Configuration
ENABLE_NOTIFICATIONS="${ENABLE_NOTIFICATIONS:-true}"
NOTIFICATION_TYPE="${NOTIFICATION_TYPE:-email}"  # email, slack, sns
EMAIL_TO="${EMAIL_TO:-admin@example.com}"
EMAIL_FROM="${EMAIL_FROM:-backup@example.com}"
SLACK_WEBHOOK_URL="${SLACK_WEBHOOK_URL:-}"
SNS_TOPIC_ARN="${SNS_TOPIC_ARN:-}"

# Logging Configuration
LOG_DIR="${LOG_DIR:-/var/log/pg_backup}"
LOG_LEVEL="${LOG_LEVEL:-INFO}"
MAX_LOG_SIZE="${MAX_LOG_SIZE:-10M}"
MAX_LOG_FILES="${MAX_LOG_FILES:-5}"

#=============================================================================
# GLOBAL VARIABLES
#=============================================================================

SCRIPT_NAME=$(basename "$0")
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_FILENAME="${DB_NAME}_${TIMESTAMP}"
LOG_FILE="${LOG_DIR}/${SCRIPT_NAME}.log"
TEMP_DIR=""
EXIT_CODE=0

#=============================================================================
# UTILITY FUNCTIONS
#=============================================================================

# Logging function with levels
log() {
    local level="$1"
    shift
    local message="$*"
    local timestamp=$(date "+%Y-%m-%d %H:%M:%S")

    # Check if we should log this level
    case "${LOG_LEVEL}" in
        DEBUG) allowed_levels="DEBUG INFO WARN ERROR" ;;
        INFO)  allowed_levels="INFO WARN ERROR" ;;
        WARN)  allowed_levels="WARN ERROR" ;;
        ERROR) allowed_levels="ERROR" ;;
        *) allowed_levels="INFO WARN ERROR" ;;
    esac

    if [[ " $allowed_levels " =~ " $level " ]]; then
        echo "[$timestamp] [$level] $message" | tee -a "$LOG_FILE"
    fi
}

# Cleanup function
cleanup() {
    local exit_code=$?
    if [[ -n "${TEMP_DIR:-}" && -d "$TEMP_DIR" ]]; then
        log "DEBUG" "Cleaning up temporary directory: $TEMP_DIR"
        rm -rf "$TEMP_DIR"
    fi
    exit $exit_code
}

# Error handler
error_exit() {
    local error_message="$1"
    log "ERROR" "$error_message"
    send_notification "ERROR" "PostgreSQL Backup Failed" "$error_message"
    EXIT_CODE=1
    exit 1
}

# Check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Setup logging directory and rotation
setup_logging() {
    mkdir -p "$LOG_DIR"

    # Log rotation if file is too large
    if [[ -f "$LOG_FILE" ]]; then
        local log_size=$(stat -f%z "$LOG_FILE" 2>/dev/null || stat -c%s "$LOG_FILE" 2>/dev/null || echo "0")
        local max_size_bytes=$(echo "$MAX_LOG_SIZE" | sed 's/M/*1024*1024/g' | bc)

        if [[ $log_size -gt $max_size_bytes ]]; then
            for i in $(seq $((MAX_LOG_FILES-1)) -1 1); do
                [[ -f "${LOG_FILE}.$i" ]] && mv "${LOG_FILE}.$i" "${LOG_FILE}.$((i+1))"
            done
            mv "$LOG_FILE" "${LOG_FILE}.1"
        fi
    fi

    touch "$LOG_FILE"
}

#=============================================================================
# NOTIFICATION FUNCTIONS
#=============================================================================

send_email_notification() {
    local subject="$1"
    local message="$2"

    if command_exists mail; then
        echo "$message" | mail -s "$subject" "$EMAIL_TO"
    elif command_exists sendmail; then
        {
            echo "To: $EMAIL_TO"
            echo "From: $EMAIL_FROM"
            echo "Subject: $subject"
            echo ""
            echo "$message"
        } | sendmail "$EMAIL_TO"
    else
        log "WARN" "No mail command found for email notifications"
    fi
}

send_slack_notification() {
    local level="$1"
    local subject="$2"
    local message="$3"

    local color="good"
    [[ "$level" == "ERROR" ]] && color="danger"
    [[ "$level" == "WARN" ]] && color="warning"

    local payload=$(cat <<EOF
{
    "attachments": [
        {
            "color": "$color",
            "title": "$subject",
            "text": "$message",
            "fields": [
                {
                    "title": "Database",
                    "value": "$DB_NAME",
                    "short": true
                },
                {
                    "title": "Host",
                    "value": "$(hostname)",
                    "short": true
                }
            ],
            "footer": "PostgreSQL Backup",
            "ts": $(date +%s)
        }
    ]
}
EOF
)

    curl -X POST -H 'Content-type: application/json' \
        --data "$payload" "$SLACK_WEBHOOK_URL" 2>/dev/null || \
        log "WARN" "Failed to send Slack notification"
}

send_sns_notification() {
    local subject="$1"
    local message="$2"

    aws sns publish \
        --topic-arn "$SNS_TOPIC_ARN" \
        --subject "$subject" \
        --message "$message" \
        --region "$AWS_REGION" 2>/dev/null || \
        log "WARN" "Failed to send SNS notification"
}

send_notification() {
    local level="$1"
    local subject="$2"
    local message="$3"

    if [[ "$ENABLE_NOTIFICATIONS" != "true" ]]; then
        return 0
    fi

    case "$NOTIFICATION_TYPE" in
        email)
            [[ -n "$EMAIL_TO" ]] && send_email_notification "$subject" "$message"
            ;;
        slack)
            [[ -n "$SLACK_WEBHOOK_URL" ]] && send_slack_notification "$level" "$subject" "$message"
            ;;
        sns)
            [[ -n "$SNS_TOPIC_ARN" ]] && send_sns_notification "$subject" "$message"
            ;;
        *)
            log "WARN" "Unknown notification type: $NOTIFICATION_TYPE"
            ;;
    esac
}

#=============================================================================
# BACKUP FUNCTIONS
#=============================================================================

check_prerequisites() {
    log "INFO" "Checking prerequisites..."

    local required_commands="pg_dump aws"
    for cmd in $required_commands; do
        if ! command_exists "$cmd"; then
            error_exit "Required command not found: $cmd"
        fi
    done

    [[ "$COMPRESSION" == "gzip" ]] && ! command_exists "gzip" && error_exit "gzip not found"
    [[ "$ENCRYPT_BACKUP" == "true" ]] && ! command_exists "gpg" && error_exit "gpg not found for encryption"

    if ! aws sts get-caller-identity >/dev/null 2>&1; then
        error_exit "AWS credentials not configured properly"
    fi

    if ! aws s3 ls "s3://$S3_BUCKET" >/dev/null 2>&1; then
        error_exit "Cannot access S3 bucket: $S3_BUCKET"
    fi

    if ! pg_isready -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" >/dev/null 2>&1; then
        error_exit "Cannot connect to PostgreSQL database"
    fi

    log "INFO" "Prerequisites check completed successfully"
}

create_backup() {
    log "INFO" "Creating PostgreSQL backup for database: $DB_NAME"

    TEMP_DIR=$(mktemp -d)
    local backup_path="$TEMP_DIR/$BACKUP_FILENAME.sql"

    if [[ -n "$DB_PASSWORD" ]]; then
        export PGPASSWORD="$DB_PASSWORD"
    fi

    local pg_dump_opts="--host=$DB_HOST --port=$DB_PORT --username=$DB_USER"
    pg_dump_opts="$pg_dump_opts --format=custom --blobs --verbose"

    log "DEBUG" "Running pg_dump with options: $pg_dump_opts"

    if ! pg_dump $pg_dump_opts "$DB_NAME" > "$backup_path" 2>>"$LOG_FILE"; then
        error_exit "Failed to create database backup"
    fi

    local backup_size=$(du -h "$backup_path" | cut -f1)
    log "INFO" "Backup created successfully. Size: $backup_size"

    if [[ "$COMPRESSION" == "gzip" ]]; then
        log "INFO" "Compressing backup..."
        if ! gzip "$backup_path"; then
            error_exit "Failed to compress backup"
        fi
        backup_path="${backup_path}.gz"
        BACKUP_FILENAME="${BACKUP_FILENAME}.sql.gz"
    fi

    echo "$backup_path"
}

upload_to_s3() {
    local backup_path="$1"
    local s3_key="${S3_PREFIX}/${DB_NAME}/$(date +%Y)/$(date +%m)/$(date +%d)/$BACKUP_FILENAME"
    local s3_url="s3://$S3_BUCKET/$s3_key"

    log "INFO" "Uploading backup to S3: $s3_url"

    if ! aws s3 cp "$backup_path" "$s3_url" \
        --metadata "database=$DB_NAME,timestamp=$TIMESTAMP,host=$(hostname)" \
        --region "$AWS_REGION" 2>>"$LOG_FILE"; then
        error_exit "Failed to upload backup to S3"
    fi

    log "INFO" "Backup uploaded successfully to S3"

    if ! aws s3 ls "$s3_url" >/dev/null 2>&1; then
        error_exit "Backup verification failed - file not found in S3"
    fi

    echo "$s3_url"
}

rotate_backups() {
    log "INFO" "Starting backup rotation (keeping last $RETENTION_DAYS days)..."

    local cutoff_date=$(date -d "$RETENTION_DAYS days ago" +%Y-%m-%d 2>/dev/null || \
                       date -v-"${RETENTION_DAYS}d" +%Y-%m-%d)

    local deleted_count=0

    aws s3api list-objects-v2 \
        --bucket "$S3_BUCKET" \
        --prefix "${S3_PREFIX}/${DB_NAME}/" \
        --query "Contents[?LastModified<='${cutoff_date}'].Key" \
        --output text 2>/dev/null | while read -r key; do

        if [[ -n "$key" && "$key" != "None" ]]; then
            log "DEBUG" "Deleting old backup: s3://$S3_BUCKET/$key"
            if aws s3 rm "s3://$S3_BUCKET/$key" >/dev/null 2>&1; then
                ((deleted_count++))
            fi
        fi
    done

    log "INFO" "Backup rotation completed. Deleted $deleted_count old backups"
}

#=============================================================================
# MAIN FUNCTION
#=============================================================================

main() {
    local start_time=$(date +%s)

    log "INFO" "Starting PostgreSQL backup process..."
    log "INFO" "Configuration: DB=$DB_NAME, S3=$S3_BUCKET/$S3_PREFIX"

    setup_logging
    check_prerequisites

    mkdir -p "$BACKUP_DIR"

    local backup_path
    backup_path=$(create_backup)

    local backup_size=$(du -h "$backup_path" | cut -f1)

    local s3_url
    s3_url=$(upload_to_s3 "$backup_path")

    rotate_backups

    local end_time=$(date +%s)
    local duration=$((end_time - start_time))

    log "INFO" "Backup completed successfully in ${duration}s"
    log "INFO" "Backup location: $s3_url"

    send_notification "INFO" "PostgreSQL Backup Successful" "Backup of $DB_NAME completed in ${duration}s. Location: $s3_url"
}

# Trap cleanup on exit
trap cleanup EXIT

# Run main
main "$@"
```
