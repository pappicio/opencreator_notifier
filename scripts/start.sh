#!/bin/sh
set -eu

PLUGIN_DIR="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
PYTHON="$PLUGIN_DIR/apprise-venv/bin/python"

[ -x "$PYTHON" ] || {
    echo "[OpenCreator Notifier] Python environment missing. Run install.sh." >&2
    exit 1
}

exec "$PYTHON" "$PLUGIN_DIR/app/telegram_notify.py"
