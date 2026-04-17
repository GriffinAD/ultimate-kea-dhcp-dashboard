#!/usr/bin/env bash
set -euo pipefail

# Usage: publish-apt.sh /path/to/repo [GPG_KEY_ID]
REPO_DIR=${1:-"/var/www/apt"}
KEY_ID=${2:-""}
PACKAGING_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

mkdir -p "$REPO_DIR/pool"
mkdir -p "$REPO_DIR/dists/stable/main/binary-amd64"

cp "$PACKAGING_DIR"/*.deb "$REPO_DIR/pool/"

cd "$REPO_DIR"
dpkg-scanpackages pool /dev/null > dists/stable/main/binary-amd64/Packages
gzip -kf dists/stable/main/binary-amd64/Packages

cat > dists/stable/Release <<EOF
Origin: UltimateKeaDashboard
Label: UltimateKeaDashboard
Suite: stable
Codename: stable
Architectures: amd64
Components: main
Description: Ultimate Kea Dashboard APT Repository
EOF

if [[ -n "$KEY_ID" ]]; then
  gpg --armor --export "$KEY_ID" > public.key
  gpg --default-key "$KEY_ID" -abs -o dists/stable/Release.gpg dists/stable/Release
  gpg --default-key "$KEY_ID" --clearsign -o dists/stable/InRelease dists/stable/Release
fi

echo "APT repo updated at $REPO_DIR"
