#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="${SCRIPT_DIR}/.env"

if [[ ! -f "${ENV_FILE}" ]]; then
    echo "Missing ${ENV_FILE}; create it from .env.example" >&2
    exit 1
fi

set -a
# shellcheck disable=SC1090
source "${ENV_FILE}"
set +a

required=(
    COUCHDB_USER
    COUCHDB_PASSWORD
    COUCHDB_DATABASE
    LIVESYNC_PASSPHRASE
    MEMEX_MCP_BEARER_TOKEN
)
for name in "${required[@]}"; do
    if [[ -z "${!name:-}" ]]; then
        echo "${name} must not be empty" >&2
        exit 1
    fi
done

install -d -m 0755 /srv/memex/vault /srv/memex/livesync
install -d -m 0700 /srv/memex/livesync-config
install -d -m 0700 /srv/memex/backups
install -d -m 0750 -o 5984 -g 5984 /srv/memex/couchdb
install -d -m 0755 /srv/memex/couchdb-config

# The MCP container runs as an unprivileged user and mounts the vault read-only.
# Normalize imported Markdown while leaving non-Markdown state and credentials
# untouched. LiveSync-created files already use a readable 0644 mode.
find /srv/memex/vault -type d -exec chmod 0755 {} +
find /srv/memex/vault -type f -name '*.md' -exec chmod 0644 {} +

install -m 0644 "${SCRIPT_DIR}/couchdb.ini" /srv/memex/couchdb-config/memex.ini
install -m 0755 "${SCRIPT_DIR}/backup.sh" /usr/local/sbin/memex-vault-backup
install -m 0644 "${SCRIPT_DIR}/memex-vault-backup.service" \
    /etc/systemd/system/memex-vault-backup.service
install -m 0644 "${SCRIPT_DIR}/memex-vault-backup.timer" \
    /etc/systemd/system/memex-vault-backup.timer
systemctl daemon-reload
systemctl enable --now memex-vault-backup.timer

cd "${SCRIPT_DIR}"
docker compose up -d couchdb

wait_for_couchdb() {
    for _ in {1..60}; do
        if docker compose exec -T couchdb \
            curl --fail --silent --user "${COUCHDB_USER}:${COUCHDB_PASSWORD}" \
            http://127.0.0.1:5984/_up >/dev/null; then
            return
        fi
        sleep 2
    done
    echo "CouchDB did not become healthy" >&2
    return 1
}

wait_for_couchdb

auth=(--user "${COUCHDB_USER}:${COUCHDB_PASSWORD}")
base_url="http://127.0.0.1:5984"

setup_state="$(curl --fail --silent --show-error "${auth[@]}" \
    "${base_url}/_cluster_setup" | jq -r '.state // empty')"
if [[ "${setup_state}" != "single_node_enabled" && "${setup_state}" != "cluster_finished" ]]; then
    curl --fail --silent --show-error "${auth[@]}" \
        -H "Content-Type: application/json" \
        -X POST "${base_url}/_cluster_setup" \
        -d "{\"action\":\"enable_single_node\",\"username\":\"${COUCHDB_USER}\",\"password\":\"${COUCHDB_PASSWORD}\",\"bind_address\":\"0.0.0.0\",\"port\":5984,\"singlenode\":true}" \
        >/dev/null
fi

database_status="$(curl --silent --show-error --output /dev/null --write-out '%{http_code}' \
    "${auth[@]}" -X PUT "${base_url}/${COUCHDB_DATABASE}")"
[[ "${database_status}" == "201" || "${database_status}" == "202" \
    || "${database_status}" == "412" ]] || {
        echo "Unexpected CouchDB database creation status: ${database_status}" >&2
        exit 1
    }

install -m 0644 "${SCRIPT_DIR}/couchdb-secure.ini" \
    /srv/memex/couchdb-config/security.ini
docker compose restart couchdb
wait_for_couchdb

settings=/srv/memex/livesync-config/settings.json
if [[ ! -s "${settings}" ]]; then
    jq -n \
        --arg uri "http://couchdb:5984" \
        --arg user "${COUCHDB_USER}" \
        --arg password "${COUCHDB_PASSWORD}" \
        --arg database "${COUCHDB_DATABASE}" \
        --arg passphrase "${LIVESYNC_PASSPHRASE}" \
        '{
            couchDB_URI: $uri,
            couchDB_USER: $user,
            couchDB_PASSWORD: $password,
            couchDB_DBNAME: $database,
            liveSync: true,
            syncOnSave: true,
            syncOnStart: true,
            encrypt: true,
            passphrase: $passphrase,
            usePathObfuscation: true,
            obfuscatePassphrase: $passphrase,
            usePluginSync: false,
            isConfigured: true
        }' > "${settings}"
fi
chmod 0600 "${settings}"

docker compose up -d --build livesync mcp
docker compose ps
