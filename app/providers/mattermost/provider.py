import re
from urllib.parse import quote, urlsplit

PROVIDER = {
    "id": "mattermost",
    "name": "Mattermost",
    "description": "Send printer notifications to Mattermost.",
    "translations": {
        "en": {
            "name": "Mattermost",
            "description": "Send printer notifications to Mattermost."
        },
        "it": {
            "name": "Mattermost",
            "description": "Invia notifiche della stampante a Mattermost."
        }
    },
    "fields": [
        {
            "id": "webhook_url",
            "label": "Incoming Webhook URL",
            "type": "password",
            "required": True
        },
        {
            "id": "channel",
            "label": "Channel (optional)",
            "type": "text",
            "required": False
        }
    ]
}


def validate(settings):
    webhook_url = str(settings.get("webhook_url", "")).strip()
    channel = str(settings.get("channel", "")).strip()

    if len(webhook_url) > 2000:
        raise ValueError("Invalid Mattermost Incoming Webhook URL")

    try:
        parsed = urlsplit(webhook_url)
        hostname = parsed.hostname
        port = parsed.port
    except ValueError:
        raise ValueError("Invalid Mattermost Incoming Webhook URL")

    path = parsed.path.rstrip("/")
    match = re.fullmatch(r"(?P<prefix>.*?)/hooks/(?P<token>[A-Za-z0-9_-]+)", path)

    if (
        parsed.scheme.lower() != "https"
        or not hostname
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
        or not match
    ):
        raise ValueError("Enter a valid HTTPS Mattermost Incoming Webhook URL")

    if port is not None and not 1 <= port <= 65535:
        raise ValueError("Invalid Mattermost server port")

    if channel.startswith("#"):
        channel = channel[1:]

    if channel and (
        len(channel) > 100
        or not re.fullmatch(r"[A-Za-z0-9_-]+", channel)
    ):
        raise ValueError("Invalid Mattermost channel name")

    return {
        "webhook_url": webhook_url,
        "channel": channel
    }


def build_url(settings):
    values = validate(settings)
    parsed = urlsplit(values["webhook_url"])
    path = parsed.path.rstrip("/")
    match = re.fullmatch(
        r"(?P<prefix>.*?)/hooks/(?P<token>[A-Za-z0-9_-]+)",
        path
    )

    hostname = parsed.hostname
    if ":" in hostname:
        hostname = f"[{hostname}]"

    if parsed.port and parsed.port != 443:
        hostname = f"{hostname}:{parsed.port}"

    prefix = match.group("prefix").strip("/")
    token = quote(match.group("token"), safe="")

    fullpath = f"/{quote(prefix, safe='/')}" if prefix else ""
    result = f"mmosts://{hostname}{fullpath}/{token}/?image=no"

    if values["channel"]:
        result += "&to=" + quote("#" + values["channel"], safe="")

    return result
