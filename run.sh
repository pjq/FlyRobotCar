#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
FLY64_DIR="${FLY64_DIR:-$ROOT/.deps/fly}"

# Reuse a neighboring development checkout when available.
if [[ ! -x "$FLY64_DIR/.venv/bin/python" && -x "$ROOT/../fly/.venv/bin/python" ]]; then
  FLY64_DIR="$ROOT/../fly"
fi
if [[ ! -x "$FLY64_DIR/.venv/bin/python" || ! -f "$FLY64_DIR/.cache/malecns/manifest.json" ]]; then
  echo "MaleCNS dependency is not prepared. Run ./setup.sh first." >&2
  exit 1
fi

export FLY64_DIR
exec "$FLY64_DIR/.venv/bin/python" "$ROOT/robot.py"
