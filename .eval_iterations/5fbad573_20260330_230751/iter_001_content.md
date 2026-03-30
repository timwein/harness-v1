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
#   SLACK_WEBHOOK_URL     - Slack webhook for notifications (optional)
#   LOG_FILE              - Log file path (default: /var/log/pg_backup.log)
#

set -euo pipefail

# Configuration with defaults
DB_HOST=${DB_HOST:-"localhost"}
DB_PORT=${DB_PORT:-5432}
DB_USER=${DB_USER:?"DB_USER environment variable is required"}
DB_NAME=${DB_NAME:?"DB_NAME environment variable is required"}
S3_BUCKET=${S3_BUCKET:?"S3_BUCKET environment variable is required"}
S3_PATH=${S3_PATH:-"backups"}
RETENTION_DAYS=${RETENTION_DAYS:-30}
LOG_FILE=${LOG_FILE:-"/var/log/pg_backup.log"}

# Validate required environment variables
: ${PGPASSWORD:?"PGPASSWORD environment variable is required"}

# Create timestamp for backup filename
TIMESTAMP=$(date -u +%Y%m%d_%H%M%S)
BACKUP_NAME="${DB_NAME}_${TIMESTAMP}.sql.gz"
TEMP_DIR=$(mktemp -d)
TEMP_BACKUP="${TEMP_DIR}/${BACKUP_NAME}"

# Log function with timestamps and levels
log() {
    local level="$1"
    local message="$2"
    local timestamp=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
    echo "[$timestamp] [$level] $message" | tee -a "$LOG_FILE"
}

# Cleanup function
cleanup() {
    local exit_code=$?
    if [[ -d "$TEMP_DIR" ]]; then
        rm -rf "$TEMP_DIR"
        log "INFO" "Cleaned up temporary directory: $TEMP_DIR"
    fi
    if [[ $exit_code -ne 0 ]]; then
        log "ERROR" "Script failed with exit code: $exit_code"
        send_notification "ERROR" "PostgreSQL backup failed for database: $DB_NAME" "Exit code: $exit_code. Check logs at $LOG_FILE for details."
    fi
}

# Set trap for cleanup on exit
trap cleanup EXIT

# Notification function
send_notification() {
    local level="$1"
    local title="$2"
    local details="$3"
    
    if [[ -n "${SLACK_WEBHOOK_URL:-}" ]]; then
        local color="good"
        case "$level" in
            "ERROR") color="danger" ;;
            "WARN") color="warning" ;;
        esac
        
        local timestamp=$(date -u +"%Y-%m-%d %H:%M:%S UTC")
        local hostname=$(hostname)
        
        # Get last 10 lines of log for context
        local log_tail=""
        if [[ -f "$LOG_FILE" ]]; then
            log_tail=$(tail -n 10 "$LOG_FILE" | sed 's/"/\\"/g' | sed ':a;N;$!ba;s/\n/\\n/g')
        fi
        
        local payload=$(cat <<EOF
{
    "attachments": [
        {
            "color": "$color",
            "title": "$title",
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
    else
        log "INFO" "No Slack webhook configured, skipping notification"
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
  SLACK_WEBHOOK_URL     - Slack webhook for error notifications
  LOG_FILE              - Log file path (default: /var/log/pg_backup.log)

Examples:
  # Basic usage
  DB_NAME=mydb DB_USER=postgres PGPASSWORD=secret S3_BUCKET=mybucket $0

  # With custom retention and Slack notifications  
  DB_NAME=mydb DB_USER=postgres PGPASSWORD=secret S3_BUCKET=mybucket \\
  RETENTION_DAYS=14 SLACK_WEBHOOK_URL=https://hooks.slack.com/... $0

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
    
    # Create database dump with optimal flags
    log "INFO" "Creating database dump..."
    
pg_dump \
        -h "$DB_HOST" \
        -p "$DB_PORT" \
        -U "$DB_USER" \
        -d "$DB_NAME" \
        --format=custom \
        --no-owner \
        --no-privileges \
        --verbose
 | gzip > "$TEMP_BACKUP"
    
    # Check if backup was created successfully
    if [[ ! -f "$TEMP_BACKUP" ]] || [[ ! -s "$TEMP_BACKUP" ]]; then
        log "ERROR" "Backup file was not created or is empty"
        exit 1
    fi
    
    # Get backup size
    local backup_size=$(du -h "$TEMP_BACKUP" | cut -f1)
    log "INFO" "Backup created successfully, size: $backup_size"
    
    # Upload to S3
    log "INFO" "Uploading backup to S3..."
    aws s3 cp "$TEMP_BACKUP" "s3://$S3_BUCKET/$S3_PATH/$BACKUP_NAME" \
        --storage-class STANDARD_IA \
        --metadata "database=$DB_NAME,created=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    
    if [[ $? -eq 0 ]]; then
        log "INFO" "Successfully uploaded backup to S3"
    else
        log "ERROR" "Failed to upload backup to S3"
        exit 1
    fi
    
    # Rotate old backups
    log "INFO" "Removing backups older than $RETENTION_DAYS days..."
    local cutoff_date=$(date -u -d "$RETENTION_DAYS days ago" +%Y-%m-%d)
    
    # List and delete old backups
    local old_backups=$(aws s3 ls "s3://$S3_BUCKET/$S3_PATH/" --recursive | \
        awk '{print $1" "$2" "$4}' | \
        while read date time file; do
            if [[ "$date" < "$cutoff_date" ]] && [[ "$file" == *"${DB_NAME}_"* ]]; then
                echo "$file"
            fi
        done)
    
    if [[ -n "$old_backups" ]]; then
        local deleted_count=0
        while IFS= read -r file; do
            if [[ -n "$file" ]]; then
                aws s3 rm "s3://$S3_BUCKET/$file"
                ((deleted_count++))
                log "INFO" "Deleted old backup: $file"
            fi
        done <<< "$old_backups"
        log "INFO" "Removed $deleted_count old backup(s)"
    else
        log "INFO" "No old backups found to remove"
    fi
    
    # Calculate duration and finish
    local end_time=$(date +%s)
    local duration=$((end_time - start_time))
    log "INFO" "Backup completed successfully in ${duration}s"
    log "INFO" "Final backup location: s3://$S3_BUCKET/$S3_PATH/$BACKUP_NAME"
    
    # Send success notification if configured
    if [[ -n "${SLACK_WEBHOOK_URL:-}" ]]; then
        send_notification "INFO" "PostgreSQL backup completed successfully" "Database: $DB_NAME, Size: $backup_size, Duration: ${duration}s"
    fi
}

# Ensure log directory exists
mkdir -p "$(dirname "$LOG_FILE")"

# Run main function
main "$@"
```