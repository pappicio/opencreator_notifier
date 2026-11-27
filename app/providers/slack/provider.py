import re

PROVIDER = {
    "id": "slack",
    "name": "Slack",
    "description": "Send printer notifications to Slack.",
    "translations": {
        "en": {
            "name": "Slack",
            "description": "Send printer notifications to Slack."
        },
        "it": {
            "name": "Slack",
            "description": "Invia notifiche della stampante a Slack."
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

    pattern = (
        r"^https://hooks\.slack\.com/services/"
        r"[A-Z0-9]+/[A-Z0-9]+/[A-Z0-9]+/?$"
    )

    if len(url) > 2000 or not re.fullmatch(pattern, url, re.I):
        raise ValueError("Invalid Slack Incoming Webhook URL")

    return {"webhook_url": url}


def build_url(settings):
    values = validate(settings)
    match = re.fullmatch(
        r"https://hooks\.slack\.com/services/"
        r"([A-Z0-9]+)/([A-Z0-9]+)/([A-Z0-9]+)/?",
        values["webhook_url"],
        re.I
    )

    if not match:
        raise ValueError("Invalid Slack Incoming Webhook URL")

    return "slack://{}/{}/{}".format(*match.groups())
