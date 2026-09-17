#!/bin/sh
set -eu

STAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR=${BACKUP_DIR:-./backups}
mkdir -p "$BACKUP_DIR"

if [ -z "${DATABASE_URL:-}" ]; then
  echo "DATABASE_URL is not set" >&2
  exit 1
fi

# Retention: keep last 14 daily dumps by default.
RETENTION_DAYS=${RETENTION_DAYS:-14}

echo "Creating database dump..."
pg_dump "$DATABASE_URL" --format=custom --file "$BACKUP_DIR/db_${STAMP}.dump"

if [ -d "${MEDIA_ROOT:-./media}" ]; then
  echo "Archiving media..."
  tar -czf "$BACKUP_DIR/media_${STAMP}.tar.gz" -C "$(dirname "${MEDIA_ROOT:-./media}")" "$(basename "${MEDIA_ROOT:-./media}")"
fi

find "$BACKUP_DIR" -type f -mtime +"$RETENTION_DAYS" -name 'db_*.dump' -delete
find "$BACKUP_DIR" -type f -mtime +"$RETENTION_DAYS" -name 'media_*.tar.gz' -delete

echo "Backup completed: $BACKUP_DIR/db_${STAMP}.dump"
