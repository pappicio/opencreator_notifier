#!/usr/bin/env python3
"""OpenCreator Notifier macro management helpers.

Existing printer macros are scanned read-only. Custom macros are stored only in
the plugin-managed notifier/notifier.cfg file. This module does not inject
notification hooks into existing printer macros.
"""
from __future__ import annotations

import os
import re
import tempfile
from pathlib import Path
from typing import Any

try:
    from .macro_scanner import scan_active_macros
except ImportError:
    from macro_scanner import scan_active_macros

_NAME_RE = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_.-]{0,63}$")
_SECTION_RE = re.compile(r"^\s*\[([^\]]+)\]\s*(?:[#;].*)?$")
_MACRO_SECTION_RE = re.compile(r"^gcode_macro\s+(.+?)$", re.I)


def _paths(config_dir: str | os.PathLike[str]) -> tuple[Path, Path]:
    root = Path(config_dir).resolve()
    custom_file = (root / "notifier" / "notifier.cfg").resolve()
    if not custom_file.is_relative_to(root):
        raise ValueError("Custom macro file must remain inside the Klipper config directory")
    return root, custom_file


def scan_existing_macros(config_dir: str | os.PathLike[str]) -> dict[str, Any]:
    """Read-only scan of macros reachable from printer.cfg."""
    root, _ = _paths(config_dir)
    return scan_active_macros(root, "printer.cfg")


def read_custom_macros(config_dir: str | os.PathLike[str]) -> list[dict[str, str]]:
    """Read custom macro sections from the dedicated plugin-managed file."""
    _, path = _paths(config_dir)
    if not path.exists():
        return []
    content = path.read_text(encoding="utf-8", errors="replace")
    lines = content.splitlines()
    result: list[dict[str, str]] = []
    current_name: str | None = None
    current_lines: list[str] = []

    def flush() -> None:
        nonlocal current_name, current_lines
        if current_name is not None:
            result.append({"name": current_name, "content": "\n".join(current_lines).rstrip()})
        current_name = None
        current_lines = []

    for line in lines:
        match = _SECTION_RE.match(line)
        if match:
            flush()
            section = match.group(1).strip()
            macro_match = _MACRO_SECTION_RE.fullmatch(section)
            if macro_match:
                name = macro_match.group(1).strip()
                if not _NAME_RE.fullmatch(name):
                    raise ValueError("Invalid macro name in notifier.cfg: " + name)
                current_name = name
                current_lines = [line]
        elif current_name is not None:
            current_lines.append(line)
    flush()
    return result


def _validate_macro_text(name: str, content: str) -> str:
    name = str(name).strip()
    if not _NAME_RE.fullmatch(name):
        raise ValueError("Macro name may contain only letters, numbers, underscore, dot and hyphen")
    if not isinstance(content, str) or not content.strip():
        raise ValueError("Macro configuration cannot be empty")
    if len(content.encode("utf-8")) > 32768:
        raise ValueError("Macro configuration is too large")
    first = content.splitlines()[0].strip() if content.splitlines() else ""
    match = _SECTION_RE.match(first)
    if not match or not _MACRO_SECTION_RE.fullmatch(match.group(1).strip()):
        raise ValueError("Content must start with [gcode_macro NAME]")
    actual_name = _MACRO_SECTION_RE.fullmatch(match.group(1).strip()).group(1).strip()
    if actual_name != name:
        raise ValueError("Macro section name does not match the selected macro")
    if any("\x00" in line for line in content.splitlines()):
        raise ValueError("NUL characters are not allowed")
    return content.rstrip() + "\n"


def save_custom_macros(config_dir: str | os.PathLike[str],
                       macros: list[dict[str, str]]) -> dict[str, Any]:
    """Atomically replace the dedicated custom-macro file.

    This is intended only for the plugin-owned notifier.cfg file. It refuses
    duplicate names and writes a managed header plus the supplied macro blocks.
    """
    if not isinstance(macros, list):
        raise ValueError("Macros must be a list")
    root, path = _paths(config_dir)
    clean: list[tuple[str, str]] = []
    seen: set[str] = set()
    for item in macros:
        if not isinstance(item, dict):
            raise ValueError("Each macro must be an object")
        name = str(item.get("name", "")).strip()
        content = _validate_macro_text(name, item.get("content", ""))
        key = name.casefold()
        if key in seen:
            raise ValueError("Duplicate custom macro name: " + name)
        seen.add(key)
        clean.append((name, content))

    path.parent.mkdir(parents=True, exist_ok=True)
    header = (
        "# OpenCreator Notifier\n"
        "# Plugin-managed custom notification macros.\n"
        "# Changes made here are managed by the OpenCreator Notifier UI.\n"
    )
    output = header + ("\n" if clean else "")
    for index, (_, content) in enumerate(clean):
        output += content
        if index != len(clean) - 1:
            output += "\n"

    old_mode = path.stat().st_mode & 0o777 if path.exists() else 0o600
    fd, temp_name = tempfile.mkstemp(prefix=".notifier-", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(output)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temp_name, old_mode)
        os.replace(temp_name, path)
    except Exception:
        try:
            os.unlink(temp_name)
        except OSError:
            pass
        raise

    return {
        "ok": True,
        "count": len(clean),
        "path": str(path),
        "bytes": len(output.encode("utf-8")),
    }


def delete_custom_macro(config_dir: str | os.PathLike[str], name: str) -> dict[str, Any]:
    """Delete one custom macro while preserving all other managed macros."""
    name = str(name).strip()
    macros = read_custom_macros(config_dir)
    kept = [item for item in macros if item["name"].casefold() != name.casefold()]
    if len(kept) == len(macros):
        raise ValueError("Custom macro not found: " + name)
    return save_custom_macros(config_dir, kept)
