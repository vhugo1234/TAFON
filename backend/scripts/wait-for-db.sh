#!/usr/bin/env sh
# backend/scripts/wait-for-db.sh
# Aguarda o banco ficar disponível antes de seguir.
# Usa pg_isready quando disponível; caso contrário usa um pequeno check em Python (psycopg2).
set -eu

HOST="${DB_HOST:-db}"
PORT="${DB_PORT:-5432}"
USER="${DB_USER:-postgres}"
DB="${DB_NAME:-postgres}"
TIMEOUT="${WAIT_FOR_DB_TIMEOUT:-60}"

echo "Waiting for database ${HOST}:${PORT} (db=${DB}, user=${USER})..."

count=0
while true; do
  # se pg_isready existir, use-o
  if command -v pg_isready >/dev/null 2>&1; then
    if pg_isready -h "$HOST" -p "$PORT" -U "$USER" -d "$DB" >/dev/null 2>&1; then
      echo "Database is ready (pg_isready)."
      break
    fi
  else
    # fallback: tentar conectar com psycopg2 via Python
    if python - <<'PY' >/dev/null 2>&1
import os, sys
try:
    import psycopg2
    conn = psycopg2.connect(
        host=os.getenv("DB_HOST","db"),
        port=int(os.getenv("DB_PORT",5432)),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        dbname=os.getenv("DB_NAME")
    )
    conn.close()
    sys.exit(0)
except Exception:
    sys.exit(1)
PY
    then
      echo "Database is ready (python check)."
      break
    fi
  fi

  count=$((count + 1))
  if [ "$count" -ge "$TIMEOUT" ]; then
    echo "Timed out waiting for database after ${TIMEOUT} seconds"
    exit 1
  fi
  echo "Database not ready yet (attempt $count/${TIMEOUT}) — sleeping 1s..."
  sleep 1
done

exit 0