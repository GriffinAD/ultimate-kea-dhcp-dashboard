#!/usr/bin/env bash
set -euo pipefail

# Usage: publish-all.sh <base-dir> [GPG_KEY_ID]
BASE_DIR=${1:-"/var/www"}
KEY_ID=${2:-""}

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

APT_DIR="$BASE_DIR/apt"
RPM_DIR="$BASE_DIR/rpm"
ARCH_DIR="$BASE_DIR/arch"

echo "Publishing all repositories..."

"$SCRIPT_DIR/publish-apt.sh" "$APT_DIR" "$KEY_ID"
"$SCRIPT_DIR/publish-rpm.sh" "$RPM_DIR" "$KEY_ID"
"$SCRIPT_DIR/publish-arch.sh" "$ARCH_DIR" "$KEY_ID"

echo "All repositories published under $BASE_DIR"
