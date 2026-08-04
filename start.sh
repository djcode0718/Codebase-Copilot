#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_PORT=8000
FRONTEND_PORT=3000
BACKEND_LOG=""
FRONTEND_LOG=""
BACKEND_PID=""
FRONTEND_PID=""
TAIL_BACKEND_PID=""
TAIL_FRONTEND_PID=""

BACKEND_RELOAD="${BACKEND_RELOAD:-true}"
STARTUP_REQUIRE_HTTP_READY="${STARTUP_REQUIRE_HTTP_READY:-true}"
STARTUP_TIMEOUT_SECONDS="${STARTUP_TIMEOUT_SECONDS:-60}"

command_exists() {
  command -v "$1" >/dev/null 2>&1
}

is_truthy() {
  local v
  v="$(printf '%s' "${1:-}" | tr '[:upper:]' '[:lower:]')"
  [[ "$v" == "1" || "$v" == "true" || "$v" == "yes" || "$v" == "on" ]]
}

kill_pid_tree() {
  local pid="${1:-}"
  [[ -z "$pid" || "$pid" == "$$" ]] && return 0

  if command_exists pkill; then
    pkill -TERM -P "$pid" 2>/dev/null || true
  fi
  kill -TERM "$pid" 2>/dev/null || true
  sleep 0.2

  if kill -0 "$pid" 2>/dev/null; then
    if command_exists pkill; then
      pkill -KILL -P "$pid" 2>/dev/null || true
    fi
    kill -KILL "$pid" 2>/dev/null || true
  fi
}

port_has_listener() {
  local port="$1"
  if command_exists lsof; then
    lsof -ti tcp:"$port" -sTCP:LISTEN >/dev/null 2>&1
    return $?
  fi
  if command_exists ss; then
    ss -lnt "( sport = :$port )" 2>/dev/null | tail -n +2 | grep -q .
    return $?
  fi
  if command_exists netstat; then
    netstat -an 2>/dev/null | grep -E "[\.:]$port[[:space:]]" | grep -q LISTEN
    return $?
  fi
  return 1
}

free_port() {
  local port="$1"
  if command_exists lsof; then
    while IFS= read -r pid; do
      [[ -z "$pid" || "$pid" == "$$" ]] && continue
      echo "Freeing port $port (PID $pid) ..."
      kill_pid_tree "$pid"
    done < <(lsof -ti tcp:"$port" -sTCP:LISTEN 2>/dev/null || true)
    return 0
  fi

  if command_exists fuser; then
    fuser -k "${port}/tcp" 2>/dev/null || true
  fi
}

mktemp_file() {
  local template="$1"
  if path=$(mktemp "$template" 2>/dev/null); then
    printf '%s' "$path"
    return 0
  fi
  mktemp -t "$(basename "$template")"
}

start_tailer() {
  local logfile="$1"
  local prefix="$2"
  local pid_var="$3"
  tail -F "$logfile" 2>/dev/null | awk -v p="$prefix" '{ print "[" p "] " $0; fflush(); }' &
  printf -v "$pid_var" '%s' "$!"
}

cleanup() {
  trap - INT TERM EXIT
  echo
  echo "Stopping servers..."

  [[ -n "$TAIL_BACKEND_PID" ]] && kill "$TAIL_BACKEND_PID" 2>/dev/null || true
  [[ -n "$TAIL_FRONTEND_PID" ]] && kill "$TAIL_FRONTEND_PID" 2>/dev/null || true

  [[ -n "$BACKEND_PID" ]] && kill_pid_tree "$BACKEND_PID"
  [[ -n "$FRONTEND_PID" ]] && kill_pid_tree "$FRONTEND_PID"

  sleep 0.3
  free_port "$BACKEND_PORT"
  free_port "$FRONTEND_PORT"

  [[ -n "$BACKEND_LOG" && -f "$BACKEND_LOG" ]] && rm -f "$BACKEND_LOG"
  [[ -n "$FRONTEND_LOG" && -f "$FRONTEND_LOG" ]] && rm -f "$FRONTEND_LOG"

  echo "Stopped."
  exit 0
}
trap cleanup INT TERM EXIT

kill_previous_start_instances() {
  local current_pid="$$"
  while IFS= read -r line; do
    local pid
    pid="$(awk '{print $1}' <<<"$line")"
    [[ -z "$pid" || "$pid" == "$current_pid" ]] && continue
    echo "Killing previous start.sh instance (PID $pid) ..."
    kill_pid_tree "$pid"
  done < <(ps -eo pid=,command= | grep "start.sh" | grep -v "grep" || true)
}

