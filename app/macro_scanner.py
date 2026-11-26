#!/usr/bin/env python3
"""Read-only scanner for Klipper macros reachable from printer.cfg.

The traversal follows Klipper's depth-first include order and resolves each
include relative to the file containing that include. Orphan files and updater
copies are ignored. Physical definitions are returned separately; duplicate
command names are compared case-insensitively because Klipper registers their
G-code command aliases in uppercase.
"""
from __future__ import annotations

import glob
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

_INCLUDE_RE = re.compile(r"^\s*\[\s*include\s+(.+?)\s*\]\s*(?:[#;].*)?$", re.I)
_MACRO_RE = re.compile(r"^\s*\[\s*gcode_macro\s+([^\]]+?)\s*\]\s*(?:[#;].*)?$", re.I)
_EXCLUDED_PARTS = {".opencreator-updater", "__pycache__"}
_CUSTOM_MACRO_FILE = Path("notifier") / "notifier.cfg"


def _inside(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _is_excluded(path: Path, root: Path) -> bool:
    try:
        parts = path.relative_to(root).parts
    except ValueError:
        return True
    return (
        any(part in _EXCLUDED_PARTS for part in parts)
        or Path(*parts) == _CUSTOM_MACRO_FILE
    )


def _clean_pattern(value: str) -> str:
    # Klipper strips '#' comments before interpreting [include ...].
    return value.split("#", 1)[0].strip().strip('"').strip("'")


def _resolve_include(pattern: str, current_file: Path, config_root: Path) -> list[Path]:
    pattern = _clean_pattern(pattern)
    if not pattern:
        return []
    include_glob = str(current_file.parent / pattern)
    matches: list[Path] = []
    for item in sorted(glob.glob(include_glob)):
        path = Path(item).resolve()
        if not path.is_file() or not _inside(path, config_root):
            continue
        if _is_excluded(path, config_root):
            continue
        matches.append(path)
    return matches


def scan_active_macros(config_dir: str | Path, entry_file: str = "printer.cfg") -> dict[str, Any]:
    """Return reachable files and all distinct physical macro definitions."""
    root = Path(config_dir).resolve()
    entry = Path(entry_file)
    if not entry.is_absolute():
        entry = root / entry
    entry = entry.resolve()
    if not _inside(entry, root):
        raise ValueError("Entry configuration must be inside the Klipper config directory")
    if not entry.is_file():
        raise FileNotFoundError(str(entry))

    active_stack: set[Path] = set()
    seen_files: set[Path] = set()
    ordered_files: list[Path] = []
    definitions: dict[str, list[dict[str, Any]]] = defaultdict(list)
    seen_definitions: set[tuple[Path, int]] = set()
    warnings: list[dict[str, str]] = []

    def visit(path: Path) -> None:
        path = path.resolve()
        if not path.is_file() or not _inside(path, root) or _is_excluded(path, root):
            return
        if path in active_stack:
            warnings.append({
                "file": str(path.relative_to(root)),
                "error": "Recursive include detected",
            })
            return

        if path not in seen_files:
            seen_files.add(path)
            ordered_files.append(path)
        active_stack.add(path)
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError as exc:
            warnings.append({"file": str(path.relative_to(root)), "error": str(exc)})
            active_stack.remove(path)
            return

        try:
            for line_number, original_line in enumerate(lines, 1):
                # Match Klipper: '#' terminates a line before section parsing.
                line = original_line.split("#", 1)[0]
                stripped = line.strip()
                if not stripped or stripped.startswith(";"):
                    continue

                include_match = _INCLUDE_RE.match(line)
                if include_match:
                    pattern = include_match.group(1).strip()
                    matches = _resolve_include(pattern, path, root)
                    # Klipper treats an unmatched wildcard include as optional.
                    # Only a missing literal include is a configuration warning.
                    clean_pattern = _clean_pattern(pattern)
                    is_custom_macro_include = (
                        not Path(clean_pattern).is_absolute()
                        and Path(clean_pattern) == _CUSTOM_MACRO_FILE
                    )
                    if (not matches
                            and not glob.has_magic(clean_pattern)
                            and not is_custom_macro_include):
                        warnings.append({
                            "file": str(path.relative_to(root)),
                            "error": "Include file does not exist: %s" % _clean_pattern(pattern),
                        })
                    for included in matches:
                        visit(included)
                    continue

                macro_match = _MACRO_RE.match(line)
                if macro_match:
                    name = macro_match.group(1).strip()
                    if not name:
                        continue
                    identity = (path, line_number)
                    if identity in seen_definitions:
                        continue
                    seen_definitions.add(identity)
                    definitions[name.upper()].append({
                        "name": name,
                        "file": str(path.relative_to(root)),
                        "line": line_number,
                    })
        finally:
            active_stack.remove(path)

    visit(entry)

    macros: list[dict[str, Any]] = []
    duplicate_names: list[str] = []
    for command_name, items in definitions.items():
        duplicated = len(items) > 1
        if duplicated:
            duplicate_names.append(command_name)
        for index, item in enumerate(items, 1):
            macros.append({
                **item,
                "duplicated": duplicated,
                "definition_index": index,
                "definition_count": len(items),
            })

    macros.sort(key=lambda item: (item["name"].casefold(), item["file"].casefold(), item["line"]))
    return {
        "entry_file": str(entry.relative_to(root)),
        "files": [str(path.relative_to(root)) for path in ordered_files],
        "macros": macros,
        "warnings": warnings,
        "file_count": len(ordered_files),
        "macro_definition_count": len(macros),
        "duplicate_names": sorted(duplicate_names),
    }


if __name__ == "__main__":
    import argparse
    import json

    parser = argparse.ArgumentParser(description="Scan active Klipper macro definitions")
    parser.add_argument("config_dir", help="Klipper configuration directory")
    parser.add_argument("--entry", default="printer.cfg")
    args = parser.parse_args()
    print(json.dumps(scan_active_macros(args.config_dir, args.entry), ensure_ascii=False, indent=2))
