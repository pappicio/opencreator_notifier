import importlib.util
import logging
import re
from pathlib import Path

logger = logging.getLogger("opencreator.notifier.providers")
PROVIDERS_DIR = Path(__file__).resolve().parent / "providers"


def discover_providers():
    providers = {}
    if not PROVIDERS_DIR.is_dir():
        return providers

    for folder in sorted(PROVIDERS_DIR.iterdir()):
        if not folder.is_dir() or folder.name.startswith("_"):
            continue
        provider_id = folder.name
        if not re.fullmatch(r"[a-z0-9_-]{1,40}", provider_id):
            continue
        path = folder / "provider.py"
        if not path.is_file():
            continue
        try:
            spec = importlib.util.spec_from_file_location(
                "oc_notifier_provider_" + provider_id, path
            )
            if spec is None or spec.loader is None:
                continue
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            definition = getattr(module, "PROVIDER", None)
            if not isinstance(definition, dict) or definition.get("id") != provider_id:
                continue
            if not callable(getattr(module, "validate", None)) or not callable(getattr(module, "build_url", None)):
                continue
            if not (folder / "web" / "config.html").is_file():
                logger.warning("Provider %s has no config.html", provider_id)
                continue
            providers[provider_id] = {"module": module, "definition": definition}
        except Exception:
            logger.exception("Could not load provider: %s", provider_id)
    return providers


def get_provider_definitions():
    result = []
    for provider_id, item in discover_providers().items():
        definition = item["definition"]
        result.append({
            "id": provider_id,
            "name": str(definition.get("name", provider_id)),
            "description": str(definition.get("description", "")),
            "translations": definition.get("translations", {}),
            "config_url": "/providers/%s/web/config.html" % provider_id,
        })
    return result


def validate_service(provider_id, settings):
    provider = discover_providers().get(provider_id)
    if provider is None:
        raise ValueError("Unknown notification provider: " + provider_id)
    clean_settings = provider["module"].validate(settings)
    url = provider["module"].build_url(clean_settings)
    if not isinstance(url, str) or not url or len(url) > 2000:
        raise ValueError("Provider generated an invalid Apprise URL")
    return clean_settings, url
