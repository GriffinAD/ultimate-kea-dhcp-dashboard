#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PACKAGING_DIR="$ROOT_DIR/packaging"

FULL_VERSION="$($PACKAGING_DIR/version.sh --full)"

DO_DOCKER=false
DO_TAG=false
DO_SIGN=false

for arg in "$@"; do
  case $arg in
    --docker) DO_DOCKER=true ;;
    --tag) DO_TAG=true ;;
    --sign) DO_SIGN=true ;;
  esac
done

echo "Starting full release for $FULL_VERSION"

"$PACKAGING_DIR/sync-metadata.sh"

"$PACKAGING_DIR/build-deb.sh"
"$PACKAGING_DIR/build-rpm.sh"
"$PACKAGING_DIR/build-arch.sh"

cd "$PACKAGING_DIR"

ARTIFACTS=( *.deb *.rpm *.pkg.tar.zst )

for file in "${ARTIFACTS[@]}"; do
  if [[ -f "$file" ]]; then
    sha256sum "$file" > "$file.sha256"
  fi
done

if [[ "$DO_SIGN" == true ]]; then
  for file in "${ARTIFACTS[@]}"; do
    if [[ -f "$file" ]]; then
      gpg --armor --detach-sign "$file"
    fi
  done
fi

"$PACKAGING_DIR/generate-release-notes.sh"

if [ "$DO_DOCKER" = true ]; then
  docker build -f packaging/docker/Dockerfile -t ultimate-kea-dashboard:$FULL_VERSION "$ROOT_DIR"
  docker tag ultimate-kea-dashboard:$FULL_VERSION ultimate-kea-dashboard:latest
fi

if [ "$DO_TAG" = true ]; then
  git tag "v$FULL_VERSION"
  git push origin "v$FULL_VERSION"
fi

echo "Release complete for $FULL_VERSION"
