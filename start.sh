#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_PORT=8000
FRONTEND_PORT=3000
PYTHON_BIN="$ROOT_DIR/venv_copilot/bin/python"
BACKEND_LOG=""
FRONTEND_LOG=""
BACKEND_PID=""
FRONTEND_PID=""
TAIL_BACK_PID=""
TAIL_FRONT_PID=""

if [[ ! -x "$PYTHON_BIN" ]]; then
  PYTHON_BIN="python"
fi

kill_pid_tree() {
  local pid="${1:-}"
  [[ -z "$pid" ]] && return 0
  [[ "$pid" == "$$" ]] && return 0

  if command -v pkill >/dev/null 2>&1; then
    pkill -TERM -P "$pid" 2>/dev/null || true
  fi
  kill -TERM "$pid" 2>/dev/null || true
  sleep 0.2
  if kill -0 "$pid" 2>/dev/null; then
    if command -v pkill >/dev/null 2>&1; then
      pkill -KILL -P "$pid" 2>/dev/null || true
    fi
    kill -KILL "$pid" 2>/dev/null || true
  fi
}

kill_previous_start_instances() {
  local current_pid="$$"
  while read -r pid cmd; do
    [[ -z "${pid:-}" ]] && continue
    [[ "$pid" == "$current_pid" ]] && continue
    if [[ "$cmd" == *"start.sh"* ]]; then
      echo "Killing previous start.sh instance (PID $pid) ..."
      kill_pid_tree "$pid"
    fi
  done < <(ps -eo pid=,command=)
}

free_port() {
  local port="$1"
  local pids=()

  if command -v lsof >/dev/null 2>&1; then
    while read -r pid; do
      [[ -n "${pid:-}" ]] && pids+=("$pid")
    done < <(lsof -ti tcp:"$port" -sTCP:LISTEN 2>/dev/null || true)
  elif command -v fuser >/dev/null 2>&1; then
    while read -r pid; do
      [[ -n "${pid:-}" ]] && pids+=("$pid")
    done < <(fuser "${port}/tcp" 2>/dev/null | tr ' ' '\n' | grep -E '^[0-9]+$' || true)
  fi

  if [[ ${#pids[@]} -gt 0 ]]; then
    for pid in "${pids[@]}"; do
      [[ -z "$pid" ]] && continue
      [[ "$pid" == "$$" ]] && continue
      echo "Freeing port $port (PID $pid) ..."
      kill_pid_tree "$pid"
    done
  fi
}

start_log_tailer() {
  local file="$1"
  local prefix="$2"
  tail -n +1 -f "$file" 2>/dev/null | awk -v prefix="$prefix" '{ print "[" prefix "] " $0; fflush(); }' &
  echo $!
}

cleanup() {
  local exit_code=$?
  trap - INT TERM EXIT

  [[ -n "${TAIL_BACK_PID:-}" ]] && kill "$TAIL_BACK_PID" 2>/dev/null || true
  [[ -n "${TAIL_FRONT_PID:-}" ]] && kill "$TAIL_FRONT_PID" 2>/dev/null || true
  [[ -n "${BACKEND_PID:-}" ]] && kill_pid_tree "$BACKEND_PID"
  [[ -n "${FRONTEND_PID:-}" ]] && kill_pid_tree "$FRONTEND_PID"

  if [[ -n "${BACKEND_LOG:-}" && -f "$BACKEND_LOG" ]]; then rm -f "$BACKEND_LOG"; fi
  if [[ -n "${FRONTEND_LOG:-}" && -f "$FRONTEND_LOG" ]]; then rm -f "$FRONTEND_LOG"; fi

  exit "$exit_code"
}

trap cleanup INT TERM EXIT

kill_previous_start_instances
free_port "$BACKEND_PORT"
free_port "$FRONTEND_PORT"
sleep 0.4

BACKEND_LOG="$(mktemp)"
FRONTEND_LOG="$(mktemp)"

pushd "$ROOT_DIR" >/dev/null

echo "Starting backend (uvicorn) ..."
PYTHONUNBUFFERED=1 "$PYTHON_BIN" -m uvicorn api.main:app --reload --port "$BACKEND_PORT" >"$BACKEND_LOG" 2>&1 &
BACKEND_PID=$!

echo "Starting frontend (npm run dev) ..."
( cd "$ROOT_DIR/frontend" && npm run dev >"$FRONTEND_LOG" 2>&1 ) &
FRONTEND_PID=$!

TAIL_BACK_PID="$(start_log_tailer "$BACKEND_LOG" backend)"
TAIL_FRONT_PID="$(start_log_tailer "$FRONTEND_LOG" frontend)"

printf '\nBoth servers are running. Press Ctrl+C to stop.\n'
printf '  Backend:  http://localhost:%s\n' "$BACKEND_PORT"
printf '  Frontend: http://localhost:%s\n\n' "$FRONTEND_PORT"

while true; do
  if ! kill -0 "$BACKEND_PID" 2>/dev/null || ! kill -0 "$FRONTEND_PID" 2>/dev/null; then
    break
  fi
  sleep 0.2
done

popd >/dev/null
