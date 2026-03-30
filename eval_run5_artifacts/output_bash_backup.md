# Bash Backup — Final Harness Output

**Task:** Write a bash script that backs up a PostgreSQL database to S3 with rotation, logging, and error notifications
**Harness Score:** 35.5 / 44 (80.7%)
**Baseline Score:** 27.4 / 44 (62.4%)
**Lift:** +18.3pp
**Iterations:** 5

---

```bash
#!/bin/bash

# PostgreSQL Database Backup Script with S3 Upload, Rotation, and Notifications
# Usage: ./backup-postgres.sh [--help]

set -euo pipefail

# Configuration via environment variables with defaults
DB_NAME="${DB_NAME:?'DB_NAME environment variable is required'}"
DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_PORT:-5432}"
DB_USER="${DB_USER:-postgres}"
S3_BUCKET="${S3_BUCKET:?'S3_BUCKET environment variable is required'}"
S3_PREFIX="${S3_PREFIX:-backups/postgresql}"
RETENTION_DAYS="${RETENTION_DAYS:-30}"
LOG_FILE="${LOG_FILE:-/var/log/postgres-backup.log}"
LOG_LEVEL="${LOG_LEVEL:-INFO}"
SLACK_WEBHOOK_URL="${SLACK_WEBHOOK_URL:-}"
NOTIFICATION_ENABLED="${NOTIFICATION_ENABLED:-true}"
NOTIFICATION_TIMEOUT="${NOTIFICATION_TIMEOUT:-10}"
NOTIFICATION_CHANNEL="${NOTIFICATION_CHANNEL:-#alerts}"
NOTIFICATION_FORMAT="${NOTIFICATION_FORMAT:-slack}"
TEMP_DIR="${TEMP_DIR:-/tmp}"

# Set up dual output to file and stdout
exec 1> >(tee -a "$LOG_FILE")
exec 2> >(tee -a "$LOG_FILE" >&2)

# Global variables
SCRIPT_NAME=$(basename "$0")
TIMESTAMP=$(date -u +%Y%m%d_%H%M%S)
BACKUP_FILENAME="${DB_NAME}_${TIMESTAMP}.sql"
COMPRESSED_FILENAME="${BACKUP_FILENAME}.gz"
TEMP_BACKUP_PATH="${TEMP_DIR}/${BACKUP_FILENAME}"
TEMP_COMPRESSED_PATH="${TEMP_DIR}/${COMPRESSED_FILENAME}"
S3_KEY="${S3_PREFIX}/${COMPRESSED_FILENAME}"
LOCKFILE="/tmp/postgres_backup.lock"

# Show help and exit
show_help() {
    cat << EOF
PostgreSQL Database Backup Script

DESCRIPTION:
    Backs up a PostgreSQL database, compresses it, uploads to S3, and manages retention.
    Includes comprehensive logging and error notifications.

USAGE:
    $SCRIPT_NAME [--help]

REQUIRED ENVIRONMENT VARIABLES:
    DB_NAME         - PostgreSQL database name to backup
    S3_BUCKET       - S3 bucket name for storing backups

OPTIONAL ENVIRONMENT VARIABLES:
    DB_HOST         - Database host (default: localhost)
    DB_PORT         - Database port (default: 5432)
    DB_USER         - Database user (default: postgres)
    S3_PREFIX       - S3 key prefix (default: backups/postgresql)
    RETENTION_DAYS  - Days to keep backups (default: 30)
    LOG_FILE        - Log file path (default: /var/log/postgres-backup.log)
    LOG_LEVEL       - Log level filter (default: INFO)
    SLACK_WEBHOOK_URL - Slack webhook for error notifications (optional)
    NOTIFICATION_ENABLED - Enable/disable notifications (default: true)
    NOTIFICATION_TIMEOUT - Notification timeout in seconds (default: 10)
    NOTIFICATION_CHANNEL - Slack channel name (default: #alerts)
    NOTIFICATION_FORMAT - Notification format: slack (default: slack)
    TEMP_DIR        - Temporary directory (default: /tmp)
    PGPASSWORD      - Database password (recommended via environment)

EXAMPLES:
    # Basic backup:
    DB_NAME=mydb S3_BUCKET=backups ./backup.sh
    
    # Custom retention:
    DB_NAME=mydb S3_BUCKET=backups RETENTION_DAYS=7 ./backup.sh

EOF
}

# Logging function with timestamps and dual output
log() {
    local level="$1"
    local message="$2"
    
    # Log level filtering
    case "$LOG_LEVEL" in
        ERROR) [[ "$level" == "ERROR" ]] || return 0 ;;
        WARN) [[ "$level" == "ERROR" || "$level" == "WARN" ]] || return 0 ;;
        INFO) [[ "$level" == "ERROR" || "$level" == "WARN" || "$level" == "INFO" ]] || return 0 ;;
        *) ;; # DEBUG or unknown - log everything
    esac
    
    local log_entry="[$(date -u +%Y-%m-%dT%H:%M:%SZ)] [$$] [$level] $message"
    echo "$log_entry"
}

# Error notification function
send_error_notification() {
    local error_message="$1"
    
    if [[ "$NOTIFICATION_ENABLED" != "true" ]]; then
        log "INFO" "Notifications disabled, skipping error notification"
        return 0
    fi
    
    # Get system diagnostics for error context
    local disk_info
    disk_info=$(df -h "$TEMP_DIR" 2>/dev/null || echo "Disk info unavailable")
    local system_load
    system_load=$(uptime 2>/dev/null || echo "System load unavailable")
    
    if [[ "$NOTIFICATION_FORMAT" == "slack" && -n "$SLACK_WEBHOOK_URL" ]]; then
        local payload=$(cat << EOF
{
    "channel": "$NOTIFICATION_CHANNEL",
    "text": "🚨 PostgreSQL Backup Failed",
    "attachments": [
        {
            "color": "danger",
            "fields": [
                {
                    "title": "Database",
                    "value": "$DB_NAME",
                    "short": true
                },
                {
                    "title": "Host",
                    "value": "$DB_HOST:$DB_PORT",
                    "short": true
                },
                {
                    "title": "Timestamp",
                    "value": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
                    "short": true
                },
                {
                    "title": "Error",
                    "value": "$error_message",
                    "short": false
                },
                {
                    "title": "Disk Space",
                    "value": "\`\`\`$disk_info\`\`\`",
                    "short": true
                },
                {
                    "title": "System Load",
                    "value": "\`\`\`$system_load\`\`\`",
                    "short": true
                },
                {
                    "title": "Recent Log Entries",
                    "value": "\`\`\`$(tail -n 5 "$LOG_FILE" 2>/dev/null || echo "No log entries available")\`\`\`",
                    "short": false
                }
            ]
        }
    ]
}
EOF
)
        
        if ! response=$(curl -s -w "%{http_code}" -X POST -H 'Content-type: application/json' \
            --max-time "$NOTIFICATION_TIMEOUT" \
            --data "$payload" "$SLACK_WEBHOOK_URL" 2>/dev/null) || [[ "${response: -3}" != "200" ]]; then
            log "WARN" "Slack notification failed, trying email fallback"
            
            # Fallback to email notification
            if command -v mail >/dev/null 2>&1; then
                local email_body="PostgreSQL Backup Failed

Database: $DB_NAME
Host: $DB_HOST:$DB_PORT
Timestamp: $(date -u +%Y-%m-%dT%H:%M:%SZ)
Error: $error_message

Disk Space:
$disk_info

System Load:
$system_load

Recent Log Entries:
$(tail -n 5 "$LOG_FILE" 2>/dev/null || echo "No log entries available")"
                
                echo "$email_body" | mail -s "PostgreSQL Backup Failed - $DB_NAME" root 2>/dev/null || \
                    log "WARN" "Failed to send email fallback notification"
            else
                log "WARN" "Email fallback unavailable - mail command not found"
            fi
        else
            log "INFO" "Error notification sent to Slack channel $NOTIFICATION_CHANNEL"
        fi
    else
        log "WARN" "Notification configuration incomplete (format: $NOTIFICATION_FORMAT, webhook configured: $([[ -n "$SLACK_WEBHOOK_URL" ]] && echo "yes" || echo "no"))"
    fi
}

# Cleanup function for temporary files
cleanup() {
    local exit_code=$?
    log "INFO" "Cleaning up temporary files"
    
    if [[ -f "$TEMP_BACKUP_PATH" ]]; then
        rm -f "$TEMP_BACKUP_PATH"
        log "INFO" "Removed temporary backup file: $TEMP_BACKUP_PATH"
    fi
    
    if [[ -f "$TEMP_COMPRESSED_PATH" ]]; then
        rm -f "$TEMP_COMPRESSED_PATH"
        log "INFO" "Removed temporary compressed file: $TEMP_COMPRESSED_PATH"
    fi
    
    # Remove lockfile
    rmdir "$LOCKFILE" 2>/dev/null || true
    
    if [[ $exit_code -ne 0 ]]; then
        log "ERROR" "Script failed with exit code $exit_code"
        send_error_notification "Backup script terminated unexpectedly with exit code $exit_code"
    fi
}

# Set up trap for cleanup
trap cleanup EXIT

# Validate required tools
validate_dependencies() {
    local missing_tools=()
    
    for tool in pg_dump gzip aws curl; do
        if ! command -v "$tool" >/dev/null 2>&1; then
            missing_tools+=("$tool")
        fi
    done
    
    if [[ ${#missing_tools[@]} -gt 0 ]]; then
        log "ERROR" "Missing required tools: ${missing_tools[*]}"
        exit 1
    fi
}

# Perform PostgreSQL dump
perform_dump() {
    log "INFO" "Starting PostgreSQL dump for database: $DB_NAME"
    local start_time=$(date +%s)
    
    # Use pg_dump with optimal flags for backup
    if ! pg_dump \
        --host="$DB_HOST" \
        --port="$DB_PORT" \
        --username="$DB_USER" \
        --format=custom \
        --no-owner \
        --no-privileges \
        --compress=6 \
        --single-transaction \
        --lock-wait-timeout=30 \
        --verbose \
        --jobs=4 \
        --quote-all-identifiers \
        "$DB_NAME" > "$TEMP_BACKUP_PATH" 2>/dev/null; then
        
        log "ERROR" "pg_dump failed for database $DB_NAME"
        send_error_notification "pg_dump command failed"
        exit 1
    fi
    
    local end_time=$(date +%s)
    local duration=$((end_time - start_time))
    local file_size=$(stat -f%z "$TEMP_BACKUP_PATH" 2>/dev/null || stat -c%s "$TEMP_BACKUP_PATH" 2>/dev/null || echo "unknown")
    
    log "INFO" "Database dump completed in ${duration}s, size: ${file_size} bytes"
}

# Compress the backup
compress_backup() {
    local file_size=$(stat -f%z "$TEMP_BACKUP_PATH" 2>/dev/null || stat -c%s "$TEMP_BACKUP_PATH" 2>/dev/null || echo "0")
    log "INFO" "Starting compression of ${file_size} byte dump file"
    local start_time=$(date +%s)
    
    if ! gzip -9 -c "$TEMP_BACKUP_PATH" > "$TEMP_COMPRESSED_PATH"; then
        log "ERROR" "Failed to compress backup file"
        send_error_notification "Backup compression failed"
        exit 1
    fi
    
    # Validate compressed file was created successfully
    if [[ ! -f "$TEMP_COMPRESSED_PATH" ]]; then
        log "ERROR" "Compressed file was not created: $TEMP_COMPRESSED_PATH"
        send_error_notification "Compressed backup file missing after compression"
        exit 1
    fi
    
    local compressed_size=$(stat -f%z "$TEMP_COMPRESSED_PATH" 2>/dev/null || stat -c%s "$TEMP_COMPRESSED_PATH" 2>/dev/null || echo "0")
    if [[ "$compressed_size" == "0" ]]; then
        log "ERROR" "Compressed file has zero size: $TEMP_COMPRESSED_PATH"
        send_error_notification "Compressed backup file is empty"
        exit 1
    fi
    
    local original_size=$(stat -f%z "$TEMP_BACKUP_PATH" 2>/dev/null || stat -c%s "$TEMP_BACKUP_PATH" 2>/dev/null || echo "0")
    
    # Verify compressed file is smaller than original and compression ratio is reasonable
    if [[ "$original_size" != "0" && "$compressed_size" -ge "$original_size" ]]; then
        log "WARN" "Compressed file is not smaller than original (${original_size} → ${compressed_size} bytes)"
    fi
    
    # Check for reasonable compression ratio (should be at least 10% compression)
    if (( compressed_size * 10 > original_size * 9 )); then
        log "ERROR" "Poor compression ratio, possible corruption"
        exit 1
    fi
    
    local end_time=$(date +%s)
    local duration=$((end_time - start_time))
    
    if [[ "$original_size" != "0" && "$compressed_size" != "0" ]]; then
        local ratio=$(( (original_size - compressed_size) * 100 / original_size ))
        log "INFO" "Compression completed in ${duration}s, ratio: ${ratio}% (${original_size} → ${compressed_size} bytes)"
    else
        log "INFO" "Compression completed in ${duration}s"
    fi
}

# Upload to S3
upload_to_s3() {
    log "INFO" "Starting S3 upload to s3://${S3_BUCKET}/${S3_KEY}"
    local start_time=$(date +%s)
    local attempt=0
    local max_attempts=3
    local upload_success=false
    
    while [[ $attempt -lt $max_attempts && "$upload_success" == "false" ]]; do
        attempt=$((attempt + 1))
        
        if [[ $attempt -gt 1 ]]; then
            local backoff=$((2 ** (attempt - 1)))
            log "INFO" "Upload attempt $attempt after ${backoff}s backoff"
            sleep "$backoff"
        fi
        
        if aws s3 cp "$TEMP_COMPRESSED_PATH" "s3://${S3_BUCKET}/${S3_KEY}" \
            --storage-class STANDARD_IA \
            --cli-read-timeout=300 \
            --cli-connect-timeout=60 \
            --checksum-algorithm SHA256 \
            --metadata "database=$DB_NAME,timestamp=$TIMESTAMP,host=$DB_HOST"; then
            upload_success=true
        else
            log "WARN" "Upload attempt $attempt failed"
        fi
    done
    
    if [[ "$upload_success" == "false" ]]; then
        log "ERROR" "Failed to upload backup to S3 after $max_attempts attempts"
        send_error_notification "S3 upload failed after $max_attempts retry attempts"
        exit 1
    fi
    
    # Verify upload was successful
    local uploaded_info
    if ! uploaded_info=$(aws s3 ls "s3://${S3_BUCKET}/${S3_KEY}"); then
        log "ERROR" "Upload verification failed - file not found in S3"
        send_error_notification "S3 upload verification failed"
        exit 1
    fi
    
    local uploaded_size=$(echo "$uploaded_info" | awk '{print $3}')
    local local_size=$(stat -f%z "$TEMP_COMPRESSED_PATH" 2>/dev/null || stat -c%s "$TEMP_COMPRESSED_PATH" 2>/dev/null || echo "0")
    
    if [[ "$uploaded_size" != "$local_size" ]]; then
        log "ERROR" "Upload verification failed - size mismatch (local: $local_size, S3: $uploaded_size)"
        send_error_notification "S3 upload size verification failed"
        exit 1
    fi
    
    local end_time=$(date +%s)
    local duration=$((end_time - start_time))
    
    log "INFO" "Upload completed in ${duration}s to s3://${S3_BUCKET}/${S3_KEY}, verified size: $uploaded_size bytes"
}

# Rotate old backups
rotate_backups() {
    log "INFO" "Starting backup rotation, keeping backups newer than $RETENTION_DAYS days"
    
    # Validate S3 bucket access before rotation
    aws s3 ls "s3://${S3_BUCKET}/" >/dev/null 2>&1 || { 
        log "ERROR" "Cannot access S3 bucket for rotation"
        exit 1
    }
    
    # Count existing backups before rotation
    local total_backups_before
    total_backups_before=$(aws s3 ls "s3://${S3_BUCKET}/${S3_PREFIX}/" --recursive | \
        grep "${DB_NAME}_" | wc -l)
    
    # Safety check: ensure at least 1 backup remains
    if [[ "$total_backups_before" -le 1 ]]; then
        log "INFO" "Only $total_backups_before backup(s) found, skipping rotation to preserve at least one backup"
        return 0
    fi
    
    # List and filter backups older than retention period
    local cutoff_date
    if command -v gdate >/dev/null 2>&1; then
        # macOS with GNU date installed
        cutoff_date=$(gdate -d "$RETENTION_DAYS days ago" -u +%Y%m%d_%H%M%S)
    else
        # Linux date
        cutoff_date=$(date -d "$RETENTION_DAYS days ago" -u +%Y%m%d_%H%M%S)
    fi
    
    local old_backups
    old_backups=$(aws s3 ls "s3://${S3_BUCKET}/${S3_PREFIX}/" --recursive | \
        grep "${DB_NAME}_" | \
        awk '{print $4}' | \
        while read -r key; do
            # Extract timestamp from filename
            local filename=$(basename "$key")
            if [[ "$filename" =~ ${DB_NAME}_([0-9]{8}_[0-9]{6})\.sql\.gz$ ]]; then
                local backup_timestamp="${BASH_REMATCH[1]}"
                if [[ "$backup_timestamp" < "$cutoff_date" ]]; then
                    echo "$key"
                fi
            fi
        done)
    
    if [[ -n "$old_backups" ]]; then
        local count=0
        local old_backups_count
        old_backups_count=$(echo "$old_backups" | grep -c .)
        
        # Ensure we don't delete all backups
        local remaining_after_rotation=$((total_backups_before - old_backups_count))
        if [[ "$remaining_after_rotation" -lt 1 ]]; then
            log "WARN" "Rotation would remove all backups, keeping newest backup for safety"
            old_backups=$(echo "$old_backups" | head -n $((old_backups_count - 1)))
        fi
        
        while IFS= read -r key; do
            if [[ -n "$key" ]]; then
                log "INFO" "Deleting old backup: s3://${S3_BUCKET}/${key}"
                if aws s3 rm "s3://${S3_BUCKET}/${key}"; then
                    ((count++))
                else
                    log "WARN" "Failed to delete: s3://${S3_BUCKET}/${key}"
                fi
            fi
        done <<< "$old_backups"
        
        # Wait for S3 eventual consistency
        sleep 5
        
        # Verify rotation results
        local total_backups_after
        total_backups_after=$(aws s3 ls "s3://${S3_BUCKET}/${S3_PREFIX}/" --recursive | \
            grep "${DB_NAME}_" | wc -l)
        
        local expected_remaining=$((total_backups_before - count))
        if [[ "$total_backups_after" != "$expected_remaining" ]]; then
            log "WARN" "Rotation count discrepancy - expected $expected_remaining remaining, found $total_backups_after"
        fi
        
        log "INFO" "Rotation completed, deleted $count old backups (before: $total_backups_before, after: $total_backups_after)"
    else
        log "INFO" "No old backups found for rotation"
    fi
}

# Main execution
main() {
    # Handle help flag
    if [[ ${1:-} == "--help" || ${1:-} == "-h" ]]; then
        show_help
        exit 0
    fi
    
    # Validate RETENTION_DAYS is a positive integer
    if ! [[ "$RETENTION_DAYS" =~ ^[1-9][0-9]*$ ]]; then
        log "ERROR" "RETENTION_DAYS must be a positive integer"
        exit 1
    fi
    
    # Validate PGPASSWORD environment variable
    if [[ -z "${PGPASSWORD:-}" ]]; then
        log "ERROR" "PGPASSWORD environment variable is required for database authentication"
        exit 1
    fi
    
    # Create lockfile to prevent concurrent execution
    if ! mkdir "$LOCKFILE" 2>/dev/null; then
        log "ERROR" "Another backup is running (lockfile exists: $LOCKFILE)"
        exit 1
    fi
    
    log "INFO" "Starting PostgreSQL backup process for database: $DB_NAME"
    log "INFO" "Configuration - Host: $DB_HOST:$DB_PORT, User: $DB_USER, S3: s3://$S3_BUCKET/$S3_PREFIX"
    
    # Validate dependencies and environment
    validate_dependencies
    
    # Create log directory if it doesn't exist and set permissions
    mkdir -p "$(dirname "$LOG_FILE")" && chmod 755 "$(dirname "$LOG_FILE")"
    
    # Rotate log file if it exceeds 10MB
    if [[ -f "$LOG_FILE" ]]; then
        local log_size
        log_size=$(stat -f%z "$LOG_FILE" 2>/dev/null || stat -c%s "$LOG_FILE" 2>/dev/null || echo "0")
        if [[ "$log_size" -gt 10485760 ]]; then  # 10MB
            mv "$LOG_FILE" "${LOG_FILE}.old"
            log "INFO" "Rotated log file (was ${log_size} bytes)"
        fi
    fi
    
    # Execute backup pipeline
    local total_start_time=$(date +%s)
    
    perform_dump
    compress_backup
    upload_to_s3
    rotate_backups
    
    local total_end_time=$(date +%s)
    local total_duration=$((total_end_time - total_start_time))
    
    log "INFO" "Backup process completed successfully in ${total_duration}s"
    log "INFO" "Backup location: s3://${S3_BUCKET}/${S3_KEY}"
}

# Execute main function
main "$@"
```

---

*Criterion scores: bash_correctness 9.0/12 (75%) | bash_safety 10.0/10 (100%) | bash_logging 6.0/8 (75%) | bash_notifications 6.0/8 (75%) | bash_configurability 4.5/6 (75%)*
