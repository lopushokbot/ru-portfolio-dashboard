#!/bin/bash
# Run Russian Portfolio Dashboard v2
# Usage: ./scripts/run.sh [--no-finrange]

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_DIR"

echo "🇷🇺 Russian Portfolio Dashboard v2"
echo "=================================="

python3 -m src.dashboard "$@"

echo ""
echo "Done. Open output/ru_portfolio_dashboard.html in your browser."
