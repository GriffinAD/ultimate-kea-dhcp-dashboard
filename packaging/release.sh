#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PACKAGING_DIR="$ROOT_DIR/packaging"

FULL_VERSION="$($PACKAGING_DIR/version.sh --full)"

DO_DOCKER=false
DO_TAG=false

for arg in "$@"; do
  case $arg in
    --docker) DO_DOCKER=true ;;
    --tag) DO_TAG=true ;;
  esac
done

echo "Starting full release for $FULL_VERSION"

# Sync metadata
"$PACKAGING_DIR/sync-metadata.sh"

# Build all packages
"$PACKAGING_DIR/build-deb.sh"
"$PACKAGING_DIR/build-rpm.sh"
"$PACKAGING_DIR/build-arch.sh"

# Optional Docker
if [ "$DO_DOCKER" = true ]; then
  echo "Building Docker image..."
  docker build -t ultimate-kea-dashboard:$FULL_VERSION "$ROOT_DIR"
  docker tag ultimate-kea-dashboard:$FULL_VERSION ultimate-kea-dashboard:latest
fi

# Optional Git tag
if [ "$DO_TAG" = true ]; then
  echo "Tagging release..."
  git tag "v$FULL_VERSION"
  git push origin "v$FULL_VERSION"
fi

echo "Release complete for $FULL_VERSION"
