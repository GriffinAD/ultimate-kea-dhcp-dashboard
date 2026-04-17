#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PACKAGING_DIR="$ROOT_DIR/packaging"

FULL_VERSION="$($PACKAGING_DIR/version.sh --full)"
VERSION="$($PACKAGING_DIR/version.sh --version)"
RELEASE="$($PACKAGING_DIR/version.sh --release)"

CHANGELOG_FILE="$PACKAGING_DIR/debian/changelog"
PKGBUILD_FILE="$PACKAGING_DIR/arch/PKGBUILD"
SPEC_FILE="$PACKAGING_DIR/rpm/ultimate-kea-dashboard.spec"
ENTRY_FILE="$PACKAGING_DIR/changelog_entry.txt"

DATE="$(date -R)"
MAINTAINER="Auto Release <auto@local>"
ENTRY="$(cat "$ENTRY_FILE")"

# Update Debian changelog
if [[ -f "$CHANGELOG_FILE" ]]; then
  if ! grep -q "($FULL_VERSION)" "$CHANGELOG_FILE"; then
    {
      echo "ultimate-kea-dashboard ($FULL_VERSION) unstable; urgency=medium"
      echo
      echo "  * $ENTRY"
      echo
      echo " -- $MAINTAINER  $DATE"
      echo
      cat "$CHANGELOG_FILE"
    } > "$CHANGELOG_FILE.tmp"
    mv "$CHANGELOG_FILE.tmp" "$CHANGELOG_FILE"
  fi
fi

# Update PKGBUILD
if [[ -f "$PKGBUILD_FILE" ]]; then
  sed -i "s/^pkgver=.*/pkgver=$VERSION/" "$PKGBUILD_FILE"
  sed -i "s/^pkgrel=.*/pkgrel=$RELEASE/" "$PKGBUILD_FILE"
fi

# Update RPM spec
if [[ -f "$SPEC_FILE" ]]; then
  sed -i "s/@VERSION@/$VERSION/" "$SPEC_FILE"
  sed -i "s/@RELEASE@/$RELEASE/" "$SPEC_FILE"

  if ! grep -q "$FULL_VERSION" "$SPEC_FILE"; then
    sed -i "/%changelog/a * $DATE $MAINTAINER - $FULL_VERSION\n- $ENTRY" "$SPEC_FILE"
  fi
fi

echo "Metadata synced for version $FULL_VERSION"
