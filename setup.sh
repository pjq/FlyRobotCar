#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
FLY64_DIR="${FLY64_DIR:-$ROOT/.deps/fly}"

command -v git >/dev/null || { echo "git is required" >&2; exit 1; }
command -v brew >/dev/null || { echo "Homebrew is required on macOS" >&2; exit 1; }

if [[ ! -d "$FLY64_DIR/.git" ]]; then
  mkdir -p "$(dirname "$FLY64_DIR")"
  git clone https://github.com/ornata/fly.git "$FLY64_DIR"
fi

# Installs Python dependencies and prepares ~1.2 GB of MaleCNS data.
"$FLY64_DIR/run-fly64" --prepare-data

echo "Setup complete. Run: $ROOT/run.sh"
