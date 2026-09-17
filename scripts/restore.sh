#!/bin/sh
set -eu

DUMP_FILE=${1:-}
if [ -z "$DUMP_FILE" ]; then
  echo "Usage: restore.sh <db.dump> [media.tar.gz]" >&2
  exit 1
fi

if [ -z "${DATABASE_URL:-}" ]; then
  echo "DATABASE_URL is not set" >&2
  exit 1
fi

echo "Restoring database from $DUMP_FILE ..."
pg_restore --clean --if-exists --no-owner --dbname="$DATABASE_URL" "$DUMP_FILE"

MEDIA_ARCHIVE=${2:-}
if [ -n "$MEDIA_ARCHIVE" ]; then
  TARGET=${MEDIA_ROOT:-./media}
  echo "Restoring media into $TARGET ..."
  mkdir -p "$TARGET"
  tar -xzf "$MEDIA_ARCHIVE" -C "$(dirname "$TARGET")"
fi

echo "Restore completed."
