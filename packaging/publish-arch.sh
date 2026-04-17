#!/usr/bin/env bash
set -euo pipefail

REPO_DIR=${1:-"/var/www/arch"}
PACKAGING_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

mkdir -p "$REPO_DIR"
cp "$PACKAGING_DIR"/*.pkg.tar.zst "$REPO_DIR/"

repo-add "$REPO_DIR/ultimate-kea-dashboard.db.tar.gz" "$REPO_DIR"/*.pkg.tar.zst

echo "Arch repo updated at $REPO_DIR"
