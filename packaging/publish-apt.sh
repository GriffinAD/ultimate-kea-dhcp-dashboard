#!/usr/bin/env bash
set -euo pipefail

# Usage: publish-apt.sh /path/to/repo
REPO_DIR=${1:-"/var/www/apt"}
PACKAGING_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

mkdir -p "$REPO_DIR/pool"
cp "$PACKAGING_DIR"/*.deb "$REPO_DIR/pool/"

cd "$REPO_DIR"
dpkg-scanpackages pool /dev/null | gzip -9c > dists/stable/main/binary-amd64/Packages.gz

echo "APT repo updated at $REPO_DIR"
