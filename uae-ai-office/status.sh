#!/usr/bin/env bash
set -u

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
RUN_DIR="$ROOT_DIR/.run"

service_status() {
  local name="$1" pid_file="$2" url="$3" pid http
  if [[ -f "$pid_file" ]] && pid="$(<"$pid_file")" && kill -0 "$pid" 2>/dev/null; then
    http="$(curl --silent --output /dev/null --write-out '%{http_code}' "$url" || true)"
    printf '%s: UP + HTTP %s (PID %s)\n' "$name" "$http" "$pid"
  else
    printf '%s: DOWN + HTTP n/a\n' "$name"
  fi
}

if [[ -f "$ROOT_DIR/backend/.env" ]] && (
  cd "$ROOT_DIR/backend" && python -c 'from app.core.config import settings; from sqlalchemy import create_engine, text; engine=create_engine(settings.database_url); connection=engine.connect(); connection.execute(text("SELECT 1")); connection.close()'
); then
  printf 'PostgreSQL: UP\n'
else
  printf 'PostgreSQL: DOWN\n'
fi
service_status "Backend" "$RUN_DIR/backend.pid" "http://127.0.0.1:8000/v1/health"
service_status "Frontend" "$RUN_DIR/frontend.pid" "http://127.0.0.1:3000/"