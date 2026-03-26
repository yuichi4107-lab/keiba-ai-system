#!/bin/bash
set -euo pipefail

# Only run in remote (web) environment
if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

PROJECT_DIR="${CLAUDE_PROJECT_DIR:-.}"

# Install Python dependencies (suppress output for clean start)
pip install -q -r "$PROJECT_DIR/requirements.txt" 2>/dev/null || true

# Install dev dependencies
pip install -q pytest flake8 2>/dev/null || true

# Set PYTHONPATH for the session
echo 'export PYTHONPATH="."' >> "$CLAUDE_ENV_FILE"

# Ensure `python` command is available (some environments only have python3)
if ! command -v python &>/dev/null && command -v python3 &>/dev/null; then
  echo 'alias python=python3' >> "$CLAUDE_ENV_FILE"
fi

# Create data directories
mkdir -p "$PROJECT_DIR/data/raw" "$PROJECT_DIR/data/processed" "$PROJECT_DIR/models"

# Generate sample data if not present
if [ ! -f "$PROJECT_DIR/data/raw/race_results.csv" ]; then
  cd "$PROJECT_DIR" && PYTHONPATH=. python scripts/generate_sample_data.py 2>/dev/null || true
fi
