import re
from urllib.parse import quote, urlsplit

PROVIDER = {
    "id": "ntfy",
    "name": "ntfy",
    "description": "Send notifications to an ntfy topic, using ntfy.sh or your own server.",
    "translations": {
        "en": {
            "name": "ntfy",
            "description": "Send notifications to an ntfy topic, using ntfy.sh or your own server."
        },
        "it": {
            "name": "ntfy",
            "description": "Invia notifiche a un topic ntfy, tramite ntfy.sh o un server personale."
        }
    },
    "fields": [
        {"id": "server_url", "label": "Server URL", "type": "text", "required": True},
        {"id": "topic", "label": "Topic", "type": "text", "required": True},
        {"id": "token", "label": "Access Token", "type": "password", "required": False}
    ]
}


def validate(settings):
    server_url = str(settings.get("server_url", "https://ntfy.sh")).strip().rstrip("/")
    topic = str(settings.get("topic", "")).strip()
    token = str(settings.get("token", "")).strip()

    try:
        parsed = urlsplit(server_url)
        if (
            parsed.scheme not in ("http", "https")
            or not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
            or parsed.path not in ("", "/")
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError
        parsed.port
    except ValueError:
        raise ValueError("Invalid ntfy server URL")

    if not re.fullmatch(r"[a-z0-9_-]{1,64}", topic, re.IGNORECASE):
        raise ValueError("Invalid ntfy topic")

    if len(token) > 4096 or any(ord(c) < 33 or ord(c) == 127 for c in token):
        raise ValueError("Invalid ntfy access token")

    return {
        "server_url": server_url,
        "topic": topic,
        "token": token
    }


def build_url(settings):
    values = validate(settings)
    parsed = urlsplit(values["server_url"])
    scheme = "ntfys" if parsed.scheme == "https" else "ntfy"
    auth = quote(values["token"], safe="") + "@" if values["token"] else ""
    return f"{scheme}://{auth}{parsed.netloc}/{quote(values['topic'], safe='')}"
