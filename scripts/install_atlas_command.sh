#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TARGET="${1:-$HOME/.local/bin/atlas}"

mkdir -p "$(dirname "$TARGET")"
cat > "$TARGET" <<EOF
#!/usr/bin/env bash
exec bash "$ROOT/run.sh" "\$@"
EOF
chmod +x "$TARGET"

echo "Installed atlas launcher: $TARGET"
case ":$PATH:" in
  *":$(dirname "$TARGET"):"*) ;;
  *) echo "Add $(dirname "$TARGET") to PATH if 'atlas' is not found in a new terminal." ;;
esac
