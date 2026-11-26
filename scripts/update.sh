#!/bin/sh
set -eu

PLUGIN_DIR="${OC_PLUGIN_DIR:-$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)}"
INSTALL_SCRIPT="$PLUGIN_DIR/scripts/install.sh"

[ -f "$INSTALL_SCRIPT" ] || {
    echo "[OpenCreator Notifier] install.sh not found." >&2
    exit 1
}

OC_PLUGIN_DIR="$PLUGIN_DIR" sh "$INSTALL_SCRIPT"
echo "[OpenCreator Notifier] Update preparation completed."
