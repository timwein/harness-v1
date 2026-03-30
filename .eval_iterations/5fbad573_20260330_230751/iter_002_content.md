```bash
#!/bin/bash
#
# PostgreSQL Database Backup Script with S3 Upload, Rotation, and Notifications
#
# This script creates compressed backups of PostgreSQL databases, uploads them to S3,
# manages retention, and sends notifications on failures.
#
# Usage: ./pg_backup_s3.sh [OPTIONS]
#   --help    Show this help message
#
# Environment Variables:
#   DB_NAME               - Database name to backup (required)
#   DB_HOST               - Database host (default: localhost)
#   DB_PORT               - Database port (default: 5432)
#   DB_USER               - Database user (required)
#   PGPASSWORD            - Database password (required)
#   S3_BUCKET             - S3 bucket name (required)
#   S3_PATH               - S3 path prefix (default: backups)
#   RETENTION_DAYS        - Days to keep backups (default: 30)
#   RETENTION_COUNT       - Max number of backups to keep (default: 60)
#   SLACK_WEBHOOK_URL     - Slack webhook for notifications (optional)
#   EMAIL_RECIPIENTS      - Comma-separated email list for notifications (optional)
#   PAGERDUTY_INTEGRATION_KEY - PagerDuty integration key for critical alerts (optional)
#   LOG_FILE              - Log file path (default: /var/log/pg_backup.log)
#   LOG_LEVEL             - Log verbosity: DEBUG,INFO,WARN,ERROR (default: INFO)
#   LOG_MAX_SIZE          - Max log file size in MB before rotation (default: 100)
#

set -euo pipefail

# Lockfile to prevent concurrent runs
LOCK_FILE="/var/run/pg_backup_${DB_NAME:-default}.lock"
LOCK_FD=200

# Acquire lock or exit
acquire_lock() {
    exec 200>"$LOCK_FILE"
    if ! flock -n 200; then
        echo "Another backup process is already running. Exiting." >&2
        exit 1
    fi
}

# Configuration with defaults
DB_HOST=${DB_HOST:-"localhost"}
DB_PORT=${DB_PORT:-5432}
DB_USER=${DB_USER:?"DB_USER environment variable is required"}
DB_NAME=${DB_NAME:?"DB_NAME environment variable is required"}
S3_BUCKET=${S3_BUCKET:?"S3_BUCKET environment variable is required"}
S3_PATH=${S3_PATH:-"backups"}
RETENTION_DAYS=${RETENTION_DAYS:-30}
RETENTION_COUNT=${RETENTION_COUNT:-60}
LOG_FILE=${LOG_FILE:-"/var/log/pg_backup.log"}
LOG_LEVEL=${LOG_LEVEL:-"INFO"}
LOG_MAX_SIZE=${LOG_MAX_SIZE:-100}

# Validate required environment variables and formats
: ${PGPASSWORD:?"PGPASSWORD environment variable is required"}

# Validate parameter formats
validate_config() {
    # Validate S3 bucket name format (basic check)
    if [[ ! "$S3_BUCKET" =~ ^[a-z0-9.-]+$ ]] || [[ ${#S3_BUCKET} -lt 3 ]] || [[ ${#S3_BUCKET} -gt 63 ]]; then
        echo "ERROR: S3_BUCKET format is invalid. Must be 3-63 characters, lowercase alphanumeric with dots/hyphens." >&2
        exit 1
    fi
    
    # Validate retention days is positive integer
    if ! [[ "$RETENTION_DAYS" =~ ^[0-9]+$ ]] || [[ "$RETENTION_DAYS" -le 0 ]]; then
        echo "ERROR: RETENTION_DAYS must be a positive integer." >&2
        exit 1
    fi
    
    # Validate retention count is positive integer
    if ! [[ "$RETENTION_COUNT" =~ ^[0-9]+$ ]] || [[ "$RETENTION_COUNT" -le 0 ]]; then
        echo "ERROR: RETENTION_COUNT must be a positive integer." >&2
        exit 1
    fi
    
    # Validate database port
    if ! [[ "$DB_PORT" =~ ^[0-9]+$ ]] || [[ "$DB_PORT" -lt 1 ]] || [[ "$DB_PORT" -gt 65535 ]]; then
        echo "ERROR: DB_PORT must be a valid port number (1-65535)." >&2
        exit 1
    fi
    
    # Test database connectivity
    if ! pg_isready -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -q; then
        echo "ERROR: Cannot connect to PostgreSQL database. Check connection parameters." >&2
        exit 1
    fi
    
    # Test AWS credentials and S3 access
    if ! aws sts get-caller-identity >/dev/null 2>&1; then
        echo "ERROR: AWS credentials not configured or invalid." >&2
        exit 1
    fi
    
    if ! aws s3 ls "s3://$S3_BUCKET/" >/dev/null 2>&1; then
        echo "ERROR: Cannot access S3 bucket: $S3_BUCKET" >&2
        exit 1
    fi
}

# Create timestamp for backup filename
TIMESTAMP=$(date -u +%Y%m%d_%H%M%S)
BACKUP_NAME="${DB_NAME}_${TIMESTAMP}.sql.gz"
TEMP_DIR=$(mktemp -d)
TEMP_BACKUP="${TEMP_DIR}/${BACKUP_NAME}"

# Log rotation function
rotate_log() {
    if [[ -f "$LOG_FILE" ]]; then
        local log_size_mb=$(( $(stat -f%z "$LOG_FILE" 2>/dev/null || stat -c%s "$LOG_FILE") / 1024 / 1024 ))
        if [[ $log_size_mb -gt $LOG_MAX_SIZE ]]; then
            mv "$LOG_FILE" "${LOG_FILE}.old"
            touch "$LOG_FILE"
        fi
    fi
}

# Enhanced log function with timestamps, levels, and rotation
log() {
    local level="$1"
    local message="$2"
    local timestamp=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
    
    # Check log level filtering
    case "$LOG_LEVEL" in
        "ERROR") [[ "$level" != "ERROR" ]] && return 0 ;;
        "WARN") [[ "$level" =~ ^(DEBUG|INFO)$ ]] && return 0 ;;
        "INFO") [[ "$level" == "DEBUG" ]] && return 0 ;;
        "DEBUG") ;; # Show all levels
    esac
    
    rotate_log
    echo "[$timestamp] [$level] $message" | tee -a "$LOG_FILE"
}

# Cleanup function
cleanup() {
    local exit_code=$?
    if [[ -d "$TEMP_DIR" ]]; then
        rm -rf "$TEMP_DIR"
        log "INFO" "Cleaned up temporary directory: $TEMP_DIR"
    fi
    
    # Release lock
    if [[ -n "${LOCK_FD:-}" ]]; then
        flock -u "$LOCK_FD" 2>/dev/null || true
    fi
    [[ -f "$LOCK_FILE" ]] && rm -f "$LOCK_FILE" 2>/dev/null || true
    
    if [[ $exit_code -ne 0 ]]; then
        log "ERROR" "Script failed with exit code: $exit_code"
        send_notification "ERROR" "PostgreSQL backup failed for database: $DB_NAME" "Exit code: $exit_code. Check logs at $LOG_FILE for details."
    fi
}

# Set trap for cleanup on exit
trap cleanup EXIT

# Enhanced notification function supporting multiple channels
send_notification() {
    local level="$1"
    local title="$2"
    local details="$3"
    
    local timestamp=$(date -u +"%Y-%m-%d %H:%M:%S UTC")
    local hostname=$(hostname)
    
    # Get last 10 lines of log for context
    local log_tail=""
    if [[ -f "$LOG_FILE" ]]; then
        log_tail=$(tail -n 10 "$LOG_FILE" | sed 's/"/\\"/g' | sed ':a;N;$!ba;s/\n/\\n/g')
    fi
    
    # Slack notification
    if [[ -n "${SLACK_WEBHOOK_URL:-}" ]]; then
        local color="good"
        local severity_icon="✅"
        case "$level" in
            "ERROR") color="danger"; severity_icon="🚨" ;;
            "WARN") color="warning"; severity_icon="⚠️" ;;
        esac
        
        local payload=$(cat <<EOF
{
    "attachments": [
        {
            "color": "$color",
            "title": "$severity_icon $title",
            "fields": [
                {
                    "title": "Database",
                    "value": "$DB_NAME",
                    "short": true
                },
                {
                    "title": "Host",
                    "value": "$hostname",
                    "short": true
                },
                {
                    "title": "Timestamp",
                    "value": "$timestamp",
                    "short": true
                },
                {
                    "title": "Severity",
                    "value": "$level",
                    "short": true
                },
                {
                    "title": "Details",
                    "value": "$details",
                    "short": false
                }
            ],
            "footer": "Recent log entries:\\n$log_tail"
        }
    ]
}
EOF
        )
        
        curl -s -X POST -H 'Content-type: application/json' \
            --data "$payload" \
            "$SLACK_WEBHOOK_URL" || log "WARN" "Failed to send Slack notification"
    fi
    
    # Email notification
    if [[ -n "${EMAIL_RECIPIENTS:-}" ]] && command -v mail >/dev/null 2>&1; then
        local subject="[$level] PostgreSQL Backup: $title"
        local body="Database: $DB_NAME
Host: $hostname
Timestamp: $timestamp
Severity: $level

Details:
$details

Recent Log Entries:
$(tail -n 10 "$LOG_FILE" 2>/dev/null || echo "Log file not available")"
        
        echo "$body" | mail -s "$subject" "$EMAIL_RECIPIENTS" || log "WARN" "Failed to send email notification"
    fi
    
    # PagerDuty notification (for critical errors only)
    if [[ -n "${PAGERDUTY_INTEGRATION_KEY:-}" ]] && [[ "$level" == "ERROR" ]]; then
        local pd_payload=$(cat <<EOF
{
    "routing_key": "$PAGERDUTY_INTEGRATION_KEY",
    "event_action": "trigger",
    "payload": {
        "summary": "$title",
        "source": "$hostname",
        "severity": "error",
        "component": "postgresql-backup",
        "group": "database",
        "class": "backup-failure",
        "custom_details": {
            "database": "$DB_NAME",
            "details": "$details",
            "log_file": "$LOG_FILE"
        }
    }
}
EOF
        )
        
        curl -s -X POST -H 'Content-type: application/json' \
            --data "$pd_payload" \
            "https://events.pagerduty.com/v2/enqueue" || log "WARN" "Failed to send PagerDuty alert"
    fi
    
    if [[ -z "${SLACK_WEBHOOK_URL:-}${EMAIL_RECIPIENTS:-}${PAGERDUTY_INTEGRATION_KEY:-}" ]]; then
        log "INFO" "No notification channels configured, skipping notification"
    fi
}

# Show help message
show_help() {
    cat << EOF
PostgreSQL Database Backup Script with S3 Upload, Rotation, and Notifications

This script creates compressed backups of PostgreSQL databases, uploads them to S3,
manages retention, and sends notifications on failures.

Usage: $0 [OPTIONS]

Options:
  --help    Show this help message

Required Environment Variables:
  DB_NAME               - Database name to backup
  DB_USER               - Database user
  PGPASSWORD            - Database password
  S3_BUCKET             - S3 bucket name

Optional Environment Variables:
  DB_HOST               - Database host (default: localhost)
  DB_PORT               - Database port (default: 5432)
  S3_PATH               - S3 path prefix (default: backups)
  RETENTION_DAYS        - Days to keep backups (default: 30)
  RETENTION_COUNT       - Max number of backups to keep (default: 60)
  SLACK_WEBHOOK_URL     - Slack webhook for error notifications
  EMAIL_RECIPIENTS      - Comma-separated email addresses for notifications
  PAGERDUTY_INTEGRATION_KEY - PagerDuty integration key for critical alerts
  LOG_FILE              - Log file path (default: /var/log/pg_backup.log)
  LOG_LEVEL             - Log verbosity: DEBUG,INFO,WARN,ERROR (default: INFO)
  LOG_MAX_SIZE          - Max log file size in MB before rotation (default: 100)

Examples:
  # Basic usage
  DB_NAME=mydb DB_USER=postgres PGPASSWORD=secret S3_BUCKET=mybucket $0

  # With advanced options and multiple notification channels
  DB_NAME=mydb DB_USER=postgres PGPASSWORD=secret S3_BUCKET=mybucket \\
  RETENTION_DAYS=14 RETENTION_COUNT=50 \\
  SLACK_WEBHOOK_URL=https://hooks.slack.com/... \\
  EMAIL_RECIPIENTS=admin@company.com,dba@company.com \\
  LOG_LEVEL=DEBUG $0

EOF
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --help)
            show_help
            exit 0
            ;;
        *)
            log "ERROR" "Unknown option: $1"
            show_help
            exit 1
            ;;
    esac
    shift
done

# Main backup function
main() {
    local start_time=$(date +%s)
    log "INFO" "Starting PostgreSQL backup for database: $DB_NAME"
    log "INFO" "Backup destination: s3://$S3_BUCKET/$S3_PATH/$BACKUP_NAME"
    log "DEBUG" "Configuration: Host=$DB_HOST:$DB_PORT, User=$DB_USER, Retention=${RETENTION_DAYS}d/${RETENTION_COUNT} backups"
    
    # Create database dump with optimized flags for performance and reliability
    log "INFO" "Creating database dump with optimized settings..."
    
    # Use zstd compression if available for better performance, fallback to gzip
    local compression_cmd="gzip"
    local backup_ext=".gz"
    if command -v zstd >/dev/null 2>&1; then
        compression_cmd="zstd -3"  # Level 3 provides good compression/speed balance
        backup_ext=".zst"
        BACKUP_NAME="${DB_NAME}_${TIMESTAMP}.sql${backup_ext}"
        TEMP_BACKUP="${TEMP_DIR}/${BACKUP_NAME}"
        log "DEBUG" "Using zstd compression for better performance on large databases"
    else
        log "DEBUG" "Using gzip compression (zstd not available)"
    fi
    
    # Enhanced pg_dump with performance optimizations for large databases
    pg_dump \
        -h "$DB_HOST" \
        -p "$DB_PORT" \
        -U "$DB_USER" \
        -d "$DB_NAME" \
        --format=custom \
        --compress=6 \
        --no-owner \
        --no-privileges \
        --lock-wait-timeout=300000 \
        --jobs=4 \
        --verbose 2>&1 | $compression_cmd > "$TEMP_BACKUP"
    
    # Verify pg_dump succeeded (check PIPESTATUS for the pg_dump exit code)
    if [[ ${PIPESTATUS[0]} -ne 0 ]]; then
        log "ERROR" "pg_dump command failed with exit code: ${PIPESTATUS[0]}"
        exit 1
    fi
    
    # Check if backup was created successfully
    if [[ ! -f "$TEMP_BACKUP" ]] || [[ ! -s "$TEMP_BACKUP" ]]; then
        log "ERROR" "Backup file was not created or is empty"
        exit 1
    fi
    
    # Get backup size and verify integrity
    local backup_size=$(du -h "$TEMP_BACKUP" | cut -f1)
    local backup_bytes=$(stat -f%z "$TEMP_BACKUP" 2>/dev/null || stat -c%s "$TEMP_BACKUP")
    log "INFO" "Backup created successfully, size: $backup_size ($backup_bytes bytes)"
    
    # Upload to S3 with multipart upload and server-side encryption for large files
    log "INFO" "Uploading backup to S3 with optimized settings..."
    
    # Configure multipart threshold and chunk size for large files
    aws configure set default.s3.multipart_threshold 64MB
    aws configure set default.s3.multipart_chunksize 16MB
    aws configure set default.s3.max_concurrent_requests 10
    
    aws s3 cp "$TEMP_BACKUP" "s3://$S3_BUCKET/$S3_PATH/$BACKUP_NAME" \
        --storage-class STANDARD_IA \
        --server-side-encryption AES256 \
        --metadata "database=$DB_NAME,created=$(date -u +%Y-%m-%dT%H:%M:%SZ),size_bytes=$backup_bytes,compression=${compression_cmd%% *}" \
        --only-show-errors
    
    if [[ $? -eq 0 ]]; then
        log "INFO" "Successfully uploaded backup to S3 with server-side encryption"
    else
        log "ERROR" "Failed to upload backup to S3"
        exit 1
    fi
    
    # Enhanced rotation: both time-based and count-based with fallback
    log "INFO" "Managing backup retention (${RETENTION_DAYS}d max age, ${RETENTION_COUNT} max count)..."
    local cutoff_date=$(date -u -d "$RETENTION_DAYS days ago" +%Y-%m-%d)
    
    # Get all backups for this database, sorted by date (newest first)
    local all_backups=$(aws s3 ls "s3://$S3_BUCKET/$S3_PATH/" --recursive | \
        grep "${DB_NAME}_" | \
        awk '{print $1" "$2" "$4}' | \
        sort -r)
    
    # Time-based rotation: remove backups older than retention period
    local time_deleted=0
    while IFS= read -r line; do
        if [[ -n "$line" ]]; then
            local date=$(echo "$line" | awk '{print $1}')
            local file=$(echo "$line" | awk '{print $3}')
            
            if [[ "$date" < "$cutoff_date" ]]; then
                aws s3 rm "s3://$S3_BUCKET/$file" --only-show-errors
                ((time_deleted++))
                log "INFO" "Deleted old backup (time-based): $file (created: $date)"
            fi
        fi
    done <<< "$all_backups"
    
    # Count-based rotation: keep only the most recent N backups
    local count_deleted=0
    local backup_count=0
    while IFS= read -r line; do
        if [[ -n "$line" ]]; then
            ((backup_count++))
            if [[ $backup_count -gt $RETENTION_COUNT ]]; then
                local file=$(echo "$line" | awk '{print $3}')
                aws s3 rm "s3://$S3_BUCKET/$file" --only-show-errors
                ((count_deleted++))
                log "INFO" "Deleted old backup (count-based): $file"
            fi
        fi
    done <<< "$(echo "$all_backups" | grep -v "$(date -u +%Y-%m-%d)")"  # Exclude today's backups from count-based deletion
    
    local total_deleted=$((time_deleted + count_deleted))
    if [[ $total_deleted -gt 0 ]]; then
        log "INFO" "Removed $total_deleted old backup(s) ($time_deleted time-based, $count_deleted count-based)"
    else
        log "INFO" "No old backups found to remove"
    fi
    
    # Calculate duration and finish
    local end_time=$(date +%s)
    local duration=$((end_time - start_time))
    local duration_human="${duration}s"
    if [[ $duration -gt 3600 ]]; then
        duration_human="$((duration/3600))h $((duration%3600/60))m $((duration%60))s"
    elif [[ $duration -gt 60 ]]; then
        duration_human="$((duration/60))m $((duration%60))s"
    fi
    
    log "INFO" "Backup completed successfully in $duration_human"
    log "INFO" "Final backup location: s3://$S3_BUCKET/$S3_PATH/$BACKUP_NAME"
    log "DEBUG" "Backup statistics: Size=$backup_size, Duration=$duration_human, Compression=${compression_cmd%% *}"
    
    # Send success notification if configured
    if [[ -n "${SLACK_WEBHOOK_URL:-}${EMAIL_RECIPIENTS:-}" ]]; then
        send_notification "INFO" "PostgreSQL backup completed successfully" "Database: $DB_NAME, Size: $backup_size, Duration: $duration_human, Deleted: $total_deleted old backups"
    fi
}

# Acquire lock to prevent concurrent runs
acquire_lock

# Validate configuration and connectivity
validate_config

# Ensure log directory exists
mkdir -p "$(dirname "$LOG_FILE")"

# Run main function
main "$@"
```