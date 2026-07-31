#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_PORT=8000
FRONTEND_PORT=3000
PYTHON_BIN="$ROOT_DIR/venv_copilot/bin/python"

if [[ ! -x "$PYTHON_BIN" ]]; then
  PYTHON_BIN="python3"
fi
if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  PYTHON_BIN="python"
fi

BACKEND_PID=""
FRONTEND_PID=""
BACKEND_LOG=""
FRONTEND_LOG=""

kill_pid_tree() {
  local pid="${1:-}"
  [[ -z "$pid" ]] && return 0
  [[ "$pid" == "$$" ]] && return 0
  if command -v pkill >/dev/null 2>&1; then
    pkill -KILL -P "$pid" 2>/dev/null || true
  fi
  kill -KILL "$pid" 2>/dev/null || true
}

free_port() {
  local port="$1"
  if command -v lsof >/dev/null 2>&1; then
    lsof -ti tcp:"$port" -sTCP:LISTEN 2>/dev/null | while read -r pid; do
      [[ -z "$pid" || "$pid" == "$$" ]] && continue
      echo "Freeing port $port (PID $pid) ..."
      kill_pid_tree "$pid"
    done
  elif command -v fuser >/dev/null 2>&1; then
    fuser -k "${port}/tcp" 2>/dev/null || true
  fi
}

# Stream a log file to stdout with a prefix, in the background.
# Captures the tailer PID into the variable named by $3.
start_tailer() {
  local logfile="$1"
  local prefix="$2"
  # tail -F (uppercase) is more reliable on macOS for newly created files.
  # Redirect stderr so "file not found" during startup is silent.
  tail -F "$logfile" 2>/dev/null | awk -v p="$prefix" '{ print "[" p "] " $0; fflush(); }' &
}

cleanup() {
  trap - INT TERM EXIT
  echo ""
  echo "Stopping servers..."
  [[ -n "${BACKEND_PID:-}" ]]  && kill_pid_tree "$BACKEND_PID"  2>/dev/null || true
  [[ -n "${FRONTEND_PID:-}" ]] && kill_pid_tree "$FRONTEND_PID" 2>/dev/null || true
  sleep 0.3
  free_port "$BACKEND_PORT" 2>/dev/null || true
  free_port "$FRONTEND_PORT" 2>/dev/null || true
  [[ -n "${BACKEND_LOG:-}"  && -f "$BACKEND_LOG"  ]] && rm -f "$BACKEND_LOG"
  [[ -n "${FRONTEND_LOG:-}" && -f "$FRONTEND_LOG" ]] && rm -f "$FRONTEND_LOG"
  echo "Stopped."
  exit 0
}
trap cleanup INT TERM EXIT

# Kill previous instances of this script.
current_pid="$$"
ps -eo pid=,command= 2>/dev/null | while read -r pid cmd; do
  [[ -z "${pid:-}" || "$pid" == "$current_pid" ]] && continue
  if [[ "$cmd" == *"start.sh"* ]]; then
    echo "Killing previous start.sh instance (PID $pid) ..."
    kill_pid_tree "$pid" 2>/dev/null || true
  fi
done

free_port "$BACKEND_PORT"
free_port "$FRONTEND_PORT"
sleep 0.4

cd "$ROOT_DIR"

# Use temp log files so we can track the ACTUAL process PIDs (not pipe PIDs).
BACKEND_LOG="$(mktemp /tmp/cc-backend.XXXXXX)"
FRONTEND_LOG="$(mktemp /tmp/cc-frontend.XXXXXX)"

echo "Starting backend (uvicorn) ..."
PYTHONUNBUFFERED=1 "$PYTHON_BIN" -m uvicorn api.main:app --reload --port "$BACKEND_PORT" \
  >"$BACKEND_LOG" 2>&1 &
BACKEND_PID=$!

echo "Starting frontend (npm run dev) ..."
( cd "$ROOT_DIR/frontend" && npm run dev >"$FRONTEND_LOG" 2>&1 ) &
FRONTEND_PID=$!

# Start log tailers — tail -F handles the file appearing after a brief delay on macOS.
start_tailer "$BACKEND_LOG"  "backend"
start_tailer "$FRONTEND_LOG" "frontend"

printf '\nBoth servers are running. Press Ctrl+C to stop.\n'
printf '  Backend:  http://localhost:%s\n' "$BACKEND_PORT"
printf '  Frontend: http://localhost:%s\n\n' "$FRONTEND_PORT"

# Monitor the actual server processes (not pipe PIDs).
# Exit if either server dies unexpectedly.
while true; do
  if ! kill -0 "$BACKEND_PID" 2>/dev/null; then
    echo "[start.sh] Backend exited unexpectedly (check logs above)." >&2
    break
  fi
  if ! kill -0 "$FRONTEND_PID" 2>/dev/null; then
    echo "[start.sh] Frontend exited unexpectedly (check logs above)." >&2
    break
  fi
  sleep 0.5
done
