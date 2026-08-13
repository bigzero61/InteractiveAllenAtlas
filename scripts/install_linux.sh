#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

VENV_DIR="${INTERACTIVE_ATLAS_VENV:-${XDG_DATA_HOME:-$HOME/.local/share}/interactive-allen-atlas/venv}"

PYTHON_BIN=""
for candidate in python3.12 python3.11 python3.10 python3; do
  if command -v "$candidate" >/dev/null 2>&1; then
    version="$("$candidate" - <<'PY'
import sys
print(f"{sys.version_info.major}.{sys.version_info.minor}")
PY
)"
    case "$version" in
      3.10|3.11|3.12)
        PYTHON_BIN="$candidate"
        break
        ;;
    esac
  fi
done

if [[ -z "$PYTHON_BIN" ]]; then
  echo "Python 3.10, 3.11, or 3.12 was not found. Please install one of these versions first." >&2
  exit 1
fi

"$PYTHON_BIN" -m venv "$VENV_DIR"
"$VENV_DIR/bin/python" -m pip install --upgrade pip
"$VENV_DIR/bin/python" -m pip install -r requirements.txt

mkdir -p "$ROOT/data/cache" "$ROOT/data/uploads"
echo "Install complete."
echo "Virtual environment: $VENV_DIR"
echo "Run with: $ROOT/run.sh"
echo "Optional command install: $ROOT/scripts/install_atlas_command.sh"
