import logging
import apprise

logger = logging.getLogger("opencreator.notifier")


def send_to_service(service, title, message, attachment=None):
    if not service.get("enabled", True):
        return False, "Service disabled"

    url = str(service.get("url", "")).strip()
    if not url:
        return False, "Service URL not configured"

    notifier = apprise.Apprise()

    if not notifier.add(url):
        return False, "Invalid service configuration"

    try:
        result = notifier.notify(
            title=title,
            body=message,
            attach=attachment
        )
        if result:
            return True, "Notification sent"
        return False, "Notification delivery failed"
    except Exception as exc:
        logger.exception("Apprise delivery failed")
        return False, str(exc)


def send_to_all(services, title, message, attachment=None):
    results = []

    for service in services:
        if not service.get("enabled", True):
            continue

        success, detail = send_to_service(
            service, title, message, attachment
        )

        results.append({
            "id": service.get("id", ""),
            "name": service.get("name", "Unnamed"),
            "success": success,
            "message": detail
        })

    return results
