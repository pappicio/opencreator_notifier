#!/bin/sh
set -eu

PLUGIN_DIR="${OC_PLUGIN_DIR:-$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)}"
VENV="$PLUGIN_DIR/apprise-venv"

# Remove only the symlink owned by this plugin. Preserve the secrets file.
MOONRAKER_DATA_DIR="${OC_MOONRAKER_DATA_DIR:-/usr/data/opencreator/klipper}"
SECRET_FILE="$PLUGIN_DIR/data/moonraker.secrets"
SECRET_LINK="$MOONRAKER_DATA_DIR/moonraker.secrets"

if [ -L "$SECRET_LINK" ] && [ "$(readlink "$SECRET_LINK")" = "$SECRET_FILE" ]; then
    rm "$SECRET_LINK"
    echo "[OpenCreator Notifier] Moonraker secrets link removed."
fi

# Remove only the symlink owned by this plugin; preserve all secrets data.
"/usr/data/python-hf/bin/python3" - "$PLUGIN_DIR" <<'PYLINK'
import os
import sys

plugin = os.path.abspath(sys.argv[1])
secret = os.path.join(plugin, "data", "moonraker.secrets")
link = "/usr/data/opencreator/klipper/moonraker.secrets"

if os.path.islink(link) and os.path.realpath(link) == os.path.realpath(secret):
    os.unlink(link)
    print("[OpenCreator Notifier] Plugin-owned Moonraker secrets link removed.")
else:
    print("[OpenCreator Notifier] Moonraker secrets link left untouched.")
PYLINK

echo "[OpenCreator Notifier] Removing plugin Python environment..."
if [ -d "$VENV" ]; then
    rm -rf "$VENV"
fi

echo "[OpenCreator Notifier] Configuration and plugin data preserved."
