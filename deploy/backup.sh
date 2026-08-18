#!/usr/bin/env bash
set -euo pipefail

vault=/srv/memex/vault
backups=/srv/memex/backups
timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
archive="${backups}/vault-${timestamp}.tar.gz"
temporary="${archive}.tmp"

test -d "${vault}"
install -d -m 0700 "${backups}"
umask 077
tar -czf "${temporary}" -C "${vault}" .
mv "${temporary}" "${archive}"
find "${backups}" -maxdepth 1 -type f -name 'vault-*.tar.gz' -mtime +30 -delete
