#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

VENV_DIR="${INTERACTIVE_ATLAS_VENV:-${XDG_DATA_HOME:-$HOME/.local/share}/interactive-allen-atlas/venv}"
if [[ -x "$VENV_DIR/bin/python" ]]; then
  exec "$VENV_DIR/bin/python" main.py "$@"
fi

if [[ -x "$ROOT/.venv/bin/python" ]]; then
  echo "Warning: using project-local .venv. On mounted drives this may fail for NumPy/SciPy binary modules." >&2
  exec "$ROOT/.venv/bin/python" main.py "$@"
fi

exec python3 main.py "$@"
