#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

"$SCRIPT_DIR/sync-metadata.sh"

VERSION=$(cat "$PROJECT_ROOT/VERSION")
PACKAGE_NAME="ultimate-kea-dashboard"
BUILD_DIR="/tmp/${PACKAGE_NAME}-arch-build"
PKG_DIR="${BUILD_DIR}/pkg"
SRC_DIR="${BUILD_DIR}/src/${PACKAGE_NAME}-${VERSION}"

rm -rf "$BUILD_DIR"
mkdir -p "$PKG_DIR" "$SRC_DIR"

cd "$PROJECT_ROOT"
for dir in bin lib static etc data; do
    [ -d "$dir" ] && cp -r "$dir" "$SRC_DIR/"
done
for file in requirements.txt requirements-plugin.txt VERSION start.sh; do
    [ -f "$file" ] && cp "$file" "$SRC_DIR/" 2>/dev/null || true
done

cp "$SCRIPT_DIR/arch/PKGBUILD" "$BUILD_DIR/"
cd "$BUILD_DIR"
sed -i "s/pkgver=.*/pkgver=${VERSION}/" PKGBUILD

mkdir -p "${PKG_DIR}/opt/ukd"
mkdir -p "${PKG_DIR}/etc/ultimate-kea-dashboard"
mkdir -p "${PKG_DIR}/var/log/ultimate-kea-dashboard"
mkdir -p "${PKG_DIR}/usr/lib/systemd/system"

cp -r "$SRC_DIR"/* "${PKG_DIR}/opt/ukd/"

cp "$SRC_DIR/etc/ultimate-kea-dashboard.service" "${PKG_DIR}/usr/lib/systemd/system/"

cd "$PKG_DIR"
bsdtar -czf .MTREE --format=mtree \
    --options='!all,use-set,type,uid,gid,mode,time,size,md5,sha256,link' \
    .PKGINFO *

cd "$BUILD_DIR"
env LANG=C bsdtar -cf - -C "$PKG_DIR" .MTREE .PKGINFO * | zstd -19 > "${PACKAGE_NAME}-${VERSION}-1-any.pkg.tar.zst"

mv "${PACKAGE_NAME}-${VERSION}-1-any.pkg.tar.zst" "$SCRIPT_DIR/"

echo "Arch package built successfully"
