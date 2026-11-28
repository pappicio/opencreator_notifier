from urllib.parse import quote, urlencode
import re

PROVIDER = {
    "id": "prowl",
    "name": "Prowl",
    "description": "Send push notifications using Prowl.",
    "translations": {
        "en": {
            "name": "Prowl",
            "description": "Send push notifications using Prowl."
        },
        "it": {
            "name": "Prowl",
            "description": "Invia notifiche push tramite Prowl."
        }
    },
    "fields": [
        {"id": "apikey", "label": "API Key", "type": "password", "required": True},
        {"id": "providerkey", "label": "Provider Key", "type": "password", "required": False},
        {"id": "priority", "label": "Priority", "type": "select", "required": False}
    ]
}

PRIORITIES = {"": "normal", "low": "low", "moderate": "moderate",
              "normal": "normal", "high": "high", "emergency": "emergency"}

def validate(settings):
    apikey = str(settings.get("apikey", "")).strip()
    providerkey = str(settings.get("providerkey", "")).strip()
    priority = str(settings.get("priority", "")).strip().lower()

    if not re.fullmatch(r"[A-Za-z0-9]{40}", apikey):
        raise ValueError("API Key must contain exactly 40 alphanumeric characters")

    if providerkey and not re.fullmatch(r"[A-Za-z0-9]{40}", providerkey):
        raise ValueError("Provider Key must contain exactly 40 alphanumeric characters")

    if priority not in PRIORITIES:
        raise ValueError("Invalid Prowl priority")

    return {
        "apikey": apikey,
        "providerkey": providerkey,
        "priority": PRIORITIES[priority]
    }

def build_url(settings):
    values = validate(settings)
    url = "prowl://" + quote(values["apikey"], safe="")
    if values["providerkey"]:
        url += "/" + quote(values["providerkey"], safe="")
    return url + "?" + urlencode({"priority": values["priority"]})
