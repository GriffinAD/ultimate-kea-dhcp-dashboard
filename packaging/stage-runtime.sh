#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STAGE_DIR="$ROOT_DIR/packaging/stage"

rm -rf "$STAGE_DIR"
mkdir -p "$STAGE_DIR"

for dir in bin lib plugins static data etc; do
  if [[ -d "$ROOT_DIR/$dir" ]]; then
    cp -r "$ROOT_DIR/$dir" "$STAGE_DIR/"
  fi
done

if [[ -d "$ROOT_DIR/config" ]]; then
  mkdir -p "$STAGE_DIR/config"
  cp -r "$ROOT_DIR/config/." "$STAGE_DIR/config/"
fi

if [[ -f "$ROOT_DIR/VERSION" ]]; then
  cp "$ROOT_DIR/VERSION" "$STAGE_DIR/"
fi

if [[ -f "$ROOT_DIR/README.md" ]]; then
  cp "$ROOT_DIR/README.md" "$STAGE_DIR/"
fi

if [[ ! -f "$STAGE_DIR/bin/ultimate-kea-dashboard-plugin" ]]; then
  echo "ERROR: plugin runtime entrypoint missing from stage" >&2
  exit 1
fi

echo "$STAGE_DIR"
