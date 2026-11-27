#!/usr/bin/env bash
set -Eeuo pipefail

# OpenCreator Notifier - Tunneled Klipper integration
# Run this installer on the remote Klipper host (Raspberry Pi, Radxa, or Linux).

PLUGIN_DIR="/usr/data/opencreator/plugins/opencreator_notifier"
REMOTE_MODULE="${PLUGIN_DIR}/klippy/oc_notifier.py"
REMOTE_SECRETS="${PLUGIN_DIR}/data/moonraker.secrets"
REMOTE_API_CONFIG="/usr/data/opencreator/api-server.json"

say() { printf '\n%s\n' "$*"; }
die() { printf '\nERROR: %s\n' "$*" >&2; exit 1; }
need() { command -v "$1" >/dev/null 2>&1 || die "Required command not found: $1"; }

for cmd in ssh python3 find grep cp mkdir awk; do need "$cmd"; done

say "OpenCreator Notifier - Tunneled Integration"

# Look only in $HOME/printer_data/config. Never use printer.cfg.
BASE_CFG="${HOME}/printer_data/config/printer.base.cfg"

if [[ ! -f "$BASE_CFG" ]]; then
    say "Not found: ${BASE_CFG}"
    read -r -p "Enter the full path to printer.base.cfg: " BASE_CFG
    [[ -f "$BASE_CFG" ]] || die "printer.base.cfg not found: $BASE_CFG"
    [[ "$(basename "$BASE_CFG")" == "printer.base.cfg" ]] \
        || die "Only printer.base.cfg is accepted. printer.cfg will never be used."
fi

CONFIG_DIR="$(dirname "$BASE_CFG")"
MODE_MONITOR_CONFIG="${CONFIG_DIR}/klipper_mode_monitor/config.json"

# Reuse creator_ip from Mode Monitor when present. Otherwise ask and save it there.
CREATOR_IP=""
if [[ -f "$MODE_MONITOR_CONFIG" ]]; then
    CREATOR_IP="$(python3 - "$MODE_MONITOR_CONFIG" <<'PY'
import json, sys
try:
    with open(sys.argv[1], encoding="utf-8") as f:
        data = json.load(f)
    value = data.get("creator_ip", "")
    if isinstance(value, str):
        print(value.strip())
except Exception:
    pass
PY
)"
fi

if [[ -z "$CREATOR_IP" ]]; then
    read -r -p "Creator 5 IP address: " CREATOR_IP
    [[ -n "$CREATOR_IP" ]] || die "Creator 5 IP address is required"
    python3 - "$MODE_MONITOR_CONFIG" "$CREATOR_IP" <<'PY'
import ipaddress, json, os, sys
path, value = sys.argv[1:3]
try:
    ipaddress.ip_address(value)
except ValueError:
    raise SystemExit("Invalid Creator 5 IP address")
data = {}
if os.path.exists(path):
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
if not isinstance(data, dict):
    raise SystemExit("Mode Monitor config is not a JSON object; refusing to overwrite it")
data["creator_ip"] = value
os.makedirs(os.path.dirname(path), exist_ok=True)
tmp = path + ".tmp"
with open(tmp, "w", encoding="utf-8") as f:
    json.dump(data, f, indent=2)
    f.write("\n")
os.replace(tmp, path)
PY
fi

python3 - "$CREATOR_IP" <<'PY'
import ipaddress, sys
try:
    ipaddress.ip_address(sys.argv[1])
except ValueError:
    raise SystemExit("Invalid creator_ip in Mode Monitor config")
PY

say "Creator 5: ${CREATOR_IP}"
say "Klipper config: ${BASE_CFG}"

# Derive Klipper extras from the same user's home directory.
USER_HOME="$HOME"
STANDARD_EXTRAS="${USER_HOME}/klipper/klippy/extras"

if [[ -d "$STANDARD_EXTRAS" ]]; then
    KLIPPY_EXTRAS="$STANDARD_EXTRAS"
else
    say "Standard Klipper extras directory not found: ${STANDARD_EXTRAS}"
    read -r -p "Enter the full path to Klipper's klippy/extras directory: " KLIPPY_EXTRAS
    [[ -d "$KLIPPY_EXTRAS" ]] || die "Klipper extras directory not found"
    [[ "$(basename "$KLIPPY_EXTRAS")" == "extras" && "$(basename "$(dirname "$KLIPPY_EXTRAS")")" == "klippy" ]] \
        || die "The path must end in klippy/extras."
fi

say "Klipper extras: ${KLIPPY_EXTRAS}"

read -r -p "Creator 5 SSH username [root]: " SSH_USER
SSH_USER="${SSH_USER:-root}"
read -r -p "Creator 5 SSH port [22]: " SSH_PORT
SSH_PORT="${SSH_PORT:-22}"
[[ "$SSH_PORT" =~ ^[0-9]+$ ]] || die "Invalid SSH port"
SSH_TARGET="${SSH_USER}@${CREATOR_IP}"
SSH_OPTS=(-p "$SSH_PORT" -o ConnectTimeout=10 -o ServerAliveInterval=5)

say "Connecting to ${SSH_TARGET}. SSH will prompt for the password if needed."

WORK_DIR="$(mktemp -d)"
trap 'rm -rf "$WORK_DIR"' EXIT
umask 077

# One SSH session fetches the tested module, the relay token, and the authorized remote_host.
# Provider credentials are never transferred.
REMOTE_EXPORT_CMD="/usr/data/python-hf/bin/python3 -c 'import base64,json; m=open(\"$REMOTE_MODULE\",\"rb\").read(); s=json.load(open(\"$REMOTE_SECRETS\")); a=json.load(open(\"$REMOTE_API_CONFIG\")); print(json.dumps({\"module\":base64.b64encode(m).decode(\"ascii\"),\"token\":s[\"opencreator_notifier\"][\"_relay_token\"],\"remote_host\":a.get(\"remote_host\",\"\")}))'"
ssh "${SSH_OPTS[@]}" "$SSH_TARGET" "$REMOTE_EXPORT_CMD" > "$WORK_DIR/creator-export.json" \
    || die "SSH export failed. Check SSH access and OpenCreator Notifier installation."

