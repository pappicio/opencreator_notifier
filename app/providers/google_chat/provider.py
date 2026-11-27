import re
from urllib.parse import quote, parse_qs, urlsplit

PROVIDER = {
    "id": "google_chat",
    "name": "Google Chat",
    "description": "Send printer notifications to Google Chat.",
    "translations": {
        "en": {
            "name": "Google Chat",
            "description": "Send printer notifications to Google Chat."
        },
        "it": {
            "name": "Google Chat",
            "description": "Invia notifiche della stampante a Google Chat."
        }
    },
    "fields": [
        {
            "id": "webhook_url",
            "label": "Incoming Webhook URL",
            "type": "password",
            "required": True
        }
    ]
}


def validate(settings):
    url = str(settings.get("webhook_url", "")).strip()

    if len(url) > 2000:
        raise ValueError("Google Chat Webhook URL is too long")

    try:
        parsed = urlsplit(url)
        query = parse_qs(parsed.query, keep_blank_values=True)
    except ValueError:
        raise ValueError("Invalid Google Chat Webhook URL")

    if (
        parsed.scheme != "https"
        or parsed.hostname != "chat.googleapis.com"
        or parsed.username
        or parsed.password
        or parsed.port is not None
        or parsed.fragment
        or not re.fullmatch(
            r"/v1/spaces/[A-Z0-9_-]+/messages/?",
            parsed.path,
            re.I
        )
    ):
        raise ValueError("Invalid Google Chat Webhook URL")

    if set(query) - {"key", "token", "threadKey"}:
        raise ValueError("Unsupported Google Chat Webhook URL parameters")

    if (
        len(query.get("key", [])) != 1
        or len(query.get("token", [])) != 1
        or len(query.get("threadKey", [])) > 1
    ):
        raise ValueError("Google Chat Webhook URL requires one key and token")

    workspace = parsed.path.split("/")[3]
    webhook_key = query["key"][0]
    webhook_token = query["token"][0]
    thread_key = query.get("threadKey", [""])[0]

    for value, label in (
        (webhook_key, "Webhook Key"),
        (webhook_token, "Webhook Token"),
    ):
        if not value or len(value) > 512 or any(ord(c) < 33 for c in value):
            raise ValueError(f"Invalid Google Chat {label}")

    if thread_key and (
        len(thread_key) > 512
        or any(ord(c) < 33 for c in thread_key)
    ):
        raise ValueError("Invalid Google Chat Thread Key")

    return {
        "webhook_url": url,
        "workspace": workspace,
        "webhook_key": webhook_key,
        "webhook_token": webhook_token,
        "thread_key": thread_key
    }


def build_url(settings):
    values = validate(settings)

    result = "gchat://{}/{}/{}".format(
        quote(values["workspace"], safe=""),
        quote(values["webhook_key"], safe=""),
        quote(values["webhook_token"], safe="")
    )

    if values["thread_key"]:
        result += "/" + quote(values["thread_key"], safe="")

    return result
