#!/usr/bin/env bash
set -euo pipefail

# Usage: sync-to-host.sh <local-base-dir> <user@host:/remote/base-dir>
LOCAL_DIR=${1:-"/var/www"}
REMOTE=${2:-""}

if [[ -z "$REMOTE" ]]; then
  echo "Usage: $0 <local-base-dir> <user@host:/remote/base-dir>" >&2
  exit 1
fi

rsync -avz --delete "$LOCAL_DIR/" "$REMOTE/"

echo "Sync complete: $LOCAL_DIR -> $REMOTE"
