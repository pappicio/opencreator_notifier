#!/usr/bin/env python3
import os
import base64
import json
import time
import logging
import threading
import urllib.request
import urllib.parse
import urllib.error
import re
import ctypes
import hmac
import pwd
import uuid
import ipaddress
import subprocess

from apprise_sender import send_to_all
from provider_manager import get_provider_definitions, validate_service
from moonraker_config import write_generated_files
from macro_manager import (
    scan_existing_macros, read_custom_macros,
    save_custom_macros, delete_custom_macro
)
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from logging.handlers import RotatingFileHandler

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
LOG_FILE = "/tmp/opencreator-notifier.log"
CONFIG_FILE = os.path.join(DATA, "config.json")
CONFIG_DIR = "/usr/data/opencreator/klipper/config"
MONITOR_STATE_FILE = os.path.join(DATA, "monitor-state.json")
MODE_MARKER = "/usr/data/opencreator/tunneled/tunneled.sh"
LANG_DIR = os.path.join(ROOT, "web", "languages")

MOONRAKER = os.environ.get("OC_MOONRAKER_URL", "http://127.0.0.1:7125").rstrip("/")
WEB_HOST = "0.0.0.0"
WEB_PORT = 8888

SESSION_TTL = 30 * 60
_sessions = {}
_sessions_lock = threading.RLock()

LIBCRYPT = ctypes.CDLL("libcrypt.so.1")
LIBCRYPT.crypt.argtypes = (ctypes.c_char_p, ctypes.c_char_p)
LIBCRYPT.crypt.restype = ctypes.c_char_p


def discover_allowed_networks():
    networks = [ipaddress.ip_network("127.0.0.0/8")]
    try:
        output = subprocess.check_output(
            ["ip", "-4", "-o", "addr", "show", "scope", "global"],
            stderr=subprocess.DEVNULL,
            universal_newlines=True,
            timeout=3
        )
        for line in output.splitlines():
            match = re.search(r"\binet\s+(\d+\.\d+\.\d+\.\d+/\d+)", line)
            if match:
                network = ipaddress.ip_interface(match.group(1)).network
                if network not in networks:
                    networks.append(network)
    except Exception:
        logger.exception("Could not discover local IPv4 networks")
    return networks


def verify_credentials(username, password):
    if (not username or len(username) > 64 or
            not password or len(password) > 1024):
        return None

    try:
        account = pwd.getpwnam(username)
    except KeyError:
        return None

    if account.pw_uid < 0 or account.pw_shell in (
        "/sbin/nologin", "/usr/sbin/nologin", "/bin/false"
    ):
        return None

    stored_hash = ""
    try:
        with open("/etc/shadow", "r", encoding="utf-8") as f:
            for line in f:
                fields = line.rstrip("\n").split(":")
                if fields and fields[0] == username and len(fields) > 1:
                    stored_hash = fields[1]
                    break
    except OSError:
        pass

    if not stored_hash:
        stored_hash = account.pw_passwd or ""

    if not stored_hash or stored_hash.startswith(("!", "*", "x")):
        return None

    try:
        result = LIBCRYPT.crypt(
            password.encode("utf-8"), stored_hash.encode("utf-8")
        )
        if result and hmac.compare_digest(result.decode("utf-8"), stored_hash):
            return account
    except Exception:
        logger.exception("SSH credential verification failed")
    return None


def get_session(cookie_header):
    for item in (cookie_header or "").split(";"):
        key, sep, value = item.strip().partition("=")
        if sep and key == "oc_opencreator_notifier":
            token = value
            break
    else:
        return None

    now = time.time()
    with _sessions_lock:
        session = _sessions.get(token)
        if not session:
            return None
        if now - session["last"] > SESSION_TTL:
            _sessions.pop(token, None)
            return None
        session["last"] = now
        return session["username"]

os.makedirs(DATA, exist_ok=True)

logger = logging.getLogger("telegram_notify")
logger.setLevel(logging.INFO)
handler = RotatingFileHandler(
    LOG_FILE,
    maxBytes=1024 * 1024,
    backupCount=3
)
handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
logger.addHandler(handler)

config_lock = threading.RLock()
config = {
    "services": [],
    "name": "Creator 5",
    "snapshot_url": "http://127.0.0.1:8080/?action=snapshot",
    "send_photos": True,
    "enable_service": True,
    "moonraker_relay_active": False,
    "events": {
        "printer_started": True,
        "started": True,
        "paused": True,
        "resumed": True,
        "complete": True,
        "error": True,
        "cancelled": True
    },
    "progress_percent": 0,
    "poll_interval": 3,
    "macro_preferences": {},
    "web_refresh_interval": 3,
    "language": "en"
}

state_lock = threading.Lock()
printer_state = {
    "connection": "Starting",
    "state": "unknown",
    "filename": "",
    "progress": 0,
    "message": "",
    "last_event": "None"
}


def load_config():
    global config
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            saved = json.load(f)
        with config_lock:
            config.update(saved)
    except FileNotFoundError:
        save_config()
    except Exception:
        logger.exception("Could not load configuration")


def save_config():
    with config_lock:
        tmp = CONFIG_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2)
        os.chmod(tmp, 0o600)
        os.replace(tmp, CONFIG_FILE)
        write_generated_files(config, ROOT)


def save_config_data_only():
    """Persist plugin data without regenerating Moonraker/Klipper config files."""
    with config_lock:
        tmp = CONFIG_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2)
        os.chmod(tmp, 0o600)
        os.replace(tmp, CONFIG_FILE)


