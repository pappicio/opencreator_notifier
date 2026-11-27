#!/bin/sh
set -eu

PLUGIN_DIR="${OC_PLUGIN_DIR:-$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)}"
VENV="/usr/data/opencreator/sunrise-venv"

# Remove only the symlink owned by this plugin. Preserve the secrets file.
MOONRAKER_DATA_DIR="${OC_MOONRAKER_DATA_DIR:-/usr/data/opencreator/klipper}"
SECRET_FILE="$PLUGIN_DIR/data/moonraker.secrets"
SECRET_LINK="$MOONRAKER_DATA_DIR/moonraker.secrets"

if [ -L "$SECRET_LINK" ]; then
    if [ "$(readlink "$SECRET_LINK")" = "$SECRET_FILE" ]; then
        rm "$SECRET_LINK"
        echo "[OpenCreator Notifier] Moonraker secrets link removed."
    else
        echo "[OpenCreator Notifier] Unrelated Moonraker secrets link left untouched."
    fi
elif [ -e "$SECRET_LINK" ]; then
    echo "[OpenCreator Notifier] Moonraker secrets file left untouched."
fi

echo "[OpenCreator Notifier] Removing plugin Python environment..."
if [ -d "$VENV" ]; then
    rm -rf "$VENV"
fi

echo "[OpenCreator Notifier] Configuration and plugin data preserved."
