#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
FRONTEND_DIR="$ROOT_DIR/frontend"
RUN_DIR="$ROOT_DIR/.run"
BACKEND_PID="$RUN_DIR/backend.pid"
FRONTEND_PID="$RUN_DIR/frontend.pid"
BACKEND_LOG="$RUN_DIR/backend.log"
FRONTEND_LOG="$RUN_DIR/frontend.log"

mkdir -p "$RUN_DIR"

error() {
  printf 'ERROR: %s\n' "$*" >&2
  exit 1
}

cleanup_on_error() {
  printf 'ERROR: startup failed. Services already started by this run are being stopped.\n' >&2
  "$ROOT_DIR/stop.sh" >/dev/null 2>&1 || true
}
trap cleanup_on_error ERR

pid_is_ours() {
  local pid_file="$1" expected="$2" pid command
  [[ -f "$pid_file" ]] || return 1
  pid="$(<"$pid_file")"
  [[ "$pid" =~ ^[0-9]+$ ]] || return 1
  kill -0 "$pid" 2>/dev/null || return 1
  command="$(tr '\0' ' ' < "/proc/$pid/cmdline" 2>/dev/null || true)"
  [[ "$command" == *"$expected"* ]] && [[ "$(readlink "/proc/$pid/cwd" 2>/dev/null || true)" == "$ROOT_DIR"/* ]]
}

clear_stale_pid() {
  local pid_file="$1"
  if [[ -f "$pid_file" ]] && ! pid_is_ours "$pid_file" ""; then
    rm -f "$pid_file"
  fi
}

wait_for_http() {
  local name="$1" url="$2" pid_file="$3" attempts=0 status
  while (( attempts < 60 )); do
    if ! pid_is_ours "$pid_file" ""; then
      error "$name process exited before becoming ready. See $RUN_DIR."
    fi
    status="$(curl --silent --show-error --output /dev/null --write-out '%{http_code}' "$url" || true)"
    if [[ "$status" == "200" ]]; then
      printf 'SUCCESS: %s is ready (HTTP %s)\n' "$name" "$status"
      return 0
    fi
    attempts=$((attempts + 1))
    sleep 1
  done
  error "$name did not become ready at $url. See $RUN_DIR."
}

frontend_origin="http://localhost:3000,http://127.0.0.1:3000"
if [[ "${CODESPACES:-}" == "true" && -n "${CODESPACE_NAME:-}" && -n "${GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN:-}" ]]; then
  frontend_origin="https://${CODESPACE_NAME}-3000.${GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN},$frontend_origin"
fi

clear_stale_pid "$BACKEND_PID"
clear_stale_pid "$FRONTEND_PID"
command -v curl >/dev/null || error "curl is required"

if pid_is_ours "$BACKEND_PID" "uvicorn"; then
  printf 'Backend already running (PID %s)\n' "$(<"$BACKEND_PID")"
else
  command -v uvicorn >/dev/null || error "uvicorn is required; install backend dependencies first"
  (
    cd "$BACKEND_DIR"
    export FRONTEND_ORIGIN="$frontend_origin"
    exec uvicorn app.main:app --host 0.0.0.0 --port 8000
  ) >>"$BACKEND_LOG" 2>&1 &
  printf '%s\n' "$!" >"$BACKEND_PID"
  printf 'Started backend (PID %s)\n' "$!"
fi

if grep -qE '^DATABASE_URL=.*@(localhost|127\.0\.0\.1)(:[0-9]+)?/' "$BACKEND_DIR/.env"; then
  if command -v pg_isready >/dev/null; then
    pg_isready -q || error "local PostgreSQL is required but is not ready"
  else
    error "pg_isready is required to verify local PostgreSQL"
  fi
  printf 'PostgreSQL: local service is ready\n'
else
  printf 'PostgreSQL: using configured managed database\n'
fi

if pid_is_ours "$FRONTEND_PID" "npm"; then
  printf 'Frontend already running (PID %s)\n' "$(<"$FRONTEND_PID")"
else
  command -v npm >/dev/null || error "npm is required"
  (
    cd "$FRONTEND_DIR"
    exec setsid npm run dev -- --hostname 0.0.0.0 --port 3000
  ) >>"$FRONTEND_LOG" 2>&1 &
  printf '%s\n' "$!" >"$FRONTEND_PID"
  printf 'Started frontend (PID %s)\n' "$!"
fi

wait_for_http "backend" "http://127.0.0.1:8000/v1/health" "$BACKEND_PID"
wait_for_http "frontend" "http://127.0.0.1:3000/" "$FRONTEND_PID"
printf 'SUCCESS: UAE AI Office is running\n'