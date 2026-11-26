import json
import re
import secrets
from pathlib import Path


EVENT_KEYS = (
    "started",
    "paused",
    "resumed",
    "complete",
    "error",
    "cancelled",
)


def _safe(value, limit=80):
    value = str(value or "").replace("\r", " ").replace("\n", " ")
    return value[:limit].strip()


def build_secrets(config, relay_token=None):
    if not relay_token:
        relay_token = secrets.token_hex(32)

    result = {
        "opencreator_notifier": {
            "_relay_token": relay_token,
            "relay_url": (
                "json://" + relay_token
                + "@127.0.0.1:8888/api/moonraker-event"
            ),
        }
    }

    for service in config.get("services", []):
        if not isinstance(service, dict) or not service.get("enabled", True):
            continue

        service_id = str(service.get("id", ""))
        url = str(service.get("url", "")).strip()

        if not re.fullmatch(r"[a-zA-Z0-9_-]{1,64}", service_id):
            continue
        if not re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", url):
            continue

        result["opencreator_notifier"][service_id] = url

    return result


def build_moonraker_config(config, secrets_path):
    if not config.get("enable_service", True):
        return ""

    events_cfg = config.get("events", {})
    selected_events = [
        event for event in EVENT_KEYS
        if bool(events_cfg.get(event, True))
    ]

    services = [
        item for item in config.get("services", [])
        if isinstance(item, dict) and item.get("enabled", True)
    ]

    if not selected_events or not services:
        return ""

    printer_name = _safe(config.get("name", "Creator 5")) or "Creator 5"

    lines = [
        "# OpenCreator Notifier - generated file",
        "# Managed by the OpenCreator Notifier plugin.",
        "",
        "[notifier oc_relay]",
        "url: { secrets['opencreator_notifier']['relay_url'] }",
        "events: " + ", ".join(selected_events),
        f"title: {printer_name}",
        "body: { event_name }|{ event_args[1].filename if event_args|length > 1 else event_message }",
        "",
    ]

    return "\n".join(lines)


def write_generated_files(config, plugin_root):
    plugin_root = Path(plugin_root).resolve()
    data_dir = plugin_root / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    secrets_path = data_dir / "moonraker.secrets"
    config_path = data_dir / "moonraker-generated.conf"

    relay_token = None
    if secrets_path.is_file():
        try:
            old = json.loads(secrets_path.read_text(encoding="utf-8"))
            relay_token = old.get("opencreator_notifier", {}).get("_relay_token")
        except (OSError, ValueError, AttributeError):
            pass

    secrets_data = build_secrets(config, relay_token)
    moonraker_config = build_moonraker_config(config, secrets_path)

    secrets_tmp = secrets_path.with_suffix(".secrets.tmp")
    config_tmp = config_path.with_suffix(".conf.tmp")

    secrets_tmp.write_text(
        json.dumps(secrets_data, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8"
    )
    secrets_tmp.chmod(0o600)
    secrets_tmp.replace(secrets_path)

    config_tmp.write_text(moonraker_config, encoding="utf-8")
    config_tmp.chmod(0o600)
    config_tmp.replace(config_path)

    return config_path, secrets_path
