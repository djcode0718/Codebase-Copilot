#!/bin/bash
# ─── run_api.sh ───────────────────────────────────────────────────────────────
# Starts the FastAPI backend for Codebase Copilot.
#
# Usage:
#   chmod +x run_api.sh
#   ./run_api.sh
#
# Or for production-like mode (no reload):
#   ./run_api.sh prod
#
# Requirements:
#   - Run from the project root: /path/to/codebase-copilot/
#   - Your conda env must be active: conda activate ai-copilot-env
#   - Ollama must be running: ollama serve
#   - .env file must have SUPABASE_URL and SUPABASE_SERVICE_KEY set
# ──────────────────────────────────────────────────────────────────────────────

set -e

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Codebase Copilot — FastAPI Backend"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Check we're in the right directory
if [ ! -f "app/config.py" ]; then
    echo "❌ ERROR: Run this from the project root (codebase-copilot/)"
    echo "   cd /path/to/codebase-copilot && ./run_api.sh"
    exit 1
fi

# Load environment
if [ -f ".env" ]; then
    echo "✅ Loading .env"
else
    echo "⚠️  No .env file found. Make sure SUPABASE_URL etc. are set."
fi

MODE=${1:-dev}

if [ "$MODE" = "prod" ]; then
    echo "🚀 Starting in PRODUCTION mode (no auto-reload)"
    uvicorn api.main:app --host 0.0.0.0 --port 8000 --workers 1
else
    echo "🔧 Starting in DEVELOPMENT mode (auto-reload on file changes)"
    echo "   API: http://localhost:8000"
    echo "   Docs: http://localhost:8000/docs"
    echo ""
    uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
fi
