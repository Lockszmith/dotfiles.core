#!/usr/bin/env python3
"""Generic XDG .desktop deduplication for home-manager activations."""

from __future__ import annotations

import os
import re
import sys
from collections import defaultdict
from pathlib import Path

LOCAL_APP = Path.home() / ".local/share/applications"
NIX_APP = Path.home() / ".nix-profile/share/applications"
SYSTEM_DIRS = (
    Path("/usr/share/applications"),
    Path("/usr/local/share/applications"),
)

# Sync/dedup skips entries owned by dedicated activations.
SKIP_BASENAMES = frozenset(
    {
        "chromium-browser.desktop",
        "chromium.desktop",
        "Zoom.desktop",
    }
)

FIELD_CODE_RE = re.compile(r"%[fFuUiIcCk%]")


def normalize_exec(line: str) -> str:
    if not line:
        return ""
    stripped = FIELD_CODE_RE.sub("", line)
    return " ".join(stripped.split()).lower()


def parse_desktop(path: Path) -> tuple[dict[str, str], list[tuple[str, dict[str, str]]]]:
    main: dict[str, str] = {}
    actions: list[tuple[str, dict[str, str]]] = []
    section = "Desktop Entry"
    current_action: dict[str, str] | None = None
    current_action_name = ""

    with path.open(encoding="utf-8", errors="replace") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if line.startswith("[") and line.endswith("]"):
                if section.startswith("Desktop Action ") and current_action is not None:
                    actions.append((current_action_name, current_action))
                section = line[1:-1]
                if section.startswith("Desktop Action "):
                    current_action_name = section.removeprefix("Desktop Action ").strip()
                    current_action = {}
                else:
                    current_action = None
                    current_action_name = ""
                continue
            if "=" not in line:
                continue
            key, value = line.split("=", 1)
            if section == "Desktop Entry":
                main[key] = value
            elif section.startswith("Desktop Action ") and current_action is not None:
                current_action[key] = value

    if section.startswith("Desktop Action ") and current_action is not None:
        actions.append((current_action_name, current_action))

    return main, actions


def is_hidden(main: dict[str, str]) -> bool:
    return main.get("NoDisplay", "").lower() == "true" or main.get("Hidden", "").lower() == "true"


def app_key(main: dict[str, str]) -> tuple[str, str] | None:
    wmclass = main.get("StartupWMClass", "").strip()
    if wmclass:
        return ("wmclass", wmclass.lower())
    exec_norm = normalize_exec(main.get("Exec", ""))
    if exec_norm:
        return ("exec", exec_norm)
    name = main.get("Name", "").strip()
    if name:
        return ("name", name.lower())
    return None


def has_meaningful_exec_override(local_main: dict[str, str], other_main: dict[str, str]) -> bool:
    local_exec = local_main.get("Exec", "")
    if ".nix-profile" not in local_exec and "/nix/store/" not in local_exec:
        return False
    return normalize_exec(local_exec) != normalize_exec(other_main.get("Exec", ""))


def search_dirs() -> list[tuple[Path, int]]:
    dirs: list[tuple[Path, int]] = [(LOCAL_APP, 0)]
    for system_dir in SYSTEM_DIRS:
        dirs.append((system_dir, 1))
    dirs.append((NIX_APP, 2))
    return dirs


def collect_visible_entries() -> list[tuple[Path, dict[str, str], int, tuple[str, str]]]:
    entries: list[tuple[Path, dict[str, str], int, tuple[str, str]]] = []
    for dir_path, priority in search_dirs():
        if not dir_path.is_dir():
            continue
        for desktop in sorted(dir_path.glob("*.desktop")):
            if desktop.name in SKIP_BASENAMES:
                continue
            main, _ = parse_desktop(desktop)
            if is_hidden(main):
                continue
            key = app_key(main)
            if key is None:
                continue
            entries.append((desktop, main, priority, key))
    return entries


def equivalent_exists_outside_nix(main: dict[str, str]) -> bool:
    key = app_key(main)
    if key is None:
        return False
    for dir_path, _priority in search_dirs():
        if dir_path == NIX_APP or not dir_path.is_dir():
            continue
        for desktop in dir_path.glob("*.desktop"):
            if desktop.name in SKIP_BASENAMES:
                continue
            other_main, _ = parse_desktop(desktop)
            if is_hidden(other_main):
                continue
            if app_key(other_main) == key:
                return True
    return False


def remove_inferior_duplicate(path: Path, canonical_main: dict[str, str]) -> None:
    main, _ = parse_desktop(path)
    if path.parent == LOCAL_APP and has_meaningful_exec_override(main, canonical_main):
        return
    try:
        path.unlink(missing_ok=True)
    except OSError:
        if path.parent != NIX_APP:
            raise
        write_hidden_override(path.name, main)


def write_hidden_override(basename: str, main: dict[str, str]) -> None:
    LOCAL_APP.mkdir(parents=True, exist_ok=True)
    dst = LOCAL_APP / basename
    if dst.exists():
        existing_main, _ = parse_desktop(dst)
        if not is_hidden(existing_main):
            return

    lines = [
        "[Desktop Entry]",
        "Type=Application",
        f"Name={main.get('Name', basename.removesuffix('.desktop'))}",
        "NoDisplay=true",
        "Hidden=true",
    ]
    if wmclass := main.get("StartupWMClass"):
        lines.append(f"StartupWMClass={wmclass}")
    dst.write_text("\n".join(lines) + "\n", encoding="utf-8")
    dst.chmod(0o644)


