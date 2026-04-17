#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PACKAGING_DIR="$ROOT_DIR/packaging"
CHANGELOG_FILE="$PACKAGING_DIR/debian/changelog"
OUTPUT_FILE="${1:-$PACKAGING_DIR/RELEASE_NOTES.md}"
FULL_VERSION="$($PACKAGING_DIR/version.sh --full)"

if [[ ! -f "$CHANGELOG_FILE" ]]; then
  echo "Debian changelog not found: $CHANGELOG_FILE" >&2
  exit 1
fi

awk -v version="$FULL_VERSION" '
  BEGIN { in_block=0 }
  $0 ~ "^ultimate-kea-dashboard \\(" version "\\)" { in_block=1; next }
  in_block && $0 ~ /^ -- / { exit }
  in_block { print }
' "$CHANGELOG_FILE" | sed '/^[[:space:]]*$/d' > "$OUTPUT_FILE.tmp"

{
  echo "# Release $FULL_VERSION"
  echo
  if [[ -s "$OUTPUT_FILE.tmp" ]]; then
    cat "$OUTPUT_FILE.tmp"
  else
    echo "- Release metadata updated"
  fi
  echo
} > "$OUTPUT_FILE"

rm -f "$OUTPUT_FILE.tmp"

echo "$OUTPUT_FILE"
