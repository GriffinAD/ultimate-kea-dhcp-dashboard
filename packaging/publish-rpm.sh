#!/usr/bin/env bash
set -euo pipefail

REPO_DIR=${1:-"/var/www/rpm"}
PACKAGING_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

mkdir -p "$REPO_DIR"
cp "$PACKAGING_DIR"/*.rpm "$REPO_DIR/"

createrepo "$REPO_DIR"

echo "RPM repo updated at $REPO_DIR"
