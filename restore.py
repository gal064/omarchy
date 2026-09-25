#!/usr/bin/env python3

"""Restore file changes made by the Quattro version of customize.py.

This restores only the script's known files and fenced sections. It deliberately
does not scan for arbitrary ``*.original`` files, reinstall removed packages,
or delete web apps that may contain user data.
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path

BACKUP_SUFFIX = ".quattro-original"
APPLIED_SUFFIX = ".quattro-applied"
ABSENT_BACKUP_SENTINEL = "__OMARCHY_CUSTOMIZE_FILE_DID_NOT_EXIST__\n"
REMOVED_SUFFIX = ".quattro-removed"


USER_TARGETS = (
    ".bashrc",
    ".config/hypr/bindings.lua",
    ".config/hypr/input.lua",
    ".config/hypr/looknfeel.lua",
    ".config/uwsm/env.d/99-gal-customizations",
    ".config/alacritty/alacritty.toml",
    ".config/ghostty/config",
    ".config/foot/foot.ini",
    ".local/state/omarchy/defaults/editor",
    ".local/share/applications/google-chrome.desktop",
    ".local/share/nautilus/scripts/open-in-vscode",
)

REMOVED_TARGETS = (
    ".config/nvim",
    ".local/share/nvim",
    ".local/state/nvim",
    ".cache/nvim",
    ".config/1Password",
    ".local/share/1Password",
    ".cache/1Password",
    ".ssh/1Password",
)

FENCES_BY_TARGET = {
    ".bashrc": ("BASH CUSTOMIZATIONS", "GHOSTTY SSH TRUECOLOR"),
    ".config/hypr/bindings.lua": ("OMARCHY BINDING CUSTOMIZATIONS",),
    ".config/hypr/input.lua": ("OMARCHY INPUT CUSTOMIZATIONS",),
    ".config/hypr/looknfeel.lua": ("OMARCHY LOOK CUSTOMIZATIONS",),
    ".config/uwsm/env.d/99-gal-customizations": ("PLAYWRIGHT WAYLAND CUSTOMIZATION",),
    ".config/ghostty/config": (
        "OMARCHY GHOSTTY CUSTOMIZATIONS",
        "OMARCHY GHOSTTY MAC TABS",
    ),
}

NAUTILUS_MARKER = "# Managed by customize.py for Omarchy Quattro."
KEYD_MARKER = "# === START OMARCHY CUSTOMIZATION ==="


def backup_path(path: Path) -> Path:
    return path.with_name(path.name + BACKUP_SUFFIX)


def applied_path(path: Path) -> Path:
    return path.with_name(path.name + APPLIED_SUFFIX)


def clear_restore_metadata(backup: Path, applied: Path, dry_run: bool) -> None:
    if dry_run:
        return
    backup.unlink(missing_ok=True)
    applied.unlink(missing_ok=True)


def fence_prefix(path: Path) -> str:
    return "--" if path.suffix == ".lua" else "#"


def remove_fenced_section(content: str, path: Path, label: str) -> tuple[str, bool]:
    prefix = fence_prefix(path)
    start = f"{prefix} === START {label} ==="
    end = f"{prefix} === END {label} ==="
    pattern = re.compile(rf"(?ms)^\s*{re.escape(start)}$.*?^\s*{re.escape(end)}$\n?")
    updated, count = pattern.subn("", content, count=1)
    return updated, count == 1


def restore_user_file(home: Path, relative: str, dry_run: bool) -> bool | None:
    path = home / relative
    backup = backup_path(path)
    applied = applied_path(path)

    # Fenced files can be restored surgically. Prefer removing only our owned
    # sections from the current file so edits made after customization survive.
    if path.exists() and relative in FENCES_BY_TARGET:
        content = path.read_text()
        changed = False
        for label in FENCES_BY_TARGET[relative]:
            content, removed = remove_fenced_section(content, path, label)
            changed = changed or removed
        if changed:
            if dry_run:
                print(f"- Would remove owned customization from {path}")
            elif content.strip():
                path.write_text(content)
                print(f"✓ Removed owned customization from {path}")
            else:
                path.unlink()
                print(f"✓ Removed customization-created file {path}")
            clear_restore_metadata(backup, applied, dry_run)
            return True

    if backup.exists():
        if applied.exists():
            expected = applied.read_text()
            current_matches = (
                not path.exists()
                if expected == ABSENT_BACKUP_SENTINEL
                else path.exists() and path.read_text() == expected
            )
            if not current_matches:
                print(
                    f"! Refusing stale restore of {path}; it changed after "
                    f"customization. Original backup remains at {backup}"
                )
                return False
        if backup.read_text() == ABSENT_BACKUP_SENTINEL:
            if dry_run:
                print(f"- Would remove customization-created file {path}")
            else:
                path.unlink(missing_ok=True)
                print(f"✓ Removed customization-created file {path}")
            clear_restore_metadata(backup, applied, dry_run)
            return True
        if dry_run:
            print(f"- Would restore {path} from {backup}")
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(backup, path)
            print(f"✓ Restored {path} from {backup}")
        clear_restore_metadata(backup, applied, dry_run)
        return True

    if not path.exists():
        print(f"- No customization file or backup found: {path}")
        return None

    content = path.read_text()
    changed = False

    if relative == ".local/share/nautilus/scripts/open-in-vscode":
        changed = NAUTILUS_MARKER in content
        if changed:
            content = ""

    if not changed:
        print(f"- No owned customization found in {path}")
        return None

    if dry_run:
        print(f"- Would remove owned customization from {path}")
        return True

    if content.strip():
        path.write_text(content)
        print(f"✓ Removed owned customization from {path}")
    else:
        path.unlink()
        print(f"✓ Removed customization-created file {path}")
    clear_restore_metadata(backup, applied, dry_run)
    return True


def restore_keyd(dry_run: bool, path: Path | None = None) -> bool | None:
    path = path or Path("/etc/keyd/default.conf")
    backup = path.with_name(path.name + BACKUP_SUFFIX)
    applied = path.with_name(path.name + APPLIED_SUFFIX)
    if applied.exists() and dry_run:
        print(f"- Would verify {path} still matches {applied} before restoring")
    elif applied.exists():
        matches = subprocess.run(
            ("sudo", "cmp", "-s", str(path), str(applied)), check=False
        )
        if matches.returncode != 0:
            print(
                f"! Refusing stale restore of {path}; it changed after "
                f"customization. Original backup remains at {backup}"
            )
            return False
    if backup.exists():
        command = ("sudo", "cp", str(backup), str(path))
        if dry_run:
            print(f"- Would run: {' '.join(command)}")
            return True
        result = subprocess.run(command, check=False)
        if result.returncode == 0:
            subprocess.run(("sudo", "rm", "-f", str(backup), str(applied)), check=False)
            reload_result = subprocess.run(("sudo", "keyd", "reload"), check=False)
            if reload_result.returncode != 0:
                print(f"! Restored {path}, but keyd reload failed")
                return False
            print(f"✓ Restored {path} from {backup}")
            return True
        print(f"! Failed to restore {path}")
        return False

    if not path.exists():
        print("- No keyd customization or backup found")
        return None

    try:
        owned = KEYD_MARKER in path.read_text()
    except PermissionError:
        owned = False
    if not owned:
        print("- Current keyd config is not recognized as customize.py-owned")
        return None

    command = ("sudo", "rm", "-f", str(path))
    if dry_run:
        print(f"- Would run: {' '.join(command)}")
        return True
    result = subprocess.run(command, check=False)
    if result.returncode == 0:
        subprocess.run(("sudo", "rm", "-f", str(applied)), check=False)
        reload_result = subprocess.run(("sudo", "keyd", "reload"), check=False)
        if reload_result.returncode != 0:
            print(f"! Removed {path}, but keyd reload failed")
            return False
        print(f"✓ Removed customization-created {path}")
        return True
    print(f"! Failed to remove {path}")
    return False


def restore_quarantined_target(home: Path, relative: str, dry_run: bool) -> bool | None:
    path = home / relative
    quarantine = path.with_name(path.name + REMOVED_SUFFIX)
    if not quarantine.exists():
        return None
    if path.exists():
        print(
            f"! Refusing to overwrite {path}; quarantined data remains at {quarantine}"
        )
        return False
    if dry_run:
        print(f"- Would restore {path} from {quarantine}")
    else:
        quarantine.rename(path)
        print(f"✓ Restored {path} from {quarantine}")
    return True


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run", action="store_true", help="show restore actions without writing"
    )
    parser.add_argument(
        "--skip-keyd", action="store_true", help="do not restore /etc/keyd/default.conf"
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    if os.geteuid() == 0:
        print(
            "! Do not run restore.py as root; it restores the current user's files "
            "and invokes sudo only for keyd."
        )
        return 1
    restored = 0
    restore_failed = False
    for relative in USER_TARGETS:
        result = restore_user_file(Path.home(), relative, args.dry_run)
        if result is True:
            restored += 1
        elif result is False:
            restore_failed = True
    for relative in REMOVED_TARGETS:
        result = restore_quarantined_target(Path.home(), relative, args.dry_run)
        if result is True:
            restored += 1
        elif result is False:
            restore_failed = True
    keyd_failed = False
    if not args.skip_keyd:
        keyd_result = restore_keyd(args.dry_run)
        if keyd_result is True:
            restored += 1
        elif keyd_result is False:
            keyd_failed = True

    print(f"\nRestored or removed {restored} owned customization target(s).")
    print(
        "Package, web-app, and global Git config changes are intentionally left "
        "for manual review."
    )
    return 1 if keyd_failed or restore_failed else 0


if __name__ == "__main__":
    sys.exit(main())
