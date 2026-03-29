# Harness Output: bash_backup

**Score:** 80.7% (35.5/44)
**Iterations:** 5
**Best Iteration:** 4 (80.7%)

---

```bash
#!/bin/bash

# PostgreSQL Database Backup Script with S3 Upload, Rotation, and Notifications
# Usage: ./backup_postgres.sh [--help]

set -euo pipefail

# Configuration with environment variables and defaults
DB_NAME="${DB_NAME:?'DB_NAME environment variable is required'}"
DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_PORT:-5432}"
DB_USER="${DB_USER:-postgres}"
S3_BUCKET="${S3_BUCKET:?'S3_BUCKET environment variable is required'}"
BACKUP_PREFIX="${BACKUP_PREFIX:-backups/postgres}"
RETENTION_DAYS="${RETENTION_DAYS:-30}"
COUNT_RETENTION="${COUNT_RETENTION:-10}"
LOG_FILE="${LOG_FILE:-/var/log/postgres_backup.log}"
LOG_LEVEL="${LOG_LEVEL:-INFO}"
BACKUP_DIR="${BACKUP_DIR:-/tmp/postgres_backups}"
NOTIFICATION_WEBHOOK="${NOTIFICATION_WEBHOOK:-}"
NOTIFICATION_TYPES="${NOTIFICATION_TYPES:-webhook}"
NOTIFICATION_SEVERITY="${NOTIFICATION_SEVERITY:-ERROR}"
COMPRESS_LEVEL="${COMPRESS_LEVEL:-6}"
SYSLOG_SERVER="${SYSLOG_SERVER:-}"
LOG_MAX_SIZE="${LOG_MAX_SIZE:-10M}"

# Lockfile for preventing concurrent executions
LOCKFILE="/tmp/postgres_backup.lock"

# Show help if requested
if [[ "${1:-}" == "--help" ]]; then
    cat << EOF
PostgreSQL Database Backup Script

USAGE:
    $0 [--help]

REQUIRED ENVIRONMENT VARIABLES:
    DB_NAME                 Database name to backup
    S3_BUCKET              S3 bucket for backup storage

OPTIONAL ENVIRONMENT VARIABLES:
    DB_HOST                Database host (default: localhost)
    DB_PORT                Database port (default: 5432)
    DB_USER                Database user (default: postgres)
    BACKUP_PREFIX          S3 prefix path (default: backups/postgres)
    RETENTION_DAYS         Days to keep backups (default: 30)
    COUNT_RETENTION        Number of recent backups to keep (default: 10)
    LOG_FILE               Log file path (default: /var/log/postgres_backup.log)
    LOG_LEVEL              Log level: DEBUG,INFO,WARN,ERROR (default: INFO)
    BACKUP_DIR             Local backup directory (default: /tmp/postgres_backups)
    NOTIFICATION_WEBHOOK   Slack webhook URL for error notifications
    NOTIFICATION_TYPES     Notification methods: webhook,email,syslog (default: webhook)
    NOTIFICATION_SEVERITY  When to notify: ERROR,WARN,INFO (default: ERROR)
    COMPRESS_LEVEL         Gzip compression level 1-9 (default: 6)
    SYSLOG_SERVER          Remote syslog server for log forwarding
    LOG_MAX_SIZE           Max log file size before rotation (default: 10M)

EXAMPLE:
    DB_NAME=mydb S3_BUCKET=my-backups ./backup_postgres.sh
EOF
    exit 0
fi

# Check for concurrent execution using lockfile
if ! (set -C; echo $$ > "$LOCKFILE") 2>/dev/null; then
    echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] [ERROR] Another backup is already running (lockfile exists: $LOCKFILE)"
    exit 1
fi

# Global variables
SCRIPT_START_TIME=$(date -u +%Y-%m-%dT%H:%M:%SZ)
BACKUP_FILENAME=""
TEMP_FILES=()
LAST_NOTIFICATION_TIME=0
NOTIFICATION_RATE_LIMIT=300

# Log level hierarchy for filtering
declare -A LOG_LEVELS=([DEBUG]=0 [INFO]=1 [WARN]=2 [ERROR]=3)
CURRENT_LOG_LEVEL=${LOG_LEVELS[$LOG_LEVEL]:-1}

# Color codes for terminal output
declare -A LOG_COLORS=([DEBUG]='\033[0;36m' [INFO]='\033[0;32m' [WARN]='\033[0;33m' [ERROR]='\033[0;31m')
RESET_COLOR='\033[0m'

# Enhanced logging function with level filtering, colors, and multiple destinations
log() {
    local level="$1"
    local message="$2"
    local timestamp=$(date -u +%Y-%m-%dT%H:%M:%SZ)
    local log_entry="[$timestamp] [$level] $message"
    
    # Check if log level meets threshold
    local msg_level=${LOG_LEVELS[$level]:-1}
    if [[ $msg_level -lt $CURRENT_LOG_LEVEL ]]; then
        return 0
    fi
    
    # Rotate log file if it exceeds size limit
    if [[ -f "$LOG_FILE" ]] && [[ $(stat -f%z "$LOG_FILE" 2>/dev/null || stat -c%s "$LOG_FILE" 2>/dev/null || echo 0) -gt $(numfmt --from=iec "$LOG_MAX_SIZE") ]]; then
        mv "$LOG_FILE" "${LOG_FILE}.old"
        touch "$LOG_FILE"
        echo "[$timestamp] [INFO] Log file rotated due to size limit" >> "$LOG_FILE"
    fi
    
    # Terminal output with colors and file output using tee for dual destination
    if [[ -t 1 ]]; then
        echo -e "${LOG_COLORS[$level]:-}$log_entry$RESET_COLOR" | tee -a "$LOG_FILE"
    else
        echo "$log_entry" | tee -a "$LOG_FILE"
    fi
    
    # Syslog integration
    if command -v logger >/dev/null 2>&1; then
        logger -t "postgres_backup" -p "daemon.$level" "$message"
    fi
    
    # Remote syslog if configured
    if [[ -n "$SYSLOG_SERVER" ]] && command -v logger >/dev/null 2>&1; then
        logger -n "$SYSLOG_SERVER" -t "postgres_backup" -p "daemon.$level" "$message" 2>/dev/null || true
    fi
}

# Cleanup function for safe exit
cleanup() {
    local exit_code=$?
    
    if [[ $exit_code -ne 0 ]]; then
        log "ERROR" "Backup failed with exit code $exit_code"
        send_failure_notification "Backup process failed unexpectedly"
    fi
    
    # Clean up temporary files
    for temp_file in "${TEMP_FILES[@]}"; do
        if [[ -f "$temp_file" ]]; then
            rm -f "$temp_file"
            log "INFO" "Cleaned up temporary file: $temp_file"
        fi
    done
    
    # Clean up empty backup directory
    if [[ -d "$BACKUP_DIR" ]] && [[ -z "$(ls -A "$BACKUP_DIR")" ]]; then
        rmdir "$BACKUP_DIR"
    fi
    
    # Remove lockfile
    if [[ -f "$LOCKFILE" ]]; then
        rm -f "$LOCKFILE"
    fi
}

# Set trap for cleanup on exit
trap cleanup EXIT

# Enhanced notification function with multiple channels and rate limiting
send_failure_notification() {
    local error_msg="$1"
    local current_time=$(date +%s)
    local severity_level=${LOG_LEVELS[$NOTIFICATION_SEVERITY]:-3}
    local error_level=${LOG_LEVELS[ERROR]:-3}
    
    # Check if we should send notification based on severity
    if [[ $error_level -lt $severity_level ]]; then
        log "DEBUG" "Notification severity threshold not met"
        return 0
    fi
    
    # Rate limiting check
    if [[ $((current_time - LAST_NOTIFICATION_TIME)) -lt $NOTIFICATION_RATE_LIMIT ]]; then
        log "WARN" "Notification rate limit active - skipping notification"
        return 0
    fi
    
    LAST_NOTIFICATION_TIME=$current_time
    
    # Process multiple notification types
    IFS=',' read -ra NOTIFICATION_METHODS <<< "$NOTIFICATION_TYPES"
    for method in "${NOTIFICATION_METHODS[@]}"; do
        case "$method" in
            webhook)
                send_webhook_notification "$error_msg"
                ;;
            email)
                send_email_notification "$error_msg"
                ;;
            syslog)
                send_syslog_notification "$error_msg"
                ;;
            *)
                log "WARN" "Unknown notification method: $method"
                ;;
        esac
    done
}

# Webhook notification implementation
send_webhook_notification() {
    local error_msg="$1"
    
    if [[ -n "$NOTIFICATION_WEBHOOK" ]]; then
        local payload=$(cat << EOF
{
    "text": "🔴 PostgreSQL Backup Failed",
    "blocks": [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "*PostgreSQL Backup Failure*\n*Database:* $DB_NAME\n*Host:* $DB_HOST\n*Time:* $SCRIPT_START_TIME\n*Error:* $error_msg"
            }
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "*Recent Log Entries:*\n\`\`\`$(tail -5 "$LOG_FILE" 2>/dev/null || echo "No log entries available")\`\`\`"
            }
        }
    ]
}
EOF
        )
        
        if curl -X POST -H 'Content-type: application/json' \
           --data "$payload" \
           --max-time 30 \
           --silent \
           "$NOTIFICATION_WEBHOOK" > /dev/null 2>&1; then
            log "INFO" "Webhook notification sent successfully"
        else
            log "WARN" "Failed to send webhook notification"
        fi
    fi
}

# Email notification implementation
send_email_notification() {
    local error_msg="$1"
    
    if [[ -n "${NOTIFICATION_EMAIL:-}" ]] && command -v mail >/dev/null 2>&1; then
        local subject="PostgreSQL Backup Failed - $DB_NAME"
        local body="Database: $DB_NAME
Host: $DB_HOST
Time: $SCRIPT_START_TIME
Error: $error_msg

Recent Log Entries:
$(tail -10 "$LOG_FILE" 2>/dev/null || echo "No log entries available")"
        
        echo "$body" | mail -s "$subject" "$NOTIFICATION_EMAIL" 2>/dev/null && \
            log "INFO" "Email notification sent successfully" || \
            log "WARN" "Failed to send email notification"
    fi
}

# Syslog notification implementation
send_syslog_notification() {
    local error_msg="$1"
    
    if command -v logger >/dev/null 2>&1; then
        logger -t "postgres_backup_alert" -p "daemon.crit" \
            "BACKUP FAILED - DB:$DB_NAME Host:$DB_HOST Error:$error_msg"
        log "INFO" "Syslog notification sent successfully"
    fi
}

# Validate dependencies and environment
validate_environment() {
    log "INFO" "Validating environment and dependencies"
    
    # Check required commands
    local required_commands=("pg_dump" "gzip" "aws" "curl")
    for cmd in "${required_commands[@]}"; do
        if ! command -v "$cmd" >/dev/null 2>&1; then
            log "ERROR" "Required command not found: $cmd"
            exit 1
        fi
    done
    
    # Create backup directory
    mkdir -p "$BACKUP_DIR"
    
    # Create log directory if it doesn't exist
    mkdir -p "$(dirname "$LOG_FILE")"
    
    # Test AWS credentials and S3 access
    if ! aws sts get-caller-identity >/dev/null 2>&1; then
        log "ERROR" "AWS credentials not configured or invalid"
        exit 1
    fi
    
    # Test S3 bucket access
    if ! aws s3 ls "s3://$S3_BUCKET/" >/dev/null 2>&1; then
        log "ERROR" "Cannot access S3 bucket: $S3_BUCKET"
        exit 1
    fi
    
    # Test database connection
    if ! pg_dump --version >/dev/null 2>&1; then
        log "ERROR" "pg_dump not available"
        exit 1
    fi
    
    log "INFO" "Environment validation completed successfully"
}

# Create database backup
create_backup() {
    local timestamp=$(date -u +%Y%m%d_%H%M%S)
    BACKUP_FILENAME="$DB_NAME-$timestamp.sql.gz"
    local backup_path="$BACKUP_DIR/$BACKUP_FILENAME"
    
    log "INFO" "Starting backup of database '$DB_NAME'"
    
    # Add backup file to cleanup list
    TEMP_FILES+=("$backup_path")
    
    # Create compressed backup using pg_dump
    local dump_start_time=$(date +%s)
    
    if ! pg_dump \
        --host="$DB_HOST" \
        --port="$DB_PORT" \
        --username="$DB_USER" \
        --no-password \
        --format=custom \
        --no-owner \
        --no-privileges \
        --verbose \
        --compress=0 \
        "$DB_NAME" | gzip -"$COMPRESS_LEVEL" > "$backup_path"; then
        log "ERROR" "pg_dump failed for database '$DB_NAME'"
        send_failure_notification "pg_dump command failed"
        exit 1
    fi
    
    local dump_end_time=$(date +%s)
    local dump_duration=$((dump_end_time - dump_start_time))
    local backup_size=$(du -h "$backup_path" | cut -f1)
    
    log "INFO" "Backup created successfully: $BACKUP_FILENAME (Size: $backup_size, Duration: ${dump_duration}s)"
}

# Upload backup to S3
upload_to_s3() {
    local backup_path="$BACKUP_DIR/$BACKUP_FILENAME"
    local s3_key="$BACKUP_PREFIX/$BACKUP_FILENAME"
    local s3_uri="s3://$S3_BUCKET/$s3_key"
    
    log "INFO" "Uploading backup to S3: $s3_uri"
    
    local upload_start_time=$(date +%s)
    
    if ! aws s3 cp "$backup_path" "$s3_uri" \
        --storage-class STANDARD_IA \
        --metadata "source=postgres_backup,database=$DB_NAME,timestamp=$SCRIPT_START_TIME"; then
        log "ERROR" "Failed to upload backup to S3"
        send_failure_notification "S3 upload failed"
        exit 1
    fi
    
    local upload_end_time=$(date +%s)
    local upload_duration=$((upload_end_time - upload_start_time))
    
    log "INFO" "Upload completed successfully (Duration: ${upload_duration}s)"
    
    # Remove local backup file after successful upload
    rm -f "$backup_path"
    log "INFO" "Local backup file deleted: $backup_path"
}

# Enhanced rotation with both time-based and count-based cleanup
rotate_backups() {
    log "INFO" "Starting backup rotation (keeping last $RETENTION_DAYS days and $COUNT_RETENTION recent backups)"
    
    local s3_prefix_path="s3://$S3_BUCKET/$BACKUP_PREFIX/"
    local cutoff_date=$(date -d "$RETENTION_DAYS days ago" -u +%Y-%m-%d)
    
    # Get all backup files sorted by modification time (newest first)
    local all_backups
    all_backups=$(aws s3api list-objects-v2 \
        --bucket "$S3_BUCKET" \
        --prefix "$BACKUP_PREFIX/" \
        --query 'Contents[?contains(Key, `'$DB_NAME'`)].{Key: Key, LastModified: LastModified}' \
        --output text | \
        sort -k2 -r)
    
    local deleted_count=0
    local backup_count=0
    
    # Process backups for both time-based and count-based rotation
    while IFS=$'\t' read -r key last_modified; do
        if [[ -n "$key" ]]; then
            backup_count=$((backup_count + 1))
            local backup_date=$(echo "$last_modified" | cut -d'T' -f1)
            local should_delete=false
            local delete_reason=""
            
            # Check time-based retention
            if [[ "$backup_date" < "$cutoff_date" ]]; then
                should_delete=true
                delete_reason="older than $RETENTION_DAYS days"
            # Check count-based retention (keep only the N most recent)
            elif [[ $backup_count -gt $COUNT_RETENTION ]]; then
                should_delete=true
                delete_reason="exceeds count retention limit of $COUNT_RETENTION"
            fi
            
            if [[ "$should_delete" == true ]]; then
                local s3_uri="s3://$S3_BUCKET/$key"
                if aws s3 rm "$s3_uri" >/dev/null 2>&1; then
                    log "INFO" "Deleted old backup: $s3_uri ($delete_reason)"
                    ((deleted_count++))
                else
                    log "WARN" "Failed to delete old backup: $s3_uri"
                fi
            fi
        fi
    done <<< "$all_backups"
    
    log "INFO" "Backup rotation completed: $deleted_count old backups removed, $backup_count total backups processed"
}

# Main execution
main() {
    log "INFO" "Starting PostgreSQL backup process for database '$DB_NAME'"
    
    validate_environment
    create_backup
    upload_to_s3
    rotate_backups
    
    local script_end_time=$(date +%s)
    local script_start_epoch=$(date -d "$SCRIPT_START_TIME" +%s)
    local total_duration=$((script_end_time - script_start_epoch))
    
    log "INFO" "Backup process completed successfully (Total duration: ${total_duration}s)"
}

# Execute main function
main "$@"
```