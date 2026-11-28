from urllib.parse import quote, urlencode, urlsplit

PROVIDER = {
    "id": "bark",
    "name": "Bark",
    "description": "Send notifications to Bark devices.",
    "translations": {
        "en": {
            "name": "Bark",
            "description": "Send notifications to Bark devices."
        },
        "it": {
            "name": "Bark",
            "description": "Invia notifiche ai dispositivi Bark."
        }
    },
    "fields": [
        {"id": "server_url", "label": "Server URL", "type": "text", "required": True},
        {"id": "targets", "label": "Device Key(s)", "type": "text", "required": True},
        {"id": "port", "label": "Port", "type": "text"},
        {"id": "user", "label": "Username", "type": "text"},
        {"id": "password", "label": "Password", "type": "password"},
        {"id": "sound", "label": "Sound", "type": "text"},
        {"id": "level", "label": "Notification Level", "type": "select",
         "options": ["active", "timeSensitive", "passive", "critical"]},
        {"id": "volume", "label": "Volume", "type": "number"},
        {"id": "subtitle", "label": "Subtitle", "type": "text"},
        {"id": "group", "label": "Group", "type": "text"},
        {"id": "category", "label": "Category", "type": "text"},
        {"id": "click", "label": "Click URL", "type": "url"},
        {"id": "badge", "label": "Badge", "type": "number"},
        {"id": "icon", "label": "Icon URL", "type": "url"},
        {"id": "action", "label": "Action", "type": "select",
         "options": ["alert", "none"]},
        {"id": "ttl", "label": "Time To Live", "type": "number"},
    ]
}

SOUNDS = (
    "alarm.caf", "anticipate.caf", "bell.caf", "birdsong.caf",
    "bloom.caf", "calypso.caf", "chime.caf", "choo.caf",
    "descent.caf", "electronic.caf", "fanfare.caf", "glass.caf",
    "gotosleep.caf", "healthnotification.caf", "horn.caf",
    "ladder.caf", "mailsent.caf", "minuet.caf",
    "multiwayinvitation.caf", "newmail.caf", "newsflash.caf",
    "noir.caf", "paymentsuccess.caf", "shake.caf",
    "sherwoodforest.caf", "silence.caf", "spell.caf",
    "suspense.caf", "telegraph.caf", "tiptoes.caf",
    "typewriters.caf", "update.caf"
)

LEVELS = ("active", "timeSensitive", "passive", "critical")


def _boolean(value, default=False):
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in ("1", "true", "yes", "on")


def validate(settings):
    settings = settings or {}

    server_url = str(settings.get("server_url", "")).strip()
    if not server_url:
        raise ValueError("Bark server URL is required")

    if "://" not in server_url:
        server_url = "https://" + server_url

    try:
        parsed = urlsplit(server_url)
        port_from_url = parsed.port
    except ValueError:
        raise ValueError("Invalid Bark server URL")

    if (
        parsed.scheme not in ("http", "https")
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path not in ("", "/")
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("Invalid Bark server URL")

    host = parsed.hostname
    if any(ord(c) < 33 or ord(c) == 127 for c in host):
        raise ValueError("Invalid Bark server host")

    raw_port = str(settings.get("port", "")).strip()
    if raw_port:
        try:
            port = int(raw_port)
        except ValueError:
            raise ValueError("Bark port must be a number")
    else:
        port = port_from_url

    if port is not None and not 1 <= port <= 65535:
        raise ValueError("Bark port must be between 1 and 65535")

    targets = [
        item.strip()
        for item in str(settings.get("targets", "")).replace("\n", ",").split(",")
        if item.strip()
    ]
    targets = list(dict.fromkeys(targets))
    if not targets:
        raise ValueError("At least one Bark Device Key is required")
    if any(any(ord(c) < 33 or ord(c) == 127 for c in item) for item in targets):
        raise ValueError("Invalid Bark Device Key")

    user = str(settings.get("user", "")).strip()
    password = str(settings.get("password", "")).strip()
    if password and not user:
        raise ValueError("Bark username is required when using a password")

    sound = str(settings.get("sound", "")).strip()
    if sound and sound not in SOUNDS:
        raise ValueError("Invalid Bark sound")

    level = str(settings.get("level", "")).strip()
    if level and level not in LEVELS:
        raise ValueError("Invalid Bark notification level")

    def optional_int(key, minimum, maximum=None):
        value = str(settings.get(key, "")).strip()
        if not value:
            return None
        try:
            number = int(value)
        except ValueError:
            raise ValueError(f"Invalid Bark {key}")
        if number < minimum or (maximum is not None and number > maximum):
            raise ValueError(f"Invalid Bark {key}")
        return number

    volume = optional_int("volume", 0, 10)
    badge = optional_int("badge", 0)
    ttl = optional_int("ttl", 1)

    def optional_text(key):
        value = str(settings.get(key, "")).strip()
        if any(ord(c) < 32 or ord(c) == 127 for c in value):
            raise ValueError(f"Invalid Bark {key}")
        return value

    click = optional_text("click")
    icon = optional_text("icon")
    for key, value in (("click", click), ("icon", icon)):
        if value and urlsplit(value).scheme not in ("http", "https"):
            raise ValueError(f"Bark {key} must be an HTTP or HTTPS URL")

    action = str(settings.get("action", "")).strip()
    if action and action not in ("alert", "none"):
        raise ValueError("Invalid Bark action")

    return {
        "server_url": ("https" if parsed.scheme == "https" else "http")
                      + "://" + parsed.netloc,
        "host": host,
        "port": port,
        "user": user,
        "password": password,
        "targets": targets,
        "sound": sound,
        "level": level,
        "volume": volume,
        "subtitle": optional_text("subtitle"),
        "group": optional_text("group"),
        "category": optional_text("category"),
        "click": click,
        "badge": badge,
        "icon": icon,
        "action": action,
        "ttl": ttl,
        "include_image": _boolean(settings.get("include_image"), True),
        "call": _boolean(settings.get("call")),
        "archive": _boolean(settings.get("archive")),
    }


def build_url(settings):
    values = validate(settings)

    auth = ""
    if values["user"]:
        auth = quote(values["user"], safe="")
        if values["password"]:
            auth += ":" + quote(values["password"], safe="")
        auth += "@"

    host = values["host"]
    if ":" in host and not host.startswith("["):
        host = f"[{host}]"

    port = values["port"]
    if port is None:
        port = 443 if values["server_url"].startswith("https://") else 80

    default_port = 443 if values["server_url"].startswith("https://") else 80
    port_part = "" if port == default_port else f":{port}"

    targets = "/".join(quote(item, safe="") for item in values["targets"])

    params = {
        "image": "yes" if values["include_image"] else "no"
    }

    for key in (
        "sound", "level", "volume", "subtitle", "group", "category",
        "click", "badge", "icon", "action", "ttl"
    ):
        value = values.get(key)
        if value is not None and value != "":
            params[key] = str(value)

    if values["call"]:
        params["call"] = "yes"
    if values["archive"]:
        params["archive"] = "yes"

    query = urlencode(params)
    return f"barks://{auth}{host}{port_part}/{targets}?{query}"
