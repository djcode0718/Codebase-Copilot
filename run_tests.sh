#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# run_tests.sh  —  Run the API test suite
#
# Usage:
#   ./run_tests.sh              # Run all tests
#   ./run_tests.sh -k models    # Run only model tests
#   ./run_tests.sh -x           # Stop on first failure
#   ./run_tests.sh --cov        # Run with coverage report
# ─────────────────────────────────────────────────────────────────────────────

set -e

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
    export $(grep -v '^#' .env | grep -v '^$' | xargs)
else
    echo "⚠  No .env found — using test defaults"
fi

# ── Install test dependencies if needed ───────────────────────────────────────
pip install -q pytest pytest-asyncio httpx 2>/dev/null || true

# ── Run tests ─────────────────────────────────────────────────────────────────
if [ "$1" == "--cov" ]; then
    pip install -q pytest-cov 2>/dev/null || true
    python -m pytest tests/ \
        --cov=api \
        --cov-report=term-missing \
        --cov-report=html:htmlcov \
        "${@:2}"
    echo ""
    echo "📊 Coverage report saved to: htmlcov/index.html"
else
    python -m pytest tests/ "$@"
fi

echo ""
echo "✅  All tests completed."