def is_redundant_local_sync(
    path: Path, main: dict[str, str], group: list[tuple[Path, dict[str, str], int]]
) -> bool:
    if path.parent != LOCAL_APP:
        return False
    for other_path, other_main, _priority in group:
        if other_path.parent not in SYSTEM_DIRS:
            continue
        if normalize_exec(main.get("Exec", "")) == normalize_exec(other_main.get("Exec", "")):
            if not has_meaningful_exec_override(main, other_main):
                return True
    return False


def pick_canonical(group: list[tuple[Path, dict[str, str], int]]) -> tuple[Path, dict[str, str], int]:
    system_main = next((main for path, main, _ in group if path.parent in SYSTEM_DIRS), {})

    def rank(item: tuple[Path, dict[str, str], int]) -> tuple[int, str]:
        path, main, _priority = item
        if is_redundant_local_sync(path, main, group):
            return (3, path.name)
        if system_main and has_meaningful_exec_override(main, system_main):
            return (0, path.name)
        if path.parent in SYSTEM_DIRS:
            return (1, path.name)
        if path.parent == LOCAL_APP:
            return (2, path.name)
        if path.parent == NIX_APP:
            return (4, path.name)
        return (5, path.name)

    return min(group, key=rank)


def patch_duplicate_actions() -> None:
    standalone_execs = {
        normalize_exec(main.get("Exec", ""))
        for _path, main, _priority, _key in collect_visible_entries()
        if normalize_exec(main.get("Exec", ""))
    }

    for src_dir in SYSTEM_DIRS:
        if not src_dir.is_dir():
            continue
        for src in sorted(src_dir.glob("*.desktop")):
            main, actions = parse_desktop(src)
            if not actions:
                continue

            duplicate_action_names = {
                action_name
                for action_name, action_main in actions
                if normalize_exec(action_main.get("Exec", "")) in standalone_execs
            }
            if not duplicate_action_names:
                continue

            dst = LOCAL_APP / src.name
            if dst.exists():
                dst_main, _ = parse_desktop(dst)
                if has_meaningful_exec_override(dst_main, main):
                    continue

            kept_actions = [
                (action_name, action_main)
                for action_name, action_main in actions
                if action_name not in duplicate_action_names
            ]

            lines: list[str] = []
            with src.open(encoding="utf-8", errors="replace") as handle:
                in_removed_action = False
                for raw_line in handle:
                    stripped = raw_line.strip()
                    if stripped.startswith("[") and stripped.endswith("]"):
                        section = stripped[1:-1]
                        in_removed_action = section.startswith("Desktop Action ") and section.removeprefix(
                            "Desktop Action "
                        ).strip() in duplicate_action_names
                        if not in_removed_action:
                            lines.append(raw_line.rstrip("\n"))
                        continue
                    if in_removed_action:
                        continue
                    if stripped.startswith("Actions="):
                        if kept_actions:
                            action_list = ";".join(name for name, _ in kept_actions) + ";"
                            lines.append(f"Actions={action_list}")
                        else:
                            continue
                        continue
                    lines.append(raw_line.rstrip("\n"))

            LOCAL_APP.mkdir(parents=True, exist_ok=True)
            dst.write_text("\n".join(lines) + "\n", encoding="utf-8")
            dst.chmod(0o644)


def dedup_entries() -> None:
    entries = collect_visible_entries()
    groups: dict[tuple[str, str], list[tuple[Path, dict[str, str], int]]] = defaultdict(list)
    for path, main, priority, key in entries:
        groups[key].append((path, main, priority))

    for group in groups.values():
        if len(group) < 2:
            continue
        canonical_path, canonical_main, _canonical_priority = pick_canonical(group)
        for path, main, priority in group:
            if path == canonical_path:
                continue
            if path.parent not in (LOCAL_APP, NIX_APP):
                continue
            remove_inferior_duplicate(path, canonical_main)

    for path, main, _priority, key in entries:
        if path.parent != LOCAL_APP or not is_hidden(main):
            continue
        group = groups.get(key, [])
        if any(other_path.parent in SYSTEM_DIRS for other_path, _, _ in group):
            path.unlink(missing_ok=True)


def update_desktop_database() -> None:
    if not LOCAL_APP.is_dir():
        return
    if os.system(f'command -v update-desktop-database >/dev/null && update-desktop-database "{LOCAL_APP}" 2>/dev/null') != 0:
        pass


def should_sync_nix_desktop(path: Path) -> bool:
    if path.name in SKIP_BASENAMES:
        return False
    main, _ = parse_desktop(path)
    if is_hidden(main):
        return False
    return not equivalent_exists_outside_nix(main)


def cmd_dedup() -> int:
    dedup_entries()
    update_desktop_database()
    return 0


def cmd_patch_actions() -> int:
    patch_duplicate_actions()
    return 0


def cmd_should_sync(path_str: str) -> int:
    path = Path(path_str)
    if not path.is_file():
        return 1
    return 0 if should_sync_nix_desktop(path) else 1


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        return cmd_dedup()
    command = argv[1]
    if command == "dedup":
        return cmd_dedup()
    if command == "patch-actions":
        return cmd_patch_actions()
    if command == "should-sync":
        if len(argv) != 3:
            return 2
        return cmd_should_sync(argv[2])
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
