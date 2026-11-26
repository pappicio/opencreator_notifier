import re
from urllib.parse import quote

PROVIDER = {
    "id": "discord",
    "name": "Discord",
    "description": "Send printer notifications to a Discord channel using a Webhook.",
    "translations": {
        "en": {
            "name": "Discord",
            "description": "Send printer notifications to a Discord channel using a Webhook."
        },
        "it": {
            "name": "Discord",
            "description": "Invia notifiche della stampante in un canale Discord tramite Webhook."
        }
    },
    "fields": [
        {"id": "webhook_id", "label": "Webhook ID", "type": "text", "required": True},
        {"id": "webhook_token", "label": "Webhook Token", "type": "password", "required": True}
    ]
}

def validate(settings):
    webhook_id = str(settings.get("webhook_id", "")).strip()
    webhook_token = str(settings.get("webhook_token", "")).strip()

    if not re.fullmatch(r"[0-9]{17,22}", webhook_id):
        raise ValueError("Invalid Discord Webhook ID")

    if not re.fullmatch(r"[A-Za-z0-9._-]{20,200}", webhook_token):
        raise ValueError("Invalid Discord Webhook Token")

    return {
        "webhook_id": webhook_id,
        "webhook_token": webhook_token
    }

def build_url(settings):
    values = validate(settings)
    return "discord://" + quote(values["webhook_id"], safe="") + "/" + quote(values["webhook_token"], safe="")
