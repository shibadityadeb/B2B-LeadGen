#!/usr/bin/env bash
# Start the local SearXNG search instance (no Docker, no API key).
#
#   ./infrastructure/searxng/start.sh
#
# Run ./infrastructure/searxng/install.sh once beforehand.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC="$HERE/../searxng-src"

if [ ! -d "$SRC/.venv" ]; then
  echo "SearXNG is not installed yet. Run: $HERE/install.sh" >&2
  exit 1
fi

# Read only the SearXNG settings out of the project .env. The file is not
# sourced, because values such as CRAWL_USER_AGENT are not shell-safe.
ENV_FILE="$HERE/../../.env"
read_env() {
  [ -f "$ENV_FILE" ] || return 0
  sed -n "s/^$1=//p" "$ENV_FILE" | tail -n 1
}

export SEARXNG_SETTINGS_PATH="$HERE/settings.yml"
export SEARXNG_SECRET="${SEARXNG_SECRET:-$(read_env SEARXNG_SECRET)}"
export SEARXNG_SECRET="${SEARXNG_SECRET:-local-development-secret}"
export SEARXNG_PORT="${SEARXNG_PORT:-$(read_env SEARXNG_PORT)}"
export SEARXNG_PORT="${SEARXNG_PORT:-8888}"
export SEARXNG_BIND_ADDRESS="${SEARXNG_BIND_ADDRESS:-127.0.0.1}"

echo "SearXNG starting on http://$SEARXNG_BIND_ADDRESS:$SEARXNG_PORT"
cd "$SRC"
exec .venv/bin/python -m searx.webapp