python3 - "$WORK_DIR/creator-export.json" "$WORK_DIR/oc_notifier.py" "$WORK_DIR/relay-token" <<'PY'
import base64, json, pathlib, sys
source, module_path, token_path = sys.argv[1:4]
with open(source, encoding="utf-8") as f:
    data = json.load(f)
module = base64.b64decode(data["module"], validate=True)
token = data["token"]
if not module or not isinstance(token, str) or len(token) < 32:
    raise SystemExit("Creator export is incomplete")
pathlib.Path(module_path).write_bytes(module)
pathlib.Path(token_path).write_text(token, encoding="ascii")
pathlib.Path(source).write_text(json.dumps({"remote_host": data.get("remote_host", "")}), encoding="utf-8")
PY

REMOTE_HOST="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1])).get("remote_host",""))' "$WORK_DIR/creator-export.json")"
LOCAL_SOURCE_IP=""
if command -v ip >/dev/null 2>&1; then
    LOCAL_SOURCE_IP="$(ip route get "$CREATOR_IP" 2>/dev/null | awk '{for(i=1;i<=NF;i++) if($i=="src"){print $(i+1); exit}}' || true)"
fi
if [[ -n "$REMOTE_HOST" && -n "$LOCAL_SOURCE_IP" && "$LOCAL_SOURCE_IP" != "$REMOTE_HOST" ]]; then
    say "WARNING: Creator 5 authorizes remote_host=${REMOTE_HOST}, but this host reaches it from ${LOCAL_SOURCE_IP}."
    read -r -p "Continue anyway? [y/N]: " answer
    [[ "$answer" =~ ^[Yy]$ ]] || exit 1
fi

TOKEN="$(cat "$WORK_DIR/relay-token")"
[[ "$TOKEN" =~ ^[A-Za-z0-9_-]{32,}$ ]] || die "Creator relay token is missing or has an unexpected format"

STAMP="$(date +%Y%m%d-%H%M%S)"
mkdir -p "${CONFIG_DIR}/backup" "$KLIPPY_EXTRAS" "${CONFIG_DIR}/oc_notifier"
BACKUP_DIR="$(mktemp -d "${CONFIG_DIR}/backup/oc-notifier-tunneled-${STAMP}-XXXXXX")"

# Back up only the files this installer is about to touch.
for file in "$BASE_CFG" "$KLIPPY_EXTRAS/oc_notifier.py" \
            "$CONFIG_DIR/oc_notifier.cfg" "$CONFIG_DIR/oc_notifier/relay.json"; do
    if [[ -e "$file" ]]; then
        cp -a "$file" "$BACKUP_DIR/"
    fi
done

cp "$WORK_DIR/oc_notifier.py" "$KLIPPY_EXTRAS/oc_notifier.py"

python3 - "$CONFIG_DIR/oc_notifier/relay.json" "$TOKEN" <<'PY'
import json, os, sys
path, token = sys.argv[1:3]
tmp = path + ".tmp"
with open(tmp, "w", encoding="utf-8") as f:
    json.dump({"opencreator_notifier": {"_relay_token": token}}, f)
    f.write("\n")
os.replace(tmp, path)
PY
unset TOKEN

cat > "$CONFIG_DIR/oc_notifier.cfg" <<EOF
# OpenCreator Notifier - Tunneled integration
[oc_notifier]
backend_url: http://${CREATOR_IP}:8888/api/macro-event
remote_mode: True
relay_token_file: ${CONFIG_DIR}/oc_notifier/relay.json
EOF

if ! grep -Eq '^[[:space:]]*\[include[[:space:]]+oc_notifier\.cfg[[:space:]]*\][[:space:]]*(#.*)?$' "$BASE_CFG"; then
    printf '\n[include oc_notifier.cfg]\n' >> "$BASE_CFG"
fi

# Verify the managed configuration and module are present.
grep -Eq '^[[:space:]]*\[oc_notifier\][[:space:]]*$' "$CONFIG_DIR/oc_notifier.cfg" \
    || die "Notifier Klipper section verification failed"
grep -Eq '^[[:space:]]*remote_mode:[[:space:]]*True[[:space:]]*$' "$CONFIG_DIR/oc_notifier.cfg" \
    || die "Remote mode verification failed"
grep -Fq '[include oc_notifier.cfg]' "$BASE_CFG" \
    || die "printer.base.cfg include verification failed"
[[ -s "$KLIPPY_EXTRAS/oc_notifier.py" && -s "$CONFIG_DIR/oc_notifier/relay.json" ]] \
    || die "Installed module or relay token file is missing"

say "Installation completed."
say "Backup: ${BACKUP_DIR}"
say "Klipper config: ${BASE_CFG}"
say "Notifier module: ${KLIPPY_EXTRAS}/oc_notifier.py"
say "Notifier config: ${CONFIG_DIR}/oc_notifier.cfg"
say "Relay token stored locally; it was not displayed."
say
read -r -p "Restart Klipper now? [Y/n]: " restart_answer
if [[ -z "$restart_answer" || "$restart_answer" =~ ^[Yy]$ ]]; then
    command -v systemctl >/dev/null 2>&1 || die "systemctl not found."
    sudo systemctl daemon-reload
    sudo systemctl restart klipper
    say "Klipper restarted."
else
    say "Klipper restart skipped. The integration will not be active until Klipper is restarted."
fi
