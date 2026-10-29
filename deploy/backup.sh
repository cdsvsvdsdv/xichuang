#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."
mkdir -p backups

STAMP=$(date +%F-%H%M)
tar czf "backups/xichuang-$STAMP.tar.gz" data
find backups -name 'xichuang-*.tar.gz' -mtime +14 -delete
echo "backup: backups/xichuang-$STAMP.tar.gz"
