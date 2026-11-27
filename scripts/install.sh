#!/bin/sh
set -eu

PLUGIN_DIR="${OC_PLUGIN_DIR:-$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)}"
BASE_PYTHON="/usr/data/python-hf/bin/python3"
VENV="/usr/data/opencreator/sunrise-venv"
APPRISE_VERSION="2.3.0"
MOONRAKER_DATA_DIR="${OC_MOONRAKER_DATA_DIR:-/usr/data/opencreator/klipper}"
SECRET_FILE="$PLUGIN_DIR/data/moonraker.secrets"
SECRET_LINK="$MOONRAKER_DATA_DIR/moonraker.secrets"
CURRENT_STEP="Starting installer"

trap 'rc=$?; if [ "$rc" -ne 0 ]; then echo ""; echo "[FAILED] $CURRENT_STEP (exit code: $rc)"; echo "Installation aborted."; fi' 0

echo ""
echo "=========================================="
echo "       OpenCreator Notifier Installer"
echo "=========================================="
echo "Plugin directory: $PLUGIN_DIR"
echo ""

CURRENT_STEP="Checking system requirements"
echo "[1/7] Checking system requirements..."

if [ ! -x "$BASE_PYTHON" ]; then
    echo "ERROR: Python not found: $BASE_PYTHON" >&2
    exit 1
fi

"$BASE_PYTHON" --version
echo "Python executable: $BASE_PYTHON"
echo "[SUCCESS] System requirements checked."
echo ""

CURRENT_STEP="Preparing plugin directories"
echo "[2/7] Preparing plugin directories..."

mkdir -p "$PLUGIN_DIR/data" "$PLUGIN_DIR/backup"
echo "Data directory: $PLUGIN_DIR/data"
echo "Backup directory: $PLUGIN_DIR/backup"
echo "[SUCCESS] Plugin directories ready."
echo ""

CURRENT_STEP="Configuring Moonraker secrets"
echo "[3/7] Configuring Moonraker secrets..."

if [ -L "$SECRET_LINK" ]; then
    [ "$(readlink "$SECRET_LINK")" = "$SECRET_FILE" ] || {
        echo "ERROR: Existing secrets link points elsewhere; refusing to replace it." >&2
        exit 1
    }
    echo "Existing plugin-managed secrets link found."
elif [ -e "$SECRET_LINK" ]; then
    echo "ERROR: Moonraker secrets path already exists; refusing to overwrite it." >&2
    exit 1
else
    ln -s "$SECRET_FILE" "$SECRET_LINK"
    echo "Moonraker secrets link created."
fi

"$BASE_PYTHON" - "$PLUGIN_DIR" "$SECRET_LINK" <<'PYLINK'
import os
import sys

plugin = os.path.abspath(sys.argv[1])
link = sys.argv[2]
secret = os.path.join(plugin, "data", "moonraker.secrets")

if not os.path.isfile(secret):
    print("Secrets file not created yet; link setup deferred.")
elif os.path.islink(link):
    if os.path.realpath(link) != os.path.realpath(secret):
        raise SystemExit("Refusing to replace an unrelated secrets link.")
else:
    if os.path.lexists(link):
        raise SystemExit("Refusing to overwrite an existing Moonraker secrets file.")
    os.symlink(secret, link)

print("Moonraker secrets path verified.")
PYLINK

echo "[SUCCESS] Moonraker secrets configuration checked."
echo ""

CURRENT_STEP="Creating Python virtual environment"
echo "[4/7] Creating Python virtual environment..."

mkdir -p "$(dirname "$VENV")"

if [ -L "$VENV" ]; then
    echo "ERROR: Virtual environment path must not be a symlink: $VENV" >&2
    exit 1
fi

if [ -x "$VENV/bin/python" ] && "$VENV/bin/python" -c "import sys" >/dev/null 2>&1; then
    echo "Existing Python environment found: $VENV"
elif [ -e "$VENV" ]; then
    echo "ERROR: Invalid environment path already exists: $VENV" >&2
    echo "It was left untouched. Inspect it before retrying." >&2
    exit 1
else
    echo "Creating environment: $VENV"
    "$BASE_PYTHON" -m venv "$VENV"
fi

"$VENV/bin/python" --version
echo "[SUCCESS] Python virtual environment ready."
echo ""

CURRENT_STEP="Installing Apprise and dependencies"
echo "[5/7] Installing Apprise and dependencies..."

if "$VENV/bin/python" -c \
    "import apprise; assert apprise.__version__ == '$APPRISE_VERSION'" \
    >/dev/null 2>&1; then
    echo "Apprise $APPRISE_VERSION is already installed."
else
    echo "Preparing pip..."
    "$VENV/bin/python" -m ensurepip --upgrade

    echo ""
    echo "Installing Apprise $APPRISE_VERSION..."
    "$VENV/bin/python" -m pip install "apprise==$APPRISE_VERSION"
fi

echo "[SUCCESS] Apprise installation completed."
echo ""

CURRENT_STEP="Verifying installed packages"
echo "[6/7] Verifying installed packages..."

"$VENV/bin/python" - <<'PYVERIFY'
import apprise
import requests

print("Apprise version:", apprise.__version__)
print("Requests version:", requests.__version__)

if apprise.__version__ != "2.3.0":
    raise SystemExit("Unexpected Apprise version.")
PYVERIFY

echo "[SUCCESS] Package verification passed."
echo ""

CURRENT_STEP="Completing installation"
echo "[7/7] Completing installation..."

echo "Plugin: $PLUGIN_DIR"
echo "Virtual environment: $VENV"
echo "Apprise: $APPRISE_VERSION"
echo ""
echo "=========================================="
echo " INSTALLATION COMPLETED SUCCESSFULLY"
echo "=========================================="
echo ""

trap - 0
