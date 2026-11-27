import re
from urllib.parse import quote, urlsplit

PROVIDER = {
    "id": "matrix",
    "name": "Matrix",
    "description": "Send printer notifications to Matrix.",
    "translations": {
        "en": {
            "name": "Matrix",
            "description": "Send printer notifications to Matrix."
        },
        "it": {
            "name": "Matrix",
            "description": "Invia notifiche della stampante a Matrix."
        }
    },
    "fields": [
        {
            "id": "homeserver_url",
            "label": "Homeserver URL",
            "type": "url",
            "required": True
        },
        {
            "id": "access_token",
            "label": "Access Token",
            "type": "password",
            "required": True
        },
        {
            "id": "target",
            "label": "Room ID, Room Alias or User ID",
            "type": "text",
            "required": True
        }
    ]
}


def validate(settings):
    server_url = str(settings.get("homeserver_url", "")).strip()
    token = str(settings.get("access_token", "")).strip()
    target = str(settings.get("target", "")).strip()

    if len(server_url) > 500:
        raise ValueError("Invalid Matrix homeserver URL")

    try:
        parsed = urlsplit(server_url)
        hostname = parsed.hostname
        port = parsed.port
    except ValueError:
        raise ValueError("Invalid Matrix homeserver URL")

    if (
        parsed.scheme.lower() != "https"
        or not hostname
        or parsed.username
        or parsed.password
        or parsed.path not in ("", "/")
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("Homeserver must be a valid HTTPS base URL")

    if port is not None and not 1 <= port <= 65535:
        raise ValueError("Invalid Matrix homeserver port")

    if not token or len(token) > 2000 or re.search(r"[\s\x00-\x1f\x7f]", token):
        raise ValueError("Invalid Matrix access token")

    if (
        len(target) > 500
        or not re.fullmatch(r"[!#@][^\s,;]+", target)
        or ":" not in target
    ):
        raise ValueError(
            "Enter a valid Matrix Room ID (!), Room Alias (#) or User ID (@)"
        )

    return {
        "homeserver_url": server_url,
        "access_token": token,
        "target": target
    }


def build_url(settings):
    values = validate(settings)
    parsed = urlsplit(values["homeserver_url"])

    hostname = parsed.hostname
    if ":" in hostname:
        hostname = f"[{hostname}]"

    if parsed.port and parsed.port != 443:
        hostname = f"{hostname}:{parsed.port}"

    token = quote(values["access_token"], safe="")
    target = quote(values["target"], safe="!:@")

    return f"matrixs://{token}@{hostname}/{target}"
