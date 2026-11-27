import re
from urllib.parse import urlsplit

PROVIDER = {
    "id": "msteams",
    "name": "Microsoft Teams",
    "description": "Send printer notifications to Microsoft Teams through Power Automate.",
    "translations": {
        "en": {
            "name": "Microsoft Teams",
            "description": "Send printer notifications to Microsoft Teams through Power Automate."
        },
        "it": {
            "name": "Microsoft Teams",
            "description": "Invia notifiche della stampante a Microsoft Teams tramite Power Automate."
        }
    },
    "fields": [
        {
            "id": "webhook_url",
            "label": "Webhook URL",
            "type": "password",
            "required": True
        }
    ]
}


WEBHOOK_PATTERN = re.compile(
    r"^https?://(?P<host>[A-Z0-9_.-]+\.(?:"
    r"logic\.azure\.[A-Z]{2,12}"
    r"|(?:power|apps)platform(?:\.[A-Z0-9-]{2,24}){1,3}"
    r"))"
    r"(?P<port>:[1-9][0-9]{0,5})?"
    r"(?P<power_automate>/powerautomate/automations/direct"
    r"(?:/cu/(?P<routing_id>[0-9]+))?)?"
    r"/workflows/"
    r"(?P<workflow>[A-Z0-9_-]+)"
    r"/triggers/manual/paths/invoke/?"
    r"\?.+$",
    re.IGNORECASE
)


def validate(settings):
    webhook_url = str(settings.get("webhook_url", "")).strip()

    if not webhook_url or len(webhook_url) > 2000:
        raise ValueError("Invalid Microsoft Teams webhook URL")

    try:
        parsed = urlsplit(webhook_url)
        if (
            parsed.scheme not in ("http", "https")
            or not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
            or parsed.fragment
            or not WEBHOOK_PATTERN.fullmatch(webhook_url)
        ):
            raise ValueError

        parsed.port

    except ValueError:
        raise ValueError("Invalid Microsoft Teams webhook URL")

    return {"webhook_url": webhook_url}


def build_url(settings):
    values = validate(settings)
    return values["webhook_url"]
