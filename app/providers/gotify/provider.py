from urllib.parse import quote, urlsplit

PROVIDER = {
    "id": "gotify",
    "name": "Gotify",
    "description": "Send printer notifications to your Gotify server.",
    "translations": {
        "en": {
            "name": "Gotify",
            "description": "Send printer notifications to your Gotify server."
        },
        "it": {
            "name": "Gotify",
            "description": "Invia notifiche della stampante al tuo server Gotify."
        }
    },
    "fields": [
        {"id": "server_url", "label": "Server URL", "type": "text", "required": True},
        {"id": "token", "label": "Application Token", "type": "password", "required": True}
    ]
}


def validate(settings):
    server_url = str(settings.get("server_url", "")).strip().rstrip("/")
    token = str(settings.get("token", "")).strip()

    try:
        parsed = urlsplit(server_url)
        if (
            parsed.scheme not in ("http", "https")
            or not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError
        parsed.port
    except ValueError:
        raise ValueError("Invalid Gotify server URL")

    if not token or len(token) > 4096 or any(ord(c) < 33 or ord(c) == 127 for c in token):
        raise ValueError("Invalid Gotify application token")

    path = "/" + "/".join(
        part for part in parsed.path.split("/") if part
    ) if parsed.path.strip("/") else ""

    return {
        "server_url": parsed.scheme + "://" + parsed.netloc + path,
        "token": token
    }


def build_url(settings):
    values = validate(settings)
    parsed = urlsplit(values["server_url"])
    scheme = "gotifys" if parsed.scheme == "https" else "gotify"
    path = "".join(
        "/" + quote(part, safe="-._~")
        for part in parsed.path.split("/") if part
    )
    return f"{scheme}://{parsed.netloc}{path}/{quote(values['token'], safe='')}/"
