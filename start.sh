#!/bin/bash
set -e

cd "$(dirname "$0")"

if [ -z "$ANTHROPIC_API_KEY" ]; then
  echo ""
  echo "  ERROR: ANTHROPIC_API_KEY is not set."
  echo ""
  echo "  Run:  export ANTHROPIC_API_KEY=sk-ant-..."
  echo "  Then: bash start.sh"
  echo ""
  exit 1
fi

python3 app.py
