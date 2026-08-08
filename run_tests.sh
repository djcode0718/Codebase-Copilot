#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# run_tests.sh  —  Run the API test suite
#
# Usage:
#   ./run_tests.sh              # Run all tests
#   ./run_tests.sh -k models    # Run only model tests
#   ./run_tests.sh -x           # Stop on first failure
#   ./run_tests.sh --cov        # Run with coverage report
#   ./run_tests.sh --lane unit
#   ./run_tests.sh --lane integration
#   ./run_tests.sh --lane unit --budget-seconds 60
# ─────────────────────────────────────────────────────────────────────────────

set -e

LANE="all"
BUDGET_SECONDS=60
EXTRA_ARGS=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --lane)
      LANE="$2"
      shift 2
      ;;
    --budget-seconds)
      BUDGET_SECONDS="$2"
      shift 2
      ;;
    *)
      EXTRA_ARGS+=("$1")
      shift
      ;;
  esac
done

PROJECT_ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_ROOT"

echo ""
echo "╔══════════════════════════════════════════════════════╗"
echo "║         Codebase Copilot — API Test Suite            ║"
echo "╚══════════════════════════════════════════════════════╝"
echo ""

# ── Check env ─────────────────────────────────────────────────────────────────
if [ -f ".env" ]; then
    echo "✓  Found .env — loading environment variables"
    while IFS= read -r line || [ -n "$line" ]; do
        line=$(echo "$line" | sed 's/#.*//')
        line=$(echo "$line" | xargs)
        if [ -n "$line" ] && [[ "$line" == *"="* ]]; then
            export "$line"
        fi
    done < ".env"
else
    echo "⚠  No .env found — using test defaults"
fi

# ── Install test dependencies if needed ───────────────────────────────────────
pip install -q pytest pytest-asyncio httpx 2>/dev/null || true

# ── Run tests ─────────────────────────────────────────────────────────────────
RUN_COV=false
FILTERED_ARGS=()
for arg in "${EXTRA_ARGS[@]}"; do
  if [ "$arg" == "--cov" ]; then
    RUN_COV=true
  else
    FILTERED_ARGS+=("$arg")
  fi
done

if [ "$RUN_COV" == "true" ]; then
    pip install -q pytest-cov 2>/dev/null || true
    python -m pytest tests/ \
        --cov=api \
        --cov-report=term-missing \
        --cov-report=html:htmlcov \
        "${FILTERED_ARGS[@]}"
    echo ""
    echo "📊 Coverage report saved to: htmlcov/index.html"
else
    START_TS=$(date +%s)
    if [ "$LANE" == "unit" ]; then
        python -m pytest tests/unit -m unit "${FILTERED_ARGS[@]}"
    elif [ "$LANE" == "integration" ]; then
        python -m pytest tests/integration -m "integration and not slow" "${FILTERED_ARGS[@]}"
    else
        python -m pytest tests/ "${FILTERED_ARGS[@]}"
    fi
    END_TS=$(date +%s)
    ELAPSED=$((END_TS - START_TS))
    if [ "$LANE" != "all" ] && [ "$ELAPSED" -gt "$BUDGET_SECONDS" ]; then
        echo "❌ ${LANE} lane exceeded budget: ${ELAPSED}s > ${BUDGET_SECONDS}s"
        exit 1
    fi
fi

echo ""
echo "✅  All tests completed."
