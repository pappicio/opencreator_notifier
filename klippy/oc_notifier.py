# OpenCreator Notifier - Klipper macro execution relay.
import base64
import json
import logging
import os
import queue
import threading
import urllib.request

logger = logging.getLogger(__name__)


class OCNotifier:
    def __init__(self, config):
        self.printer = config.get_printer()
        self.gcode = self.printer.lookup_object("gcode")
        plugin_root = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
        self.data_dir = os.path.join(plugin_root, "data")
        self.preferences_file = os.path.join(self.data_dir, "config.json")
        self.secrets_file = os.path.join(self.data_dir, "moonraker.secrets")
        self.backend_url = config.get(
            "backend_url", "http://127.0.0.1:8888/api/macro-event"
        )
        self.remote_mode = config.getboolean("remote_mode", False)
        self.relay_token_file = config.get(
            "relay_token_file", self.secrets_file
        )
        self._cache_mtime = None
        self._preferences = {}
        self._queue = queue.Queue(maxsize=128)
        self._wrapped = set()
        self._worker = threading.Thread(
            target=self._worker_loop, name="oc-notifier-relay", daemon=True
        )
        self._worker.start()
        self.printer.register_event_handler("klippy:ready", self._handle_ready)

    def _get_preferences(self):
        try:
            mtime = os.stat(self.preferences_file).st_mtime
            if mtime != self._cache_mtime:
                with open(self.preferences_file, "r", encoding="utf-8") as file:
                    data = json.load(file)
                prefs = data.get("macro_preferences", {})
                self._preferences = prefs if isinstance(prefs, dict) else {}
                self._cache_mtime = mtime
        except Exception:
            logger.exception("OpenCreator Notifier could not read macro preferences")
            return {}
        return self._preferences

    def _enqueue_if_enabled(self, name):
        key = str(name).upper()
        if self.remote_mode:
            try:
                self._queue.put_nowait(key)
            except queue.Full:
                logger.warning("Macro notification queue is full; skipped %s", key)
            return

        prefs = self._get_preferences()
        pref = prefs.get(key)
        if pref is None:
            # Backward compatibility while an older backend is still running.
            pref = next(
                (value for old_key, value in prefs.items()
                 if str(old_key).split("@", 1)[0].upper() == key),
                {}
            )
        if not isinstance(pref, dict):
            return
        if not pref.get("enabled") or not pref.get("notify"):
            return
        try:
            self._queue.put_nowait(key)
        except queue.Full:
            logger.warning("Macro notification queue is full; skipped %s", key)

    def _relay_token(self):
        with open(self.relay_token_file, "r", encoding="utf-8") as file:
            data = json.load(file)
        token = data.get("opencreator_notifier", {}).get("_relay_token", "")
        if not isinstance(token, str) or not token:
            raise ValueError("Relay token is missing")
        return token

    def _worker_loop(self):
        while True:
            name = self._queue.get()
            try:
                token = self._relay_token()
                auth = base64.b64encode((token + ":").encode("utf-8")).decode("ascii")
                body = json.dumps({"name": name}).encode("utf-8")
                request = urllib.request.Request(
                    self.backend_url,
                    data=body,
                    headers={
                        "Content-Type": "application/json",
                        "Authorization": "Basic " + auth
                    },
                    method="POST"
                )
                with urllib.request.urlopen(request, timeout=5) as response:
                    response.read(1024)
            except Exception:
                logger.exception("Macro notification relay failed for %s", name)
            finally:
                self._queue.task_done()

    def _handle_ready(self):
        aliases = set()
        for _object_name, macro in self.printer.lookup_objects("gcode_macro"):
            alias = getattr(macro, "alias", None)
            if alias:
                aliases.add(str(alias).upper())

        handlers = self.gcode.ready_gcode_handlers
        for alias in aliases:
            original = handlers.get(alias)
            if original is None or alias in self._wrapped:
                continue
            if getattr(original, "_oc_notifier_wrapped", False):
                self._wrapped.add(alias)
                continue

            def wrapped(*args, _original=original, _alias=alias, **kwargs):
                result = _original(*args, **kwargs)
                self._enqueue_if_enabled(_alias)
                return result

            wrapped._oc_notifier_wrapped = True
            handlers[alias] = wrapped
            self._wrapped.add(alias)

        logger.info("OpenCreator Notifier monitoring %d macro command(s)", len(self._wrapped))


def load_config(config):
    return OCNotifier(config)