def get_config():
    with config_lock:
        return dict(config)


def normalize_macro_preferences(raw):
    """Normalize macro preferences to one shared entry per command name."""
    if not isinstance(raw, dict):
        return {}

    result = {}
    items = sorted(raw.items(), key=lambda item: "@" in str(item[0]), reverse=True)

    for raw_key, value in items:
        name = str(raw_key).split("@", 1)[0].strip().upper()
        if not re.fullmatch(r"[A-Z0-9_][A-Z0-9_.-]{0,63}", name):
            continue
        if not isinstance(value, dict):
            continue
        result[name] = {
            "enabled": bool(value.get("enabled", True)),
            "notify": bool(value.get("notify", True)),
            "screenshot": bool(value.get("screenshot", False))
        }

    return result


def service_runtime_state(cfg=None):
    cfg = get_config() if cfg is None else cfg
    if not bool(cfg.get("enable_service", True)):
        return "disabled"
    try:
        return "tunneled" if (os.stat(MODE_MARKER).st_mode & 0o111) else "soc"
    except OSError:
        return "unknown"


def moonraker_query():
    url = MOONRAKER + (
        "/printer/objects/query?"
        "print_stats&display_status&virtual_sdcard&extruder&heater_bed"
    )
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=5) as response:
        payload = json.loads(response.read().decode("utf-8"))
    return payload["result"]["status"]


def moonraker_server_info():
    req = urllib.request.Request(MOONRAKER + "/server/info")
    with urllib.request.urlopen(req, timeout=5) as response:
        payload = json.loads(response.read().decode("utf-8"))
    return payload["result"]


def current_boot_id():
    try:
        with open("/proc/sys/kernel/random/boot_id", "r", encoding="utf-8") as f:
            return f.read().strip()
    except OSError:
        logger.exception("Could not read system boot ID")
        return ""


def local_ip_address():
    try:
        output = subprocess.check_output(
            ["ip", "-4", "-o", "addr", "show", "scope", "global"],
            stderr=subprocess.DEVNULL,
            universal_newlines=True,
            timeout=3
        )
        for line in output.splitlines():
            fields = line.split()
            if "inet" in fields:
                address = fields[fields.index("inet") + 1].split("/", 1)[0]
                if not address.startswith("127."):
                    return address
    except Exception:
        logger.exception("Could not detect local IPv4 address")
    return "Unavailable"


def load_monitor_boot_id():
    try:
        with open(MONITOR_STATE_FILE, "r", encoding="utf-8") as f:
            state = json.load(f)
        value = state.get("boot_id", "")
        return value if isinstance(value, str) else ""
    except FileNotFoundError:
        return ""
    except Exception:
        logger.exception("Could not read monitor state")
        return ""


def save_monitor_boot_id(boot_id):
    if not boot_id:
        return

    tmp = MONITOR_STATE_FILE + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({"boot_id": boot_id}, f)
        os.chmod(tmp, 0o600)
        os.replace(tmp, MONITOR_STATE_FILE)
    except Exception:
        logger.exception("Could not save monitor state")
        try:
            if os.path.exists(tmp):
                os.unlink(tmp)
        except OSError:
            pass




def load_language_pack(code):
    code = str(code or "en")
    if not re.fullmatch(r"[a-z]{2}(?:-[A-Z]{2})?", code):
        code = "en"

    path = os.path.join(LANG_DIR, code + ".json")
    try:
        with open(path, "r", encoding="utf-8") as f:
            pack = json.load(f)
        if not isinstance(pack, dict):
            raise ValueError("Invalid language pack")
        return pack
    except Exception:
        if code != "en":
            return load_language_pack("en")
        raise


def notification_text(key, **values):
    cfg = get_config()
    try:
        pack = load_language_pack(cfg.get("language", "en"))
        template = pack["notifications"].get(key)
        if not isinstance(template, str):
            raise KeyError(key)
        return template.format(**values)
    except Exception:
        pack = load_language_pack("en")
        return pack["notifications"][key].format(**values)


def send_notification(message, photo=False, service_ids=None):
    cfg = get_config()
    runtime_state = service_runtime_state(cfg)

    if runtime_state not in ("soc", "tunneled"):
        logger.info("Notification suppressed; service state: %s", runtime_state)
        return

    services = cfg.get("services", [])
    if service_ids is not None:
        services = [s for s in services if s.get("id") in service_ids]
    if not services:
        logger.warning("Notification skipped: no services configured")
        return

    attachment = None
    snapshot_path = None

    if photo and cfg.get("send_photos") and cfg.get("snapshot_url"):
        try:
            req = urllib.request.Request(cfg["snapshot_url"])
            with urllib.request.urlopen(req, timeout=8) as response:
                content_type = response.headers.get("Content-Type", "")
                data = response.read(2 * 1024 * 1024 + 1)

            if content_type.startswith("image/") and len(data) <= 2 * 1024 * 1024:
                snapshot_path = os.path.join(
                    DATA, "snapshot-" + uuid.uuid4().hex + ".jpg"
                )
                with open(snapshot_path, "wb") as image_file:
                    image_file.write(data)
                os.chmod(snapshot_path, 0o600)
                attachment = snapshot_path
            else:
                logger.warning("Snapshot ignored: invalid type or size")
        except Exception:
            logger.exception("Could not retrieve webcam snapshot")

    title = cfg.get("name", "Creator 5").strip() or "Creator 5"

    try:
        results = send_to_all(services, title, message, attachment)
        for result in results:
            if result["success"]:
                logger.info("Notification sent: %s", result["name"])
            else:
                logger.warning(
                    "Notification failed for %s: %s",
                    result["name"], result["message"]
                )
    finally:
        if snapshot_path:
            try:
                os.unlink(snapshot_path)
            except OSError:
                logger.warning("Could not remove temporary snapshot: %s", snapshot_path)



