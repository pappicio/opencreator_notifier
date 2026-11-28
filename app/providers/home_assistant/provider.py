import re
from urllib.parse import quote, urlencode, urlsplit

PROVIDER = {
    "id": "home_assistant",
    "name": "Home Assistant",
    "description": "Send notifications to Home Assistant persistent notifications or notification services.",
    "translations": {
        "en": {
            "name": "Home Assistant",
            "description": "Send notifications to Home Assistant persistent notifications or notification services."
        },
        "it": {
            "name": "Home Assistant",
            "description": "Invia notifiche a Home Assistant tramite notifiche persistenti o servizi di notifica."
        }
    },
    "fields": [
        {"id": "ha_url", "label": "Home Assistant URL", "type": "text", "required": True},
        {"id": "token", "label": "Long-Lived Access Token", "type": "password", "required": True},
        {"id": "mode", "label": "Notification Mode", "type": "select", "required": True},
        {"id": "target", "label": "Service Target", "type": "text", "required": False},
        {"id": "notification_id", "label": "Notification ID", "type": "text", "required": False}
    ]
}

TOKEN_RE = re.compile(
    r"^([0-9a-f]{8}\.[0-9a-f]{64}|[a-z0-9_-]+\.[a-z0-9_-]+\.[a-z0-9_-]+)$",
    re.I,
)
TARGET_RE = re.compile(r"^[a-z0-9_]+\.[a-z0-9_]+$", re.I)
NID_RE = re.compile(r"^[a-z0-9_-]+$", re.I)


def validate(settings):
    ha_url = str(settings.get("ha_url", "")).strip().rstrip("/")
    token = str(settings.get("token", "")).strip()
    mode = str(settings.get("mode", "persistent")).strip().lower()
    target = str(settings.get("target", "")).strip()
    notification_id = str(settings.get("notification_id", "")).strip()

    if not ha_url:
        raise ValueError("Home Assistant URL is required")
    try:
        parsed = urlsplit(ha_url)
        if parsed.scheme not in ("http", "https") or not parsed.hostname:
            raise ValueError("Invalid Home Assistant URL")
        if parsed.username or parsed.password:
            raise ValueError("Credentials must not be included in the URL")
        _ = parsed.port
    except ValueError as exc:
        raise ValueError("Invalid Home Assistant URL") from exc

    if not TOKEN_RE.fullmatch(token):
        raise ValueError("Invalid Long-Lived Access Token")

    if mode not in ("persistent", "service"):
        raise ValueError("Invalid notification mode")

    if mode == "service":
        if not TARGET_RE.fullmatch(target):
            raise ValueError("Service target must be in domain.service format")
    else:
        target = ""

    if mode == "persistent" and notification_id:
        if not NID_RE.fullmatch(notification_id):
            raise ValueError("Invalid Notification ID")
    else:
        notification_id = ""

    return {
        "ha_url": ha_url,
        "token": token,
        "mode": mode,
        "target": target,
        "notification_id": notification_id,
    }


def build_url(settings):
    values = validate(settings)
    parsed = urlsplit(values["ha_url"])
    secure = parsed.scheme == "https"
    scheme = "hassios" if secure else "hassio"

    host = parsed.hostname
    if ":" in host:
        host = "[" + host + "]"

    port = parsed.port
    default_port = 443 if secure else 8123
    if port and port != default_port:
        host += ":" + str(port)

    token = quote(values["token"], safe="")
    url = f"{scheme}://{host}/{token}"

    params = {}
    prefix = parsed.path.strip("/")
    if prefix:
        params["prefix"] = "/" + prefix + "/"

    if values["mode"] == "service":
        url += "/" + quote(values["target"], safe="")
    elif values["notification_id"]:
        params["nid"] = values["notification_id"]

    if params:
        url += "?" + urlencode(params)

    return url
