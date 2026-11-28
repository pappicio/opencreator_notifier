from urllib.parse import quote, urlencode

PROVIDER = {
    "id": "pushsafer",
    "name": "Pushsafer",
    "description": "Send notifications to your devices using Pushsafer.",
    "translations": {
        "en": {
            "name": "Pushsafer",
            "description": "Send notifications to your devices using Pushsafer."
        },
        "it": {
            "name": "Pushsafer",
            "description": "Invia notifiche ai tuoi dispositivi tramite Pushsafer."
        }
    },
    "fields": [
        {"id": "privatekey", "label": "Private Key", "type": "password", "required": True},
        {"id": "targets", "label": "Target Devices", "type": "text", "required": False},
        {"id": "priority", "label": "Priority", "type": "select", "required": False},
        {"id": "sound", "label": "Sound", "type": "select", "required": False},
        {"id": "vibration", "label": "Vibration", "type": "select", "required": False}
    ]
}

PRIORITIES = {"", "low", "medium", "normal", "high", "emergency"}
SOUNDS = {
    "", "silent", "ahem", "applause", "arrow", "baby", "bell",
    "bicycle", "boing", "buzzer", "camera", "carhorn",
    "cashregister", "chime", "creakydoor", "cuckooclock",
    "disconnect", "dog", "doorbell", "fanfare", "gunshot",
    "honk", "jawharp", "morse", "electric", "radiotuner",
    "sirens", "militarytrumpets", "ufo", "whahwhah", "goodye",
    "hello", "no", "okay", "ooohhhweee", "warn", "welcome",
    "yeah", "yes", "beep", "weee", "cutinout", "flickglass",
    "laser", "windchime", "echo", "zipper", "hihat", "beep2",
    "beep3", "beep4", "alarmarmed", "alarmdisarmed",
    "backupready", "dooropen", "doorclosed", "windowopen",
    "windowclosed", "lighton", "lightoff", "doorbellrang"
}
VIBRATIONS = {"", "1", "2", "3"}


def validate(settings):
    privatekey = str(settings.get("privatekey", "")).strip()
    if not privatekey:
        raise ValueError("Private Key is required")

    targets = str(settings.get("targets", "")).strip()
    priority = str(settings.get("priority", "")).strip().lower()
    sound = str(settings.get("sound", "")).strip().lower()
    vibration = str(settings.get("vibration", "")).strip()

    if priority not in PRIORITIES:
        raise ValueError("Invalid Pushsafer priority")
    if sound not in SOUNDS:
        raise ValueError("Invalid Pushsafer sound")
    if vibration not in VIBRATIONS:
        raise ValueError("Invalid Pushsafer vibration")

    return {
        "privatekey": privatekey,
        "targets": targets,
        "priority": priority,
        "sound": sound,
        "vibration": vibration
    }


def build_url(settings):
    values = validate(settings)
    url = "psafers://" + quote(values["privatekey"], safe="")

    targets = [
        item.strip()
        for item in values["targets"].replace("\n", ",").split(",")
        if item.strip()
    ]
    if targets:
        url += "/" + "/".join(quote(item, safe="") for item in targets)

    params = {}
    if values["priority"]:
        params["priority"] = values["priority"]
    if values["sound"]:
        params["sound"] = values["sound"]
    if values["vibration"]:
        params["vibration"] = values["vibration"]

    if params:
        url += "?" + urlencode(params)

    return url
