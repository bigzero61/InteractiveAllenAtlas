#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 was not found. Please install Python 3.10 or newer first." >&2
  exit 1
fi

python3 -m venv .venv
"$ROOT/.venv/bin/python" -m pip install --upgrade pip
"$ROOT/.venv/bin/python" -m pip install -r requirements.txt

mkdir -p "$ROOT/data/cache" "$ROOT/data/uploads"
echo "Install complete."
echo "Run with: $ROOT/run.sh"
echo "Optional command install: $ROOT/scripts/install_atlas_command.sh"