def set_status(**values):
    with state_lock:
        printer_state.update(values)


def send_event_notification(event_key, message, photo=False):
    cfg = get_config()

    relay_events = (
        "started", "paused", "resumed",
        "complete", "error", "cancelled"
    )
    if cfg.get("moonraker_relay_active", False) and event_key in relay_events:
        logger.info("Monitor notification skipped; handled by Moonraker relay: %s",
                    event_key)
        return False

    events = cfg.get("events", {})
    if not isinstance(events, dict) or not bool(events.get(event_key, True)):
        logger.info("Notification event disabled: %s", event_key)
        return False
    send_notification(message, photo)
    return True


def monitor():
    previous_state = None
    previous_filename = ""
    last_progress = 0

    previous_moonraker_connected = None
    previous_klippy_state = None

    boot_id = current_boot_id()
    stored_boot_id = load_monitor_boot_id()
    boot_changed = bool(stored_boot_id and boot_id and stored_boot_id != boot_id)

    if not stored_boot_id and boot_id:
        save_monitor_boot_id(boot_id)

    was_dormant = False
    mode_check_failed = False

    while True:
        cfg = get_config()
        interval = max(2, min(30, int(cfg.get("poll_interval", 3))))

        runtime_state = service_runtime_state(cfg)

        if runtime_state == "unknown":
            if not mode_check_failed:
                logger.warning(
                    "Could not detect printer mode; monitoring kept dormant"
                )
            mode_check_failed = True
        else:
            mode_check_failed = False

        if runtime_state in ("disabled", "unknown"):
            if not was_dormant:
                logger.info("Monitoring suspended; service state: %s", runtime_state)
            was_dormant = True

            previous_state = None
            previous_filename = ""
            last_progress = 0
            previous_moonraker_connected = None
            previous_klippy_state = None

            set_status(
                connection="Disabled" if runtime_state == "disabled" else "Dormant",
                state="unknown",
                filename="",
                progress=0,
                message=""
            )
            time.sleep(interval)
            continue

        if was_dormant:
            logger.info("Printer monitoring resumed; mode: %s", runtime_state)
            was_dormant = False

        try:
            server_info = moonraker_server_info()
            klippy_state = str(
                server_info.get("klippy_state", "unknown")
            ).lower()
            klippy_connected = bool(server_info.get("klippy_connected"))
            ready = klippy_connected and klippy_state == "ready"

            if ready:
                startup_event = (
                    boot_changed
                    or previous_moonraker_connected is False
                    or (
                        previous_klippy_state is not None
                        and previous_klippy_state != "ready"
                    )
                )

                if startup_event:
                    ip_address = local_ip_address()
                    send_event_notification(
                        "printer_started",
                        notification_text("printer_started", ip=ip_address)
                    )
                    set_status(last_event="Printer started")
                    logger.info(
                        "Printer ready notification triggered; IP: %s",
                        ip_address
                    )

                    if boot_changed:
                        save_monitor_boot_id(boot_id)
                        boot_changed = False

                status = moonraker_query()
                stats = status.get("print_stats", {})
                display = status.get("display_status", {})
                sdcard = status.get("virtual_sdcard", {})

                current = str(stats.get("state", "unknown")).lower()
                filename = stats.get("filename") or ""
                progress = int(max(
                    float(display.get("progress") or 0),
                    float(sdcard.get("progress") or 0)
                ) * 100)
                message = stats.get("message") or ""

                set_status(
                    connection="Connected",
                    state=current,
                    filename=filename,
                    progress=progress,
                    message=message
                )

                if previous_state is None:
                    previous_state = current
                    previous_filename = filename
                    last_progress = progress

                elif current == "printing" and (
                    previous_state != "printing" or filename != previous_filename
                ):
                    if previous_state == "paused":
                        send_event_notification(
                            "resumed",
                            notification_text("print_resumed", filename=filename),
                            True
                        )
                        set_status(last_event="Resumed")
                    else:
                        send_event_notification(
                            "started",
                            notification_text("print_started", filename=filename),
                            True
                        )
                        set_status(last_event="Print started")
                    last_progress = progress

                elif current == "paused" and previous_state != "paused":
                    send_event_notification(
                        "paused",
                        notification_text("print_paused", filename=filename),
                        True
                    )
                    set_status(last_event="Paused")

                elif current == "complete" and previous_state != "complete":
                    send_event_notification(
                        "complete",
                        notification_text("print_completed", filename=filename),
                        True
                    )
                    set_status(last_event="Completed")

                elif current == "error" and previous_state != "error":
                    send_event_notification(
                        "error",
                        notification_text(
                            "print_error",
                            filename=filename,
                            error=str(message)
                        ),
                        True
                    )
                    set_status(last_event="Error")

                elif current == "cancelled" and previous_state != "cancelled":
                    send_event_notification(
                        "cancelled",
                        notification_text("print_cancelled", filename=filename),
                        True
                    )
                    set_status(last_event="Cancelled")

                threshold = int(cfg.get("progress_percent", 0))
                if (
                    current == "printing"
                    and threshold > 0
                    and progress > 0
                    and progress >= last_progress + threshold
                ):
                    send_notification(
                        notification_text(
                            "print_progress",
                            progress=progress,
                            filename=filename
                        ),
                        True
                    )
                    last_progress = (progress // threshold) * threshold

                previous_state = current
                previous_filename = filename

            else:
                set_status(connection="Connected", state="unknown")

            previous_moonraker_connected = True
            previous_klippy_state = klippy_state

        except Exception as exc:
            set_status(connection="Disconnected")
            previous_moonraker_connected = False
            logger.warning("Moonraker polling failed: %s", exc)

        time.sleep(interval)




def authenticate_moonraker_relay(handler):
    """Authenticate local Moonraker requests using HTTP Basic."""
    try:
        if not ipaddress.ip_address(handler.client_address[0]).is_loopback:
            return False

        scheme, separator, encoded = handler.headers.get(
            "Authorization", ""
        ).partition(" ")
        if not separator or scheme.lower() != "basic":
            return False

        decoded = base64.b64decode(encoded, validate=True).decode("utf-8")
        username, separator, _password = decoded.partition(":")
        if not separator:
            return False

        path = os.path.join(DATA, "moonraker.secrets")
        with open(path, "r", encoding="utf-8") as file:
            stored = json.load(file)

        expected = stored.get("opencreator_notifier", {}).get("_relay_token", "")
        return bool(expected) and hmac.compare_digest(username, expected)
    except Exception:
        logger.warning("Moonraker relay authentication failed")
        return False


def process_moonraker_event(payload):
    if not isinstance(payload, dict):
        raise ValueError("Invalid event payload")

    raw = str(payload.get("message", ""))
    event_key, separator, filename = raw.partition("|")
    event_key = event_key.strip().lower()
    filename = filename.strip()[:256] if separator else ""

    templates = {
        "started": "print_started",
        "paused": "print_paused",
        "resumed": "print_resumed",
        "complete": "print_completed",
        "error": "print_error",
        "cancelled": "print_cancelled",
    }

    template_key = templates.get(event_key)
    if not template_key:
        raise ValueError("Unsupported Moonraker event")

    if event_key == "error":
        message = notification_text(
            template_key, filename=filename, error="Moonraker print error"
        )
    else:
        message = notification_text(template_key, filename=filename)

    cfg = get_config()
    events = cfg.get("events", {})
    if not isinstance(events, dict) or not bool(events.get(event_key, True)):
        logger.info("Moonraker event disabled: %s", event_key)
        return False

    runtime_state = service_runtime_state(cfg)
    if runtime_state not in ("soc", "tunneled"):
        logger.info("Moonraker notification suppressed; service state: %s",
                    runtime_state)
        return False

    services = [
        item for item in cfg.get("services", [])
        if isinstance(item, dict) and item.get("enabled", True)
    ]
    if not services:
        logger.warning("Moonraker notification skipped: no enabled services")
        return False

    attachment_path = None
    try:
        attachments = payload.get("attachments", [])
        if attachments and cfg.get("send_photos"):
            if not isinstance(attachments, list) or len(attachments) > 1:
                raise ValueError("Invalid attachment list")

            item = attachments[0]
            if not isinstance(item, dict):
                raise ValueError("Invalid attachment")

            mime = str(item.get("mimetype", item.get("mime", ""))).lower()
            encoded = item.get("data", item.get("base64", item.get("content", "")))
            if not mime.startswith("image/") or not isinstance(encoded, str):
                raise ValueError("Unsupported attachment type")

            import base64
            import binascii

            try:
                image_data = base64.b64decode(encoded, validate=True)
            except (ValueError, binascii.Error):
                raise ValueError("Invalid attachment encoding")

            if not image_data or len(image_data) > 2 * 1024 * 1024:
                raise ValueError("Attachment exceeds size limit")

            extensions = {
                "image/jpeg": ".jpg",
                "image/png": ".png",
                "image/gif": ".gif",
                "image/webp": ".webp",
            }
            extension = extensions.get(mime.split(";", 1)[0].strip())
            if not extension:
                raise ValueError("Unsupported image format")

            attachment_path = os.path.join(
                DATA, "moonraker-" + uuid.uuid4().hex + extension
            )
            with open(attachment_path, "xb") as image_file:
                image_file.write(image_data)
            os.chmod(attachment_path, 0o600)

        title = str(payload.get("title") or cfg.get("name", "Creator 5"))
        results = send_to_all(services, title, message, attachment_path)

        for result in results:
            if result.get("success"):
                logger.info("Moonraker notification sent: %s", result.get("name"))
            else:
                logger.warning(
                    "Moonraker notification failed for %s: %s",
                    result.get("name"), result.get("message")
                )

        return True
    finally:
        if attachment_path:
            try:
                os.unlink(attachment_path)
            except OSError:
                logger.warning("Could not remove relay attachment: %s",
                               attachment_path)


class Handler(BaseHTTPRequestHandler):
    def parse_request(self):
        if not super().parse_request():
            return False
        try:
            address = ipaddress.ip_address(
                self.client_address[0].split("%", 1)[0]
            )
            allowed = any(
                address in network for network in discover_allowed_networks()
            )
        except ValueError:
            allowed = False

        if not allowed:
            self.send_error(403, "LAN access only")
            logger.warning("Blocked non-LAN client: %s", self.client_address[0])
            return False
        return True

    def log_message(self, fmt, *args):
        logger.info("Web %s - %s", self.address_string(), fmt % args)

    def send_json(self, data, status=200, headers=None):
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        if headers:
            for key, value in headers.items():
                self.send_header(key, value)
        self.end_headers()
        self.wfile.write(body)

    def current_user(self):
        return get_session(self.headers.get("Cookie"))

    def require_auth(self):
        if not self.current_user():
            self.send_json({"error": "SSH login required"}, 401)
            return False
        return True

    def check_origin(self):
        origin = self.headers.get("Origin")
        if not origin:
            return True
        try:
            return urllib.parse.urlparse(origin).netloc.lower() == (
                self.headers.get("Host", "").lower()
            )
        except Exception:
            return False

    def read_json(self):
        length = int(self.headers.get("Content-Length", "0"))
        if length > 16384:
            raise ValueError("Request too large")
        return json.loads(self.rfile.read(length).decode("utf-8"))

    def do_GET(self):
        route = urllib.parse.urlsplit(self.path).path

        if route == "/api/session":
            username = self.current_user()
            if not username:
                return self.send_json({"error": "SSH login required"}, 401)
            return self.send_json({"ok": True, "username": username})

        if route not in ("/", "/opencreator-logo.png") and not self.require_auth():
            return

        if route == "/":
            path = os.path.join(ROOT, "web", "index.html")
            try:
                with open(path, "rb") as f:
                    body = f.read()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            except OSError:
                self.send_error(404)
            return

        if route.startswith("/api/provider/") and route.endswith("/config"):
            parts = route.strip("/").split("/")
            if len(parts) != 4 or parts[0:2] != ["api", "provider"]:
                self.send_error(404)
                return
            provider_id = parts[2]
            provider = get_provider_definitions()
            if not any(item.get("id") == provider_id for item in provider):
                self.send_error(404)
                return
            query = urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)
            service_id = query.get("service_id", [""])[0]
            service = None
            if service_id:
                service = next((item for item in get_config().get("services", [])
                                if item.get("id") == service_id and
                                item.get("provider") == provider_id), None)
                if service is None:
                    self.send_error(404)
                    return
            self.send_json({
                "provider": next(item for item in provider if item.get("id") == provider_id),
                "service": ({"id": service.get("id"), "name": service.get("name"),
                             "settings": service.get("settings", {}),
                             "enabled": service.get("enabled", True)} if service else None)
            })
            return

        if route == "/opencreator-logo.png":
            path = os.path.realpath(os.path.join(ROOT, "web", "opencreator-logo.png"))
            web_dir = os.path.realpath(os.path.join(ROOT, "web"))
            if not path.startswith(web_dir + os.sep):
                self.send_error(403)
                return
            try:
                with open(path, "rb") as f:
                    body = f.read()
                self.send_response(200)
                self.send_header("Content-Type", "image/png")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.send_header("X-Content-Type-Options", "nosniff")
                self.send_header("X-Frame-Options", "DENY")
                self.end_headers()
                self.wfile.write(body)
            except OSError:
                self.send_error(404)
            return

        if route.startswith("/providers/"):
            parts = route.strip("/").split("/")
            if len(parts) != 4 or parts[0] != "providers" or parts[2] != "web":
                self.send_error(404)
                return
            provider_id, filename = parts[1], parts[3]
            if not re.fullmatch(r"[a-z0-9_-]{1,40}", provider_id) or filename not in ("config.html", "config.css", "config.js"):
                self.send_error(404)
                return
            provider_dir = os.path.realpath(os.path.join(ROOT, "app", "providers", provider_id))
            path = os.path.realpath(os.path.join(provider_dir, "web", filename))
            if not path.startswith(provider_dir + os.sep):
                self.send_error(403)
                return
            content_types = {".html": "text/html; charset=utf-8", ".css": "text/css; charset=utf-8", ".js": "application/javascript; charset=utf-8"}
            try:
                with open(path, "rb") as f:
                    body = f.read()
                self.send_response(200)
                self.send_header("Content-Type", content_types[os.path.splitext(path)[1]])
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.send_header("X-Content-Type-Options", "nosniff")
                self.send_header("X-Frame-Options", "DENY")
                self.end_headers()
                self.wfile.write(body)
            except OSError:
                self.send_error(404)
            return

        if route == "/api/token":
            cfg = get_config()
            self.send_json({"token": cfg.get("bot_token", "")})
            return

        if route == "/api/status":
            with state_lock:
                status = dict(printer_state)
            try:
                status["mode"] = (
                    "TUNNELED"
                    if os.stat(MODE_MARKER).st_mode & 0o111
                    else "SOC"
                )
            except OSError:
                status["mode"] = "UNKNOWN"
            self.send_json(status)
            return

        if route == "/api/providers":
            self.send_json({"providers": get_provider_definitions()})
            return

        if route == "/api/config":
            cfg = get_config()
            self.send_json({
                "services": [{"id": item.get("id"), "name": item.get("name"),
                              "provider": item.get("provider"),
                              "settings": item.get("settings", {}),
                              "enabled": item.get("enabled", True)}
                             for item in cfg.get("services", [])],
                "name": cfg.get("name", "Creator 5"),
                "snapshot_url": cfg.get("snapshot_url", ""),
                "send_photos": bool(cfg.get("send_photos", True)),
                "enable_service": bool(cfg.get("enable_service", True)),
                "events": {
                    key: bool(cfg.get("events", {}).get(key, True))
                    for key in (
                        "printer_started", "started", "paused",
                        "resumed", "complete", "error", "cancelled"
                    )
                },
                "progress_percent": int(cfg.get("progress_percent", 0)),
                "poll_interval": int(cfg.get("poll_interval", 3)),
                "web_refresh_interval": max(2, min(30, int(cfg.get("web_refresh_interval", 3)))),
                "language": cfg.get("language", "en")
            })
            return

        if route == "/api/macros/existing":
            macros = scan_existing_macros(CONFIG_DIR)
            self.send_json({"macros": macros})
            return

        if route == "/api/macros/custom":
            macros = read_custom_macros(CONFIG_DIR)
            self.send_json({"macros": macros})
            return

        if route == "/api/macros/preferences":
            cfg = get_config()
            self.send_json({
                "preferences": normalize_macro_preferences(
                    cfg.get("macro_preferences", {})
                )
            })
            return

        if route == "/api/languages":
            items = []
            os.makedirs(LANG_DIR, exist_ok=True)
            for filename in sorted(os.listdir(LANG_DIR)):
                if not filename.endswith(".json"):
                    continue
                try:
                    with open(os.path.join(LANG_DIR, filename), encoding="utf-8") as f:
                        pack = json.load(f)
                    if (pack.get("version") != 2 or
                            not isinstance(pack.get("interface"), dict) or
                            not isinstance(pack.get("notifications"), dict)):
                        raise ValueError("Unsupported language pack schema")
                    items.append({
                        "code": pack["code"],
                        "name": pack["name"],
                        "native_name": pack["native_name"]
                    })
                except Exception:
                    logger.warning("Ignoring invalid language pack: %s", filename)
            self.send_json({"languages": items})
            return

        if route.startswith("/api/languages/") and route.endswith(".json"):
            code = route[len("/api/languages/"):-5]
            if not re.fullmatch(r"[a-z]{2}(?:-[A-Z]{2})?", code):
                self.send_error(400)
                return
            path = os.path.join(LANG_DIR, code + ".json")
            try:
                with open(path, "rb") as f:
                    body = f.read()
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Disposition", 'attachment; filename="' + code + '.json"')
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            except OSError:
                self.send_error(404)
            return

        self.send_error(404)

    def do_POST(self):
        route = urllib.parse.urlsplit(self.path).path

        if not self.check_origin():
            return self.send_json({"error": "Invalid request origin"}, 403)

        if route == "/api/login":
            try:
                data = self.read_json()
                username = str(data.get("username", ""))
                password = str(data.get("password", ""))
            except Exception:
                return self.send_json({"error": "Invalid request"}, 400)

            account = verify_credentials(username, password)
            if not account:
                time.sleep(0.5)
                logger.warning("Failed login from %s for user %s",
                               self.client_address[0], username[:64])
                return self.send_json(
                    {"error": "Invalid SSH username or password"}, 401
                )

            token = uuid.uuid4().hex + uuid.uuid4().hex
            with _sessions_lock:
                _sessions[token] = {
                    "username": username,
                    "last": time.time()
                }

            logger.info("Login accepted from %s as %s",
                        self.client_address[0], username)
            return self.send_json(
                {"ok": True, "username": username},
                200,
                {"Set-Cookie":
                 "oc_opencreator_notifier=%s; Path=/; HttpOnly; SameSite=Strict; Max-Age=%d"
                 % (token, SESSION_TTL)}
            )

        if route == "/api/logout":
            token = ""
            for item in (self.headers.get("Cookie") or "").split(";"):
                key, sep, value = item.strip().partition("=")
                if sep and key == "oc_opencreator_notifier":
                    token = value
                    break
            with _sessions_lock:
                _sessions.pop(token, None)
            return self.send_json(
                {"ok": True},
                200,
                {"Set-Cookie":
                 "oc_opencreator_notifier=; Path=/; HttpOnly; SameSite=Strict; Max-Age=0"}
            )

        if route == "/api/macro-event":
            if not authenticate_moonraker_relay(self):
                return self.send_json({"error": "Relay authentication failed"}, 401)
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if length <= 0 or length > 16 * 1024:
                    raise ValueError("Invalid macro event size")
                payload = json.loads(self.rfile.read(length).decode("utf-8"))
                if not isinstance(payload, dict):
                    raise ValueError("Invalid macro event")
                name = str(payload.get("name", "")).strip()
                if not re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_.-]{0,63}", name):
                    raise ValueError("Invalid macro name")

                preferences = normalize_macro_preferences(
                    get_config().get("macro_preferences", {})
                )
                pref = preferences.get(name.upper(), {})
                if pref.get("enabled") and pref.get("notify"):
                    send_notification(
                        "Macro executed: " + name,
                        photo=bool(pref.get("screenshot"))
                    )
                return self.send_json({"ok": True})
            except ValueError as exc:
                return self.send_json({"error": str(exc)}, 400)
            except Exception:
                logger.exception("Macro notification relay failed")
                return self.send_json({"error": "Macro event processing failed"}, 500)

        if route == "/api/moonraker-event":
            if not authenticate_moonraker_relay(self):
                return self.send_json({"error": "Relay authentication failed"}, 401)
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if length <= 0 or length > 3 * 1024 * 1024:
                    raise ValueError("Invalid relay request size")
                payload = json.loads(self.rfile.read(length).decode("utf-8"))
                accepted = process_moonraker_event(payload)
                return self.send_json({"ok": True, "accepted": bool(accepted)})
            except ValueError as exc:
                return self.send_json({"error": str(exc)}, 400)
            except Exception:
                logger.exception("Moonraker relay event processing failed")
                return self.send_json({"error": "Event processing failed"}, 500)

        if not self.require_auth():
            return

        try:
            if route == "/api/languages":
                pack = self.read_json()
                code = pack.get("code", "")
                if not isinstance(code, str) or not re.fullmatch(r"[a-z]{2}(?:-[A-Z]{2})?", code):
                    raise ValueError("Invalid language code")
                if not isinstance(pack.get("name"), str) or not pack["name"].strip():
                    raise ValueError("Language name is required")
                if not isinstance(pack.get("native_name"), str) or not pack["native_name"].strip():
                    raise ValueError("Native language name is required")
                if pack.get("version") != 2:
                    raise ValueError("Language pack version must be 2")

                interface = pack.get("interface")
                notifications = pack.get("notifications")

                if not isinstance(interface, dict) or not isinstance(notifications, dict):
                    raise ValueError("Interface and notifications objects are required")

                if any(not isinstance(k, str) or not isinstance(v, str)
                       for section in (interface, notifications)
                       for k, v in section.items()):
                    raise ValueError("Translation keys and values must be strings")

                with open(os.path.join(LANG_DIR, "en.json"), "r", encoding="utf-8") as f:
                    reference = json.load(f)

                if set(interface) != set(reference["interface"]):
                    raise ValueError("Interface keys do not match the English template")

                if set(notifications) != set(reference["notifications"]):
                    raise ValueError("Notification keys do not match the English template")

                for key in reference["notifications"]:
                    expected = sorted(re.findall(
                        r"\{([a-zA-Z_][a-zA-Z0-9_]*)\}",
                        reference["notifications"][key]
                    ))
                    actual = sorted(re.findall(
                        r"\{([a-zA-Z_][a-zA-Z0-9_]*)\}",
                        notifications[key]
                    ))
                    if expected != actual:
                        raise ValueError("Invalid notification placeholders: " + key)
                os.makedirs(LANG_DIR, exist_ok=True)
                target = os.path.join(LANG_DIR, code + ".json")
                temporary = target + ".tmp"
                with open(temporary, "w", encoding="utf-8") as f:
                    json.dump(pack, f, ensure_ascii=False, indent=2)
                os.chmod(temporary, 0o644)
                os.replace(temporary, target)
                self.send_json({"ok": True, "code": code})
                return

            if route.startswith("/api/provider/") and route.endswith("/config"):
                parts = route.strip("/").split("/")
                if len(parts) != 4 or parts[0:2] != ["api", "provider"]:
                    self.send_error(404)
                    return
                provider_id = parts[2]
                values = self.read_json()
                service_name = str(values.get("name", "")).strip()[:80]
                settings = values.get("settings", {})
                service_id = str(values.get("service_id", "")).strip()
                if not service_name:
                    raise ValueError("Service name is required")
                if not isinstance(settings, dict):
                    raise ValueError("Invalid provider settings")
                clean_settings, url = validate_service(provider_id, settings)
                with config_lock:
                    services = list(config.get("services", []))
                    if service_id:
                        if not re.fullmatch(r"[a-zA-Z0-9_-]{1,64}", service_id):
                            raise ValueError("Invalid service ID")
                        index = next((i for i, item in enumerate(services)
                                      if item.get("id") == service_id and
                                      item.get("provider") == provider_id), None)
                        if index is None:
                            raise ValueError("Service not found")
                        enabled = bool(values.get("enabled", services[index].get("enabled", True)))
                        services[index] = {"id": service_id, "name": service_name,
                                           "provider": provider_id, "settings": clean_settings,
                                           "url": url, "enabled": enabled}
                    else:
                        if len(services) >= 20:
                            raise ValueError("A maximum of 20 notification services is supported")
                        service_id = uuid.uuid4().hex
                        services.append({"id": service_id, "name": service_name,
                                         "provider": provider_id, "settings": clean_settings,
                                         "url": url, "enabled": bool(values.get("enabled", True))})
                    config["services"] = services
                    save_config()
                self.send_json({"ok": True, "service_id": service_id})
                return

            if route == "/api/macros/preferences":
                values = self.read_json()
                name = str(values.get("name", "")).strip()
                if not re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_.-]{0,63}", name):
                    raise ValueError("Invalid macro name")
                supplied = values.get("preferences")
                if not isinstance(supplied, dict):
                    raise ValueError("Invalid macro preferences")

                name_key = name.upper()
                clean = {
                    "enabled": bool(supplied.get("enabled", True)),
                    "notify": bool(supplied.get("notify", True)),
                    "screenshot": bool(supplied.get("screenshot", False))
                }
                with config_lock:
                    preferences = normalize_macro_preferences(
                        config.get("macro_preferences", {})
                    )
                    preferences[name_key] = clean
                    config["macro_preferences"] = preferences
                    save_config_data_only()

                self.send_json({
                    "ok": True,
                    "preferences": get_config().get("macro_preferences", {})
                })
                return

            if route == "/api/macros/custom":
                values = self.read_json()
                macros = values.get("macros")
                if not isinstance(macros, list):
                    raise ValueError("Macros must be a list")
                save_custom_macros(CONFIG_DIR, macros)
                active_keys = {
                    str(item.get("name", "")).strip().upper()
                    for item in macros if isinstance(item, dict)
                }
                existing_keys = {
                    str(item.get("name", "")).strip().upper()
                    for item in scan_existing_macros(CONFIG_DIR).get("macros", [])
                }
                with config_lock:
                    preferences = normalize_macro_preferences(
                        config.get("macro_preferences", {})
                    )
                    keep_keys = active_keys | existing_keys
                    config["macro_preferences"] = {
                        key: value for key, value in preferences.items()
                        if key in keep_keys
                    }
                    save_config_data_only()
                self.send_json({"ok": True, "macros": read_custom_macros(CONFIG_DIR)})
                return

            if route == "/api/config":
                values = self.read_json()
                services = values.get("services", get_config().get("services", []))

                if not isinstance(services, list) or len(services) > 20:
                    raise ValueError("Services must be a list containing at most 20 entries")

                clean_services = []
                seen_ids = set()

                for item in services:
                    if not isinstance(item, dict):
                        raise ValueError("Invalid service entry")

                    service_id = str(item.get("id", "")).strip()
                    service_name = str(item.get("name", "")).strip()[:80]
                    provider = str(item.get("provider", "")).strip().lower()[:40]
                    settings = item.get("settings", {})
                    if not isinstance(settings, dict):
                        raise ValueError("Invalid provider settings")

                    if not re.fullmatch(r"[a-zA-Z0-9_-]{1,64}", service_id):
                        raise ValueError("Invalid service ID")
                    if service_id in seen_ids:
                        raise ValueError("Duplicate service ID")
                    if not provider or not service_name:
                        raise ValueError("Service name and provider are required")

                    clean_settings, url = validate_service(provider, settings)

                    seen_ids.add(service_id)
                    clean_services.append({
                        "id": service_id,
                        "name": service_name,
                        "provider": provider,
                        "settings": clean_settings,
                        "url": url,
                        "enabled": bool(item.get("enabled", True))
                    })

                with config_lock:
                    config["services"] = clean_services
                    config["name"] = str(values.get("name", config["name"]))[:80]
                    config["snapshot_url"] = str(
                        values.get("snapshot_url", config["snapshot_url"])
                    )[:500]
                    config["send_photos"] = bool(
                        values.get("send_photos", config["send_photos"])
                    )
                    config["enable_service"] = bool(
                        values.get("enable_service", config.get("enable_service", True))
                    )
                    event_defaults = {
                        "printer_started": True,
                        "started": True,
                        "paused": True,
                        "resumed": True,
                        "complete": True,
                        "error": True,
                        "cancelled": True
                    }
                    event_values = values.get("events", config.get("events", event_defaults))
                    if not isinstance(event_values, dict):
                        raise ValueError("Invalid notification events")
                    config["events"] = {
                        key: bool(event_values.get(key, default))
                        for key, default in event_defaults.items()
                    }
                    config["progress_percent"] = max(
                        0, min(100, int(values.get("progress_percent", config["progress_percent"])))
                    )
                    config["poll_interval"] = max(
                        2, min(30, int(values.get("poll_interval", config["poll_interval"])))
                    )
                    config["web_refresh_interval"] = max(
                        2, min(30, int(values.get("web_refresh_interval", config.get("web_refresh_interval", 3))))
                    )
                    selected_language = str(values.get("language", config.get("language", "en")))
                    if not re.fullmatch(r"[a-z]{2}(?:-[A-Z]{2})?", selected_language):
                        raise ValueError("Invalid language code")
                    if not os.path.isfile(os.path.join(LANG_DIR, selected_language + ".json")):
                        raise ValueError("Language pack not found")
                    config["language"] = selected_language
                    save_config()

                self.send_json({"ok": True})
                return

            if route == "/api/test":
                runtime_state = service_runtime_state()
                if runtime_state not in ("soc", "tunneled"):
                    self.send_json({
                        "ok": False,
                        "error": "Service disabled" if runtime_state == "disabled"
                                 else "Notifications are unavailable in the current printer mode"
                    })
                    return
                values = self.read_json()
                service_id = str(values.get("service_id", "")).strip()
                service_ids = [service_id] if service_id else None
                if service_id and not any(
                    item.get("id") == service_id
                    for item in get_config().get("services", [])
                ):
                    raise ValueError("Unknown service")
                threading.Thread(
                    target=send_notification,
                    args=(notification_text("test_message"), False, service_ids),
                    daemon=True
                ).start()
                self.send_json({"ok": True, "message": "Test queued"})
                return

            self.send_error(404)

        except Exception as exc:
            logger.exception("Web request failed")
            self.send_json({"ok": False, "error": str(exc)}, 400)

    def do_DELETE(self):
        route = urllib.parse.urlsplit(self.path).path

        if not self.check_origin():
            return self.send_json({"error": "Invalid request origin"}, 403)
        if not self.require_auth():
            return

        prefix = "/api/macros/custom/"
        if not route.startswith(prefix):
            self.send_error(404)
            return

        name = urllib.parse.unquote(route[len(prefix):])
        if not re.fullmatch(r"[A-Za-z0-9_]{1,64}", name):
            return self.send_json({"error": "Invalid macro name"}, 400)

        try:
            deleted = delete_custom_macro(CONFIG_DIR, name)
            if deleted is False:
                return self.send_json({"error": "Custom macro not found"}, 404)
            self.send_json({"ok": True, "macros": read_custom_macros(CONFIG_DIR)})
        except ValueError as exc:
            self.send_json({"error": str(exc)}, 400)
        except Exception:
            logger.exception("Custom macro deletion failed")
            self.send_json({"error": "Custom macro deletion failed"}, 500)


def main():
    load_config()
    threading.Thread(target=monitor, daemon=True, name="moonraker-monitor").start()

    server = ThreadingHTTPServer((WEB_HOST, WEB_PORT), Handler)
    logger.info("OpenCreator Notifier started; Moonraker: %s; Web: %s:%d",
                MOONRAKER, WEB_HOST, WEB_PORT)
    print("OpenCreator Notifier listening on port %d" % WEB_PORT, flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
