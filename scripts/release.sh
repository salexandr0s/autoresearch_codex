#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="${1:-dist/release}"
DRY_RUN=0

if [[ "${1:-}" == "--dry-run" ]]; then
  OUT="dist/release"
  DRY_RUN=1
fi

cd "$ROOT"
python3 scripts/validate-codex-assets.py

if [[ "$DRY_RUN" -eq 1 ]]; then
  echo "release dry-run passed"
  exit 0
fi

rm -rf "$OUT"
mkdir -p "$OUT"

copy_item() {
  local item="$1"
  mkdir -p "$OUT/$(dirname "$item")"
  cp -R "$item" "$OUT/$item"
}

for item in \
  AGENTS.md \
  README.md \
  CONTRIBUTING.md \
  .gitignore \
  .codex \
  .agents \
  .autoresearch \
  codex \
  docs \
  scripts \
  test-fixtures \
  legacy
  do
  copy_item "$item"
done

mkdir -p "$OUT/.autoresearch/runs"
find "$OUT/.autoresearch/runs" -mindepth 1 -maxdepth 1 ! -name '.gitkeep' -exec rm -rf {} +
touch "$OUT/.autoresearch/runs/.gitkeep"

echo "release bundle staged at $OUT"
