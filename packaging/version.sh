#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VERSION_FILE="$ROOT_DIR/VERSION"

if [[ ! -f "$VERSION_FILE" ]]; then
  echo "VERSION file not found: $VERSION_FILE" >&2
  exit 1
fi

FULL_VERSION="$(tr -d '[:space:]' < "$VERSION_FILE")"
if [[ -z "$FULL_VERSION" ]]; then
  echo "VERSION file is empty" >&2
  exit 1
fi

if [[ "$FULL_VERSION" == *-* ]]; then
  VERSION="${FULL_VERSION%-*}"
  RELEASE="${FULL_VERSION##*-}"
else
  VERSION="$FULL_VERSION"
  RELEASE="1"
fi

case "${1:---full}" in
  --full)
    echo "$FULL_VERSION"
    ;;
  --version)
    echo "$VERSION"
    ;;
  --release)
    echo "$RELEASE"
    ;;
  --export)
    echo "FULL_VERSION=$FULL_VERSION"
    echo "VERSION=$VERSION"
    echo "RELEASE=$RELEASE"
    ;;
  *)
    echo "Usage: $0 [--full|--version|--release|--export]" >&2
    exit 1
    ;;
esac
