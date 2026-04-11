#!/usr/bin/env bash
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$DIR/../../.." && pwd)"
cd "$REPO_ROOT"
echo "Reproducing autotest..."
if [ -x "$REPO_ROOT/.venv/bin/python" ]; then
  "$REPO_ROOT/.venv/bin/python" pneumo_solver_ui/tools/run_autotest.py --level quick
else
  python3 pneumo_solver_ui/tools/run_autotest.py --level quick
fi