resolve_python_bin() {
  local candidates=(
    "$ROOT_DIR/.venv/bin/python"
    "$ROOT_DIR/venv_copilot/bin/python"
    "$ROOT_DIR/venv/bin/python"
  )
  local candidate
  for candidate in "${candidates[@]}"; do
    if [[ -x "$candidate" ]]; then
      printf '%s' "$candidate"
      return 0
    fi
  done

  if command_exists python3; then
    printf '%s' "python3"
    return 0
  fi
  if command_exists python; then
    printf '%s' "python"
    return 0
  fi

  return 1
}

http_ready() {
  local url="$1"
  command_exists curl || return 0
  curl -fsS --max-time 2 "$url" >/dev/null 2>&1
}

wait_for_ready() {
  local timeout_seconds="$1"
  local deadline=$((SECONDS + timeout_seconds))

  while (( SECONDS < deadline )); do
    if ! kill -0 "$BACKEND_PID" 2>/dev/null || ! kill -0 "$FRONTEND_PID" 2>/dev/null; then
      return 1
    fi

    local ports_ready=false
    if port_has_listener "$BACKEND_PORT" && port_has_listener "$FRONTEND_PORT"; then
      ports_ready=true
    fi

    if [[ "$ports_ready" == "true" ]]; then
      if is_truthy "$STARTUP_REQUIRE_HTTP_READY"; then
        if http_ready "http://127.0.0.1:${BACKEND_PORT}/api/health" && http_ready "http://127.0.0.1:${FRONTEND_PORT}/"; then
          return 0
        fi
      else
        return 0
      fi
    fi

    sleep 0.25
  done

  return 1
}

if ! command_exists npm; then
  echo "npm is not available on PATH. Install Node.js and retry." >&2
  exit 1
fi

PYTHON_BIN="$(resolve_python_bin || true)"
if [[ -z "$PYTHON_BIN" ]]; then
  echo "Python interpreter not found. Expected .venv/ or venv_copilot/, or python on PATH." >&2
  exit 1
fi

kill_previous_start_instances
free_port "$BACKEND_PORT"
free_port "$FRONTEND_PORT"
sleep 0.4

cd "$ROOT_DIR"

BACKEND_LOG="$(mktemp_file "/tmp/cc-backend.XXXXXX")"
FRONTEND_LOG="$(mktemp_file "/tmp/cc-frontend.XXXXXX")"

echo "Starting backend (uvicorn) ..."
BACKEND_ARGS=(
  -m uvicorn api.main:app
  --host 0.0.0.0
  --port "$BACKEND_PORT"
)
if is_truthy "$BACKEND_RELOAD"; then
  BACKEND_ARGS+=(
    --reload
    --reload-dir api
    --reload-dir app
    --reload-exclude=data/repos/*
    --reload-exclude=data/index/*
    --reload-exclude=frontend/.next/*
    --reload-exclude=venv_copilot/*
    --reload-exclude=.venv/*
    --reload-exclude=*.log
    --reload-exclude=*.pyc
    --reload-exclude=__pycache__/*
  )
fi

PYTHONUNBUFFERED=1 "$PYTHON_BIN" "${BACKEND_ARGS[@]}" >"$BACKEND_LOG" 2>&1 &
BACKEND_PID=$!

echo "Starting frontend (npm run dev) ..."
(
  cd "$ROOT_DIR/frontend"
  NO_COLOR=1 FORCE_COLOR=0 CI=1 npm run dev
) >"$FRONTEND_LOG" 2>&1 &
FRONTEND_PID=$!

start_tailer "$BACKEND_LOG" "backend" TAIL_BACKEND_PID
start_tailer "$FRONTEND_LOG" "frontend" TAIL_FRONTEND_PID

if wait_for_ready "$STARTUP_TIMEOUT_SECONDS"; then
  printf '\nBoth servers are running. Press Ctrl+C to stop.\n'
  printf '  Backend:  http://localhost:%s\n' "$BACKEND_PORT"
  printf '  Frontend: http://localhost:%s\n\n' "$FRONTEND_PORT"
else
  echo "One or more servers exited before becoming ready." >&2
  exit 1
fi

while true; do
  if ! kill -0 "$BACKEND_PID" 2>/dev/null; then
    echo "[start.sh] Backend exited unexpectedly (check logs above)." >&2
    exit 1
  fi
  if ! kill -0 "$FRONTEND_PID" 2>/dev/null; then
    echo "[start.sh] Frontend exited unexpectedly (check logs above)." >&2
    exit 1
  fi
  sleep 0.5
done
