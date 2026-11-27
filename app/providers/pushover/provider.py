import re
from urllib.parse import quote

PROVIDER = {
    "id": "pushover",
    "name": "Pushover",
    "description": "Send printer notifications to Pushover.",
    "translations": {
        "en": {
            "name": "Pushover",
            "description": "Send printer notifications to Pushover."
        },
        "it": {
            "name": "Pushover",
            "description": "Invia notifiche della stampante tramite Pushover."
        }
    },
    "fields": [
        {"id": "user_key", "label": "User Key", "type": "password", "required": True},
        {"id": "api_token", "label": "API Token", "type": "password", "required": True}
    ]
}


def validate(settings):
    user_key = str(settings.get("user_key", "")).strip()
    api_token = str(settings.get("api_token", "")).strip()

    if (
        not user_key or not api_token
        or len(user_key) > 256 or len(api_token) > 256
        or re.search(r"[\s\x00-\x1f\x7f]", user_key)
        or re.search(r"[\s\x00-\x1f\x7f]", api_token)
    ):
        raise ValueError("Invalid Pushover credentials")

    return {
        "user_key": user_key,
        "api_token": api_token
    }


def build_url(settings):
    values = validate(settings)
    user_key = quote(values["user_key"], safe="")
    api_token = quote(values["api_token"], safe="")
    return "pover://{}@{}".format(user_key, api_token)
