#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
RUN_DIR="$ROOT_DIR/.run"

stop_pid_file() {
  local name="$1" pid_file="$2" pid command
  [[ -f "$pid_file" ]] || { printf '%s: already stopped\n' "$name"; return 0; }
  pid="$(<"$pid_file")"
  if [[ ! "$pid" =~ ^[0-9]+$ ]] || ! kill -0 "$pid" 2>/dev/null; then
    rm -f "$pid_file"
    printf '%s: already stopped\n' "$name"
    return 0
  fi
  command="$(tr '\0' ' ' < "/proc/$pid/cmdline" 2>/dev/null || true)"
  if [[ "$(readlink "/proc/$pid/cwd" 2>/dev/null || true)" != "$ROOT_DIR"/* ]]; then
    printf 'ERROR: refusing to stop PID %s because it is not owned by this project\n' "$pid" >&2
    return 1
  fi
  if [[ "$name" == "Frontend" ]]; then
    kill -- "-$pid" 2>/dev/null || true
  else
    kill "$pid" 2>/dev/null || true
  fi
  for _ in {1..20}; do
    kill -0 "$pid" 2>/dev/null || break
    sleep 0.25
  done
  if kill -0 "$pid" 2>/dev/null; then
    kill -TERM "$pid" 2>/dev/null || true
  fi
  rm -f "$pid_file"
  printf '%s: stopped\n' "$name"
}

stop_pid_file "Backend" "$RUN_DIR/backend.pid"
stop_pid_file "Frontend" "$RUN_DIR/frontend.pid"