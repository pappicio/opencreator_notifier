from urllib.parse import quote
import re

PROVIDER = {
    "id": "telegram",
    "name": "Telegram",
    "description": "Send notifications through a Telegram bot.",
    "translations": {
        "en": {
            "name": "Telegram",
            "description": "Send notifications through a Telegram bot."
        },
        "it": {
            "name": "Telegram",
            "description": "Invia notifiche tramite un bot Telegram."
        }
    },
    "fields": [
        {
            "id": "bot_token",
            "label": "Bot Token",
            "type": "password",
            "required": True
        },
        {
            "id": "chat_id",
            "label": "Chat ID",
            "type": "text",
            "required": True
        }
    ]
}


def validate(settings):
    token = str(settings.get("bot_token", "")).strip()
    chat_id = str(settings.get("chat_id", "")).strip()

    if not re.fullmatch(r"\d+:[A-Za-z0-9_-]+", token):
        raise ValueError("Invalid Telegram bot token")

    if not chat_id or len(chat_id) > 128:
        raise ValueError("A valid Telegram Chat ID is required")

    return {
        "bot_token": token,
        "chat_id": chat_id
    }


def build_url(settings):
    values = validate(settings)
    token = values["bot_token"]
    chat_id = quote(values["chat_id"], safe="@_-")
    return "tgram://" + token + "/" + chat_id
