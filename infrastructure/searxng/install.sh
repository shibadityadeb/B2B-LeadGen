#!/usr/bin/env bash
# One-time local install of SearXNG from source. No Docker involved.
#
#   ./infrastructure/searxng/install.sh
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC="$HERE/../searxng-src"

if [ ! -d "$SRC" ]; then
  echo "==> Cloning SearXNG"
  git clone --depth 1 https://github.com/searxng/searxng.git "$SRC"
fi

echo "==> Creating virtualenv"
python3 -m venv "$SRC/.venv"

echo "==> Installing dependencies (a few minutes on first run)"
"$SRC/.venv/bin/pip" install --upgrade pip setuptools wheel >/dev/null
"$SRC/.venv/bin/pip" install -r "$SRC/requirements.txt"

echo
echo "SearXNG installed. Start it with: $HERE/start.sh"
