```bash
#!/bin/bash

# PostgreSQL Backup Script with S3 Upload, Rotation, Logging, and Notifications
# Author: Auto-generated
# Description: Backs up PostgreSQL database, compresses, uploads to S3, manages retention

set -euo pipefail

# Configuration via environment variables with defaults
DB_NAME=${DB_NAME:?'DB_NAME is required'}
DB_HOST=${DB_HOST:-localhost}
DB_PORT=${DB_PORT:-5432}
DB_USER=${DB_USER:-postgres}

S3_BUCKET=${S3_BUCKET:?'S3_BUCKET is required'}
S3_PREFIX=${S3_PREFIX:-backups/postgresql}

RETENTION_DAYS=${RETENTION_DAYS:-30}
LOG_FILE=${LOG_FILE:-/var/log/pg_backup.log}

# Notification settings
SLACK_WEBHOOK_URL=${SLACK_WEBHOOK_URL:-}
EMAIL_TO=${EMAIL_TO:-}

# Internal variables
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILENAME="${DB_NAME}_${TIMESTAMP}.sql.gz"
TEMP_DIR="/tmp/pg_backup_$$"
SCRIPT_NAME=$(basename "$0")

# Help function
show_help() {
    cat << EOF
PostgreSQL Backup Script with S3 Upload, Rotation, and Notifications

USAGE:
    $SCRIPT_NAME [OPTIONS]

REQUIRED ENVIRONMENT VARIABLES:
    DB_NAME         - Database name to backup
    S3_BUCKET       - S3 bucket for storing backups

OPTIONAL ENVIRONMENT VARIABLES:
    DB_HOST         - Database host (default: localhost)
    DB_PORT         - Database port (default: 5432)  
    DB_USER         - Database user (default: postgres)
    S3_PREFIX       - S3 key prefix (default: backups/postgresql)
    RETENTION_DAYS  - Days to retain backups (default: 30)
    LOG_FILE        - Log file path (default: /var/log/pg_backup.log)
    SLACK_WEBHOOK_URL - Slack webhook URL for notifications
    EMAIL_TO        - Email address for notifications

OPTIONS:
    -h, --help      Show this help message

EXAMPLES:
    # Basic backup
    DB_NAME=myapp S3_BUCKET=my-backups ./backup_pg.sh
    
    # With Slack notifications
    DB_NAME=myapp S3_BUCKET=my-backups SLACK_WEBHOOK_URL=https://hooks.slack.com/... ./backup_pg.sh
    
    # Custom retention
    DB_NAME=myapp S3_BUCKET=my-backups RETENTION_DAYS=7 ./backup_pg.sh

EOF
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -h|--help)
            show_help
            exit 0
            ;;
        *)
            echo "Unknown option: $1" >&2
            echo "Use -h or --help for usage information" >&2
            exit 1
            ;;
    esac
done

# Logging function with timestamps and levels
log() {
    local level="$1"
    local message="$2"
    local timestamp=$(date -u +%Y-%m-%dT%H:%M:%SZ)
    local log_entry="[$timestamp] [$level] $message"
    
    echo "$log_entry" | tee -a "$LOG_FILE"
}

# Cleanup function
cleanup() {
    local exit_code=$?
    if [[ -d "$TEMP_DIR" ]]; then
        log "INFO" "Cleaning up temporary directory: $TEMP_DIR"
        rm -rf "$TEMP_DIR"
    fi
    
    if [[ $exit_code -ne 0 ]]; then
        log "ERROR" "Script failed with exit code: $exit_code"
        send_notification "ERROR" "PostgreSQL backup failed" "Backup of database '$DB_NAME' failed with exit code $exit_code. Check logs for details."
    fi
    
    exit $exit_code
}

# Set trap for cleanup
trap cleanup EXIT INT TERM

# Notification function
send_notification() {
    local level="$1"
    local subject="$2"
    local message="$3"
    
    # Determine color based on level
    local color="good"
    local emoji=":white_check_mark:"
    case "$level" in
        "WARN")
            color="warning"
            emoji=":warning:"
            ;;
        "ERROR")
            color="danger"
            emoji=":x:"
            ;;
    esac
    
    # Send Slack notification if webhook URL is provided
    if [[ -n "$SLACK_WEBHOOK_URL" ]]; then
        log "INFO" "Sending Slack notification"
        local slack_payload=$(cat <<EOF
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
                },
                {
                    "title": "Timestamp",
                    "value": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
                    "short": true
                }
            ],
            "footer": "PostgreSQL Backup Script"
        }
    ]
}
EOF
        )
        
        if ! curl -s -X POST -H 'Content-type: application/json' \
                --data "$slack_payload" \
                "$SLACK_WEBHOOK_URL" >/dev/null; then
            log "WARN" "Failed to send Slack notification"
        fi
    fi
    
    # Send email notification if email address is provided
    if [[ -n "$EMAIL_TO" ]] && command -v mail >/dev/null 2>&1; then
        log "INFO" "Sending email notification"
        local email_body="$message\n\nDatabase: $DB_NAME\nHost: $(hostname)\nTimestamp: $(date -u +%Y-%m-%dT%H:%M:%SZ)\n\nLast few log entries:\n$(tail -10 "$LOG_FILE")"
        
        if ! echo -e "$email_body" | mail -s "$subject" "$EMAIL_TO"; then
            log "WARN" "Failed to send email notification"
        fi
    fi
}

# Validate required tools
validate_dependencies() {
    local missing_deps=()
    
    if ! command -v pg_dump >/dev/null 2>&1; then
        missing_deps+=("pg_dump")
    fi
    
    if ! command -v gzip >/dev/null 2>&1; then
        missing_deps+=("gzip")
    fi
    
    if ! command -v aws >/dev/null 2>&1; then
        missing_deps+=("aws")
    fi
    
    if [[ ${#missing_deps[@]} -gt 0 ]]; then
        log "ERROR" "Missing required dependencies: ${missing_deps[*]}"
        exit 1
    fi
}

# Test database connectivity
test_db_connection() {
    log "INFO" "Testing database connectivity"
    
    if ! pg_dump --host="$DB_HOST" --port="$DB_PORT" --username="$DB_USER" \
            --no-password --schema-only --format=custom \
            "$DB_NAME" >/dev/null 2>&1; then
        log "ERROR" "Cannot connect to database $DB_NAME"
        exit 1
    fi
    
    log "INFO" "Database connection successful"
}

# Create database backup
create_backup() {
    log "INFO" "Starting backup of database: $DB_NAME"
    
    mkdir -p "$TEMP_DIR"
    local backup_path="$TEMP_DIR/$BACKUP_FILENAME"
    
    # Create compressed backup using custom format for better compression and features
    if ! pg_dump --host="$DB_HOST" --port="$DB_PORT" --username="$DB_USER" \
            --no-password --format=custom --compress=6 --no-owner --no-privileges \
            --verbose "$DB_NAME" | gzip > "$backup_path" 2>>"$LOG_FILE"; then
        log "ERROR" "pg_dump failed"
        exit 1
    fi
    
    # Get backup size
    local backup_size=$(du -h "$backup_path" | cut -f1)
    log "INFO" "Backup created successfully: $backup_path ($backup_size)"
    
    echo "$backup_path"
}

# Upload backup to S3
upload_to_s3() {
    local backup_path="$1"
    local s3_key="$S3_PREFIX/$BACKUP_FILENAME"
    
    log "INFO" "Uploading backup to S3: s3://$S3_BUCKET/$s3_key"
    
    local upload_start=$(date +%s)
    
    if ! aws s3 cp "$backup_path" "s3://$S3_BUCKET/$s3_key" \
            --storage-class STANDARD_IA \
            --metadata "database=$DB_NAME,created=$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
            --no-progress 2>>"$LOG_FILE"; then
        log "ERROR" "S3 upload failed"
        exit 1
    fi
    
    local upload_duration=$(($(date +%s) - upload_start))
    log "INFO" "S3 upload completed in ${upload_duration}s: s3://$S3_BUCKET/$s3_key"
}

# Rotate old backups in S3
rotate_backups() {
    log "INFO" "Starting backup rotation (keeping last $RETENTION_DAYS days)"
    
    local cutoff_date=$(date -d "$RETENTION_DAYS days ago" +%Y-%m-%d)
    
    # List objects older than cutoff date
    local old_objects
    if ! old_objects=$(aws s3api list-objects-v2 \
            --bucket "$S3_BUCKET" \
            --prefix "$S3_PREFIX/" \
            --query "Contents[?LastModified<='$cutoff_date'].Key" \
            --output text 2>>"$LOG_FILE"); then
        log "WARN" "Failed to list S3 objects for rotation"
        return
    fi
    
    if [[ -z "$old_objects" || "$old_objects" == "None" ]]; then
        log "INFO" "No old backups to delete"
        return
    fi
    
    # Delete old objects
    local delete_count=0
    for object_key in $old_objects; do
        if [[ "$object_key" =~ $S3_PREFIX.*\.sql\.gz$ ]]; then
            log "INFO" "Deleting old backup: $object_key"
            if aws s3 rm "s3://$S3_BUCKET/$object_key" 2>>"$LOG_FILE"; then
                ((delete_count++))
            else
                log "WARN" "Failed to delete: $object_key"
            fi
        fi
    done
    
    log "INFO" "Rotation completed: deleted $delete_count old backups"
}

# Main execution
main() {
    log "INFO" "Starting PostgreSQL backup process"
    
    # Validate environment and dependencies
    validate_dependencies
    test_db_connection
    
    # Create backup
    local backup_start=$(date +%s)
    local backup_path
    backup_path=$(create_backup)
    
    # Upload to S3
    upload_to_s3 "$backup_path"
    
    # Rotate old backups
    rotate_backups
    
    # Calculate total duration
    local total_duration=$(($(date +%s) - backup_start))
    local backup_size=$(du -h "$backup_path" | cut -f1)
    
    log "INFO" "Backup process completed successfully in ${total_duration}s"
    
    # Send success notification
    send_notification "INFO" "PostgreSQL backup completed successfully" \
        "Backup of database '$DB_NAME' completed successfully.\n\nBackup size: $backup_size\nDuration: ${total_duration}s\nS3 location: s3://$S3_BUCKET/$S3_PREFIX/$BACKUP_FILENAME"
}

# Execute main function
main "$@"
```