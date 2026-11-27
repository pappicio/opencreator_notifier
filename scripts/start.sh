#!/bin/sh
set -eu

PLUGIN_DIR="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
PYTHON="/usr/data/opencreator/sunrise-venv/bin/python"
BASE_PYTHON="/usr/data/python-hf/bin/python3"
MODE_SCRIPT="/usr/data/opencreator/tunneled/tunneled.sh"
API_CONFIG="/usr/data/opencreator/api-server.json"

if [ ! -x "$PYTHON" ]; then
    echo "[OpenCreator Notifier] Python environment missing: $PYTHON" >&2
    exit 1
fi

if [ -x "$MODE_SCRIPT" ]; then
    MODE="Tunneled"

    if [ ! -x "$BASE_PYTHON" ]; then
        echo "[OpenCreator Notifier] System Python unavailable." >&2
        exit 1
    fi

    if [ ! -f "$API_CONFIG" ]; then
        echo "[OpenCreator Notifier] API configuration not found: $API_CONFIG" >&2
        exit 1
    fi

    OC_MOONRAKER_URL=$("$BASE_PYTHON" - "$API_CONFIG" <<'PYCONFIG'
import ipaddress
import json
import sys

try:
    with open(sys.argv[1], encoding="utf-8") as f:
        config = json.load(f)

    host = str(config.get("remote_host", "")).strip()
    if not host:
        raise ValueError("remote_host is empty")

    address = ipaddress.ip_address(host)
    host = address.compressed
    if address.version == 6:
        host = f"[{host}]"

    print(f"http://{host}:7125")
except Exception as exc:
    print(f"Invalid remote_host configuration: {exc}", file=sys.stderr)
    raise SystemExit(1)
PYCONFIG
    ) || exit 1
else
    MODE="SOC"
    OC_MOONRAKER_URL="http://127.0.0.1:7125"
fi

export OC_MOONRAKER_URL

echo "[OpenCreator Notifier] Mode: $MODE"
echo "[OpenCreator Notifier] Moonraker: $OC_MOONRAKER_URL"

exec "$PYTHON" "$PLUGIN_DIR/app/telegram_notify.py"
