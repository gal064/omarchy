#!/usr/bin/env python3

"""Apply Gal's post-install customizations to Omarchy Quattro.

Run this only after the official ``omarchy upgrade to quattro`` flow has
completed and the machine has rebooted. Omarchy-owned files under
``/usr/share/omarchy`` are never modified; durable changes are made through
Quattro's commands and user configuration entry points.
"""

from __future__ import annotations

import argparse
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Iterable, Sequence
from pathlib import Path

BACKUP_SUFFIX = ".quattro-original"
APPLIED_SUFFIX = ".quattro-applied"
ABSENT_BACKUP_SENTINEL = "__OMARCHY_CUSTOMIZE_FILE_DID_NOT_EXIST__\n"
REMOVED_SUFFIX = ".quattro-removed"


REMOVE_PACKAGES = (
    # Editor/development packages intentionally excluded from this setup.
    # Keep lua51, cargo, clang, llvm, and gcc14 as explicit user choices.
    "omarchy-nvim",
    "neovim",
    "nvim",
    "luarocks",
    "tree-sitter-cli",
    "mariadb-libs",
    "mise-bin",
    # ruby stays: Omarchy 4's tobi-try depends on it, so omarchy-pkg-drop
    # would refuse the removal anyway.
    "wl-clip-persist",
    # Applications intentionally excluded from this setup. Both legacy and
    # current names are harmless because omarchy-pkg-drop ignores missing ones.
    "zoom",
    "obsidian",
    "obsidian-bin",
    "signal-desktop",
    "dropbox-cli",
    "1password",
    "1password-beta",
    "1password-cli",
    "localsend",
    "localsend-bin",
)

REMOVE_FONT_PACKAGES = (
    "noto-fonts-cjk",
    "noto-fonts-extra",
)

INSTALL_PACKAGES = (
    "nano",
    "ttf-liberation",
)

USER_DESKTOP_FILES = (
    "nvim.desktop",
    "dropbox.desktop",
    "Zoom.desktop",
    "chromium.desktop",
    "obsidian.desktop",
    "signal-desktop.desktop",
    "1password.desktop",
    "1password-beta.desktop",
    "Google Photos.desktop",
)

REMOVE_WEBAPPS = (
    "HEY",
    "Basecamp",
    "X",
    "Google Photos",
)

WEBAPPS = (
    (
        "Gmail",
        "https://mail.google.com",
        "https://cdn.jsdelivr.net/gh/homarr-labs/dashboard-icons/png/gmail.png",
    ),
    (
        "Google Calendar",
        "https://calendar.google.com",
        "https://cdn.jsdelivr.net/gh/homarr-labs/dashboard-icons/png/google-calendar.png",
    ),
    (
        "Google AI",
        "https://aistudio.google.com/",
        "https://cdn.jsdelivr.net/gh/homarr-labs/dashboard-icons/png/google-gemini.png",
    ),
)

KEYD_CONFIG = """# === START OMARCHY CUSTOMIZATION ===
# Mac-like modifier behavior.
[ids]
*

[main]
leftalt = layer(mac_control)
leftcontrol = layer(alt)
rightalt = layer(mac_control)
rightcontrol = layer(alt)

[mac_control:C]
left = home
right = end

[alt:A]
c = C-c
# === END OMARCHY CUSTOMIZATION ===
"""


class CustomizationError(RuntimeError):
    """Raised when a customization cannot be applied safely."""


class Customizer:
    def __init__(
        self,
        *,
        home: Path | None = None,
        root: Path | None = None,
        dry_run: bool = False,
        assume_yes: bool = False,
        skip_keyd: bool = False,
    ) -> None:
        self.home = (home or Path.home()).expanduser()
        self.root = root or Path("/")
        self.dry_run = dry_run
        self.assume_yes = assume_yes
        self.skip_keyd = skip_keyd
        self.failures: list[str] = []
        self.package_removals: dict[str, bool] = {}

    def home_path(self, relative: str) -> Path:
        return self.home / relative

    def system_path(self, absolute: str) -> Path:
        return self.root / absolute.lstrip("/")

    def run(self, *command: str, quiet: bool = False) -> bool:
        """Run a command directly, without the legacy Omarchy Bash checkout."""
        rendered = shlex.join(command)
        print(f"$ {rendered}")
        if self.dry_run:
            return True

        try:
            if quiet:
                result = subprocess.run(
                    command,
                    check=False,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            else:
                result = subprocess.run(command, check=False)
        except FileNotFoundError:
            print(f"! Command not found: {command[0]}")
            return False
        return result.returncode == 0

    def require_quattro(self) -> None:
        """Refuse to run against a legacy or half-upgraded installation."""
        if self.dry_run:
            return
        if os.geteuid() == 0 and self.root == Path("/"):
            raise CustomizationError(
                "Do not run customize.py as root; it invokes sudo only for the "
                "specific system operations that need it."
            )

        omarchy_root = self.system_path("/usr/share/omarchy")
        required = (
            omarchy_root / "config/hypr/hyprland.lua",
            omarchy_root / "shell/shell.qml",
            self.home_path(".config/hypr/hyprland.lua"),
            self.home_path(".config/omarchy/shell.json"),
        )
        missing = [str(path) for path in required if not path.exists()]
        if shutil.which("omarchy") is None:
            missing.append("omarchy command in PATH")
        if not missing and not self.run("omarchy-shell", "shell", "ping", quiet=True):
            missing.append("responsive Quattro shell (reboot into the Quattro desktop)")
        if missing:
            details = "\n  - ".join(missing)
            raise CustomizationError(
                "Omarchy Quattro is not fully installed. Run the official "
                "'omarchy upgrade to quattro' flow, reboot, and retry. Missing:\n"
                f"  - {details}"
            )

    @staticmethod
    def report_unsupported_legacy_preferences() -> None:
        print("\nQuattro compatibility notes:")
        print(
            "- Ghostty-specific persistent notification timeouts are not applied: "
            "Quattro has notification history but no supported per-app timeout override."
        )
        print(
            "- Apple-display brightness support is preserved: Quattro owns asdcontrol "
            "and has no supported Apple-only disable switch."
        )
        print(
            "- PLAYWRIGHT_CHROMIUM_ARGS is not a Playwright-supported global setting; "
            "set Wayland flags in each project's launchOptions.args instead."
        )
        print(
            "- Selectively removed bundled launchers and mise wrappers can be "
            "recreated by a future omarchy-refresh-applications run; rerun this "
            "script if they reappear."
        )

    def backup(self, path: Path) -> Path | None:
        """Create one stable pre-customization backup for a file."""
        if not path.exists():
            return None

        backup = path.with_name(path.name + BACKUP_SUFFIX)
        if backup.exists():
            try:
                was_absent = backup.read_text() == ABSENT_BACKUP_SENTINEL
            except (OSError, UnicodeDecodeError):
                was_absent = False
            if was_absent:
                if self.dry_run:
                    print(f"- Would replace absence marker with backup of {path}")
                    return backup
                shutil.copy2(path, backup)
                print(f"✓ Replaced absence marker with backup of {path}")
                return backup
            print(f"- Backup already exists: {backup}")
            return backup
        if self.dry_run:
            print(f"- Would back up {path} to {backup}")
            return backup

        backup.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, backup)
        print(f"✓ Backed up {path} to {backup}")
        return backup

    def record_applied(self, path: Path, *, absent: bool = False) -> None:
        if self.dry_run:
            return
        applied = path.with_name(path.name + APPLIED_SUFFIX)
        applied.write_text(ABSENT_BACKUP_SENTINEL if absent else path.read_text())

    @staticmethod
    def _comment_prefix(path: Path) -> str:
        return "--" if path.suffix == ".lua" else "#"

    def upsert_fenced(self, path: Path, lines: Iterable[str], label: str) -> bool:
        """Insert or replace one owned section while preserving the rest."""
        prefix = self._comment_prefix(path)
        start = f"{prefix} === START {label} ==="
        end = f"{prefix} === END {label} ==="
        body = "\n".join(lines).rstrip()
        replacement = f"{start}\n{body}\n{end}"
        current = path.read_text() if path.exists() else ""

        has_start = start in current
        has_end = end in current
        if has_start != has_end:
            print(f"! Refusing to edit {path}: incomplete {label} fence")
            return False

        if has_start:
            pattern = re.compile(rf"(?ms)^{re.escape(start)}$.*?^{re.escape(end)}$")
            updated, count = pattern.subn(replacement, current, count=1)
            if count != 1:
                print(f"! Could not uniquely replace {label} in {path}")
                return False
        else:
            separator = (
                "" if not current else ("" if current.endswith("\n\n") else "\n")
            )
            updated = f"{current}{separator}{replacement}\n"

        if updated == current:
            print(f"- {label} already current in {path}")
            return True
        if self.dry_run:
            print(f"- Would update {label} in {path}")
            return True

        self.backup(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(updated)
        print(f"✓ Updated {label} in {path}")
        return True

    def install_chrome(self) -> None:
        """Use Quattro's installer so flags, policies, and extensions stay intact."""
        print("\nInstalling and selecting Google Chrome...")
        if not self.run("omarchy-install-browser", "chrome"):
            self.failures.append("Google Chrome installation")
            return
        if not self.run("omarchy-default-browser", "chrome"):
            self.failures.append("Google Chrome default selection")
            return

        self.remove_legacy_chrome_desktop_override()

        # Remove Chromium only after Chrome is installed and selected.
        if not self.run("omarchy-pkg-drop", "chromium"):
            self.failures.append("Chromium removal")

    def remove_legacy_chrome_desktop_override(self) -> None:
        """Stop the v3 customization from shadowing Quattro's launcher."""
        path = self.home_path(".local/share/applications/google-chrome.desktop")
        if not path.exists():
            return

        old_signature = (
            "google-chrome-stable --ozone-platform=wayland "
            "--ozone-platform-hint=wayland "
            "--enable-features=TouchpadOverscrollHistoryNavigation"
        )
        try:
            owned = old_signature in path.read_text()
        except OSError as error:
            print(f"! Could not inspect legacy Chrome launcher {path}: {error}")
            self.failures.append("inspect legacy Chrome desktop override")
            return
        if not owned:
            print(f"- Preserving non-customize.py Chrome launcher: {path}")
            return
        if self.dry_run:
            print(f"- Would remove legacy Chrome launcher {path}")
            return

        self.backup(path)
        path.unlink()
        self.record_applied(path, absent=True)
        print(f"✓ Removed legacy Chrome launcher {path}")

    def manage_packages(self) -> bool:
        # Keep the current editor stack until Nano is installed.
        print("\nInstalling preferred packages...")
        nano_ready = False
        for package in INSTALL_PACKAGES:
            if self.run("omarchy-pkg-add", package):
                print(f"✓ Installed or retained {package}")
                if package == "nano":
                    nano_ready = True
            else:
                self.failures.append(f"install {package}")

        if nano_ready:
            nano_ready = self.configure_default_editor()

        print("\nRemoving excluded packages...")
        removals = tuple(
            package
            for package in REMOVE_PACKAGES
            if nano_ready or package not in {"omarchy-nvim", "neovim", "nvim"}
        )
        if not nano_ready:
            print("! Preserving Neovim because Nano did not install successfully")
        for package in (*removals, *REMOVE_FONT_PACKAGES):
            removed = self.run("omarchy-pkg-drop", package)
            self.package_removals[package] = removed
            if removed:
                print(f"✓ Removed or confirmed absent: {package}")
            else:
                self.failures.append(f"remove {package}")
        return nano_ready

    def remove_mise_wrappers(self) -> None:
        """Drop the mise shims Quattro writes over native agent CLIs.

        install/user/mise.sh (run by omarchy-refresh-applications during the
        upgrade) replaces ~/.local/bin/claude, codex, and friends with wrappers
        that exec through mise. Without mise-bin those wrappers only fail, so
        remove them and relink the native installs where they still exist.
        """
        print("\nRemoving mise wrappers left in ~/.local/bin...")
        if not self.package_removals.get("mise-bin", False):
            print("! Preserving mise wrappers because mise-bin was not removed")
            return

        local_bin = self.home_path(".local/bin")
        removed: list[str] = []
        if local_bin.is_dir():
            for path in sorted(local_bin.iterdir()):
                if not path.is_file() or path.is_symlink():
                    continue
                try:
                    content = path.read_text()
                except (OSError, UnicodeDecodeError):
                    continue
                if "mise use -g" not in content or "exec mise x" not in content:
                    continue
                if self.dry_run:
                    print(f"- Would remove mise wrapper {path}")
                else:
                    path.unlink()
                    print(f"✓ Removed mise wrapper {path}")
                removed.append(path.name)

        for name, target, hint in (
            ("claude", self._native_claude(), "curl -fsSL https://claude.ai/install.sh | bash"),
            ("codex", self._native_codex(), "npm install -g @openai/codex"),
        ):
            if name not in removed:
                continue
            link = local_bin / name
            if target is None:
                print(f"! No native {name} install found; reinstall with: {hint}")
                self.failures.append(f"relink native {name}")
                continue
            if self.dry_run:
                print(f"- Would link {link} -> {target}")
                continue
            link.parent.mkdir(parents=True, exist_ok=True)
            link.symlink_to(target)
            print(f"✓ Linked {link} -> {target}")

    def _native_claude(self) -> Path | None:
        versions = self.home_path(".local/share/claude/versions")
        if not versions.is_dir():
            return None

        def version_key(path: Path) -> tuple[int, ...]:
            parts = re.findall(r"\d+", path.name)
            return tuple(int(part) for part in parts)

        candidates = [path for path in versions.iterdir() if path.is_file()]
        if not candidates:
            return None
        return max(candidates, key=version_key)

    def _native_codex(self) -> Path | None:
        codex = self.home_path(".codex/packages/standalone/current/bin/codex")
        return codex if codex.exists() else None

    def configure_default_editor(self) -> bool:
        """Keep Omarchy's config editor usable after removing Neovim."""
        print("\nSelecting Nano as Omarchy's default editor...")
        if not self.run("omarchy-cmd-present", "nano", quiet=True):
            self.failures.append("select Nano as default editor")
            return False

        editor_file = self.home_path(".local/state/omarchy/defaults/editor")
        current = editor_file.read_text() if editor_file.exists() else ""
        updated = "nano\n"
        if current == updated:
            print("- Nano is already Omarchy's default editor")
            return True
        if self.dry_run:
            print(f"- Would select Nano in {editor_file}")
            return True

        editor_file.parent.mkdir(parents=True, exist_ok=True)
        if editor_file.exists():
            self.backup(editor_file)
        else:
            backup = editor_file.with_name(editor_file.name + BACKUP_SUFFIX)
            backup.write_text(ABSENT_BACKUP_SENTINEL)
            print(f"✓ Recorded that {editor_file} did not previously exist")
        editor_file.write_text(updated)
        self.record_applied(editor_file)
        print(f"✓ Selected Nano in {editor_file}")
        return True

    def remove_user_config_directories(self) -> None:
        print("\nRemoving configs for excluded applications...")
        groups = (
            (
                "Neovim",
                ("omarchy-nvim", "neovim", "nvim"),
                (
                    ".config/nvim",
                    ".local/share/nvim",
                    ".local/state/nvim",
                    ".cache/nvim",
                ),
            ),
            (
                "1Password",
                ("1password", "1password-beta", "1password-cli"),
                (
                    ".config/1Password",
                    ".local/share/1Password",
                    ".cache/1Password",
                    ".ssh/1Password",
                ),
            ),
        )

        for name, packages, paths in groups:
            if not all(
                self.package_removals.get(package, False) for package in packages
            ):
                print(
                    f"! Preserving {name} data because package removal did not "
                    "fully succeed"
                )
                continue
            for relative in paths:
                path = self.home_path(relative)
                if not path.exists():
                    continue
                if self.dry_run:
                    print(f"- Would quarantine {path}")
                    continue
                quarantine = path.with_name(path.name + REMOVED_SUFFIX)
                if quarantine.exists():
                    print(
                        f"! Preserving {path}: quarantine already exists at "
                        f"{quarantine}"
                    )
                    self.failures.append(f"quarantine {path}")
                    continue
                path.rename(quarantine)
                print(f"✓ Quarantined {path} as {quarantine}")

    def manage_desktop_entries(self) -> None:
        print("\nManaging user desktop entries and web apps...")
        user_apps = self.home_path(".local/share/applications")
        if not self.dry_run:
            user_apps.mkdir(parents=True, exist_ok=True)

        for filename in USER_DESKTOP_FILES:
            path = user_apps / filename
            if not path.exists():
                continue
            if self.dry_run:
                print(f"- Would remove {path}")
            else:
                path.unlink()
                print(f"✓ Removed {path}")

        for name in REMOVE_WEBAPPS:
            if not self.run("omarchy-webapp-remove", name, quiet=True):
                self.failures.append(f"remove web app {name}")

        for name, url, icon in WEBAPPS:
            if not self.run("omarchy-webapp-install", name, url, icon):
                self.failures.append(f"create web app {name}")

    def create_nautilus_vscode_script(self) -> None:
        print("\nCreating Nautilus open-in-editor script...")
        script_path = self.home_path(".local/share/nautilus/scripts/open-in-vscode")
        content = """#!/bin/bash
# Managed by customize.py for Omarchy Quattro.
set -e

if command -v code >/dev/null 2>&1; then
  editor=(code)
elif command -v cursor >/dev/null 2>&1; then
  editor=(cursor)
else
  zenity --error --text="Neither VS Code nor Cursor is installed."
  exit 1
fi

selected=${NAUTILUS_SCRIPT_SELECTED_FILE_PATHS:-}
if [[ -z $selected ]]; then
  zenity --error --text="No local files selected."
  exit 1
fi

while IFS= read -r file; do
  [[ -n $file && -e $file ]] && "${editor[@]}" "$file"
done <<< "$selected"
"""
        current = script_path.read_text() if script_path.exists() else ""
        if current == content:
            print(f"- Nautilus script already current: {script_path}")
            return
        if self.dry_run:
            print(f"- Would write {script_path}")
            return

        self.backup(script_path)
        script_path.parent.mkdir(parents=True, exist_ok=True)
        script_path.write_text(content)
        script_path.chmod(0o755)
        self.record_applied(script_path)
        print(f"✓ Wrote {script_path}")

    def customize_bash(self) -> None:
        print("\nConfiguring Bash...")
        lines = (
            'export EDITOR="nano"',
            'export SUDO_EDITOR="$EDITOR"',
            "alias e='nano'",
            "alias open='xdg-open'",
            "alias c='claude --allow-dangerously-skip-permissions'",
            "alias cx='codex --ask-for-approval on-request -c '\"'\"'approvals_reviewer=\"auto_review\"'\"'\"''",
            "alias ter='codex --ask-for-approval on-request -c '\"'\"'approvals_reviewer=\"auto_review\"'\"'\"' -m gpt-5.6-terra -c '\"'\"'model_reasoning_effort=\"medium\"'\"'\"''",
            "",
            "code() {",
            '  /usr/bin/code "$@" &',
            '  if [[ $(ps -o comm= -p "$PPID" 2>/dev/null) =~ ^(alacritty|foot|ghostty)$ ]]; then',
            "    sleep 0.5",
            '    kill "$PPID" 2>/dev/null',
            "  fi",
            "}",
            "",
            "if [[ $- == *i* ]]; then",
            "  bind 'set show-all-if-ambiguous on'",
            "  bind '\"\\t\":menu-complete'",
            "  bind 'set menu-complete-display-prefix on'",
            "fi",
        )
        if not self.upsert_fenced(
            self.home_path(".bashrc"), lines, "BASH CUSTOMIZATIONS"
        ):
            self.failures.append("Bash customizations")

    def customize_ssh_ghostty_truecolor(self) -> None:
        lines = (
            'if [[ -n ${SSH_TTY:-} && ${TERM:-} == "xterm-ghostty" ]]; then',
            '  export COLORTERM="truecolor"',
            "fi",
        )
        if not self.upsert_fenced(
            self.home_path(".bashrc"), lines, "GHOSTTY SSH TRUECOLOR"
        ):
            self.failures.append("Ghostty SSH truecolor")

    def customize_hyprland(self) -> None:
        print("\nWriting Quattro Hyprland Lua overrides...")
        bindings = (
            # Only keys Omarchy 4 still binds by default need unbinding first.
            'hl.unbind("SUPER + SHIFT + E")',
            'hl.unbind("SUPER + SHIFT + G")',
            'hl.unbind("SUPER + SHIFT + O")',
            'hl.unbind("SUPER + SHIFT + SLASH")',
            'hl.unbind("SUPER + SHIFT + C")',
            'hl.unbind("SUPER + SHIFT + ALT + E")',
            'hl.unbind("SUPER + SHIFT + P")',
            'hl.unbind("SUPER + SHIFT + X")',
            'hl.unbind("SUPER + SHIFT + ALT + X")',
            "",
            'o.bind("SUPER + SHIFT + J", "Joplin", "joplin-desktop")',
            'o.bind("CTRL + SHIFT + C", "Clipboard manager", "omarchy-shell shell toggle omarchy.clipboard")',
            'o.bind("SUPER + E", "Full width", hl.dsp.window.fullscreen({ mode = "maximized" }))',
            'o.bind("SUPER + SHIFT + E", "Resize active window", "hyprctl dispatch resizeactive 67% 0")',
            'o.bind("CTRL + SHIFT + code:13", "Screenshot", "omarchy-capture-screenshot")',
            'o.bind("CTRL + SHIFT + code:12", "Screenrecording", "omarchy-capture-screenrecording --stop-recording || omarchy-menu toggle trigger.capture.screenrecord")',
        )
        input_config = (
            "hl.config({",
            "  input = {",
            '    kb_layout = "us,il",',
            '    kb_options = "grp:caps_toggle",',
            "    touchpad = {",
            "      scroll_factor = 1.2,",
            "    },",
            "  },",
            "})",
        )
        looknfeel = (
            "hl.config({",
            "  misc = {",
            "    on_focus_under_fullscreen = 2,",
            "  },",
            "})",
            "",
            "-- Omarchy tags windows default-opacity and sets 0.985/0.96 on the tag;",
            "-- apps that opt out of the tag keep their own opacity.",
            'o.window({ tag = "default-opacity" }, { opacity = "1 1" })',
        )

        configs = (
            (".config/hypr/bindings.lua", bindings, "OMARCHY BINDING CUSTOMIZATIONS"),
            (".config/hypr/input.lua", input_config, "OMARCHY INPUT CUSTOMIZATIONS"),
            (".config/hypr/looknfeel.lua", looknfeel, "OMARCHY LOOK CUSTOMIZATIONS"),
        )
        for relative, lines, label in configs:
            if not self.upsert_fenced(self.home_path(relative), lines, label):
                self.failures.append(label)

    def customize_terminal_paste(self) -> None:
        print("\nConfiguring terminal paste behavior...")
        alacritty = self.home_path(".config/alacritty/alacritty.toml")
        if alacritty.exists():
            current = alacritty.read_text()
            updated = current
            binding = '{ key = "V", mods = "Control", action = "Paste" },'
            if binding not in updated:
                bindings_pattern = re.compile(
                    r"(?m)^(?P<prefix>\s*(?:keyboard\.)?bindings\s*=\s*)\["
                )
                if bindings_pattern.search(updated):
                    updated = bindings_pattern.sub(
                        lambda match: f"{match.group(0)}\n{binding}", updated, count=1
                    )
                elif "[keyboard]" in updated:
                    updated = updated.replace(
                        "[keyboard]", f"[keyboard]\nbindings = [\n{binding}\n]", 1
                    )
                else:
                    updated += f"\n[keyboard]\nbindings = [\n{binding}\n]\n"

            selection_pattern = re.compile(
                r"(?m)^(?P<prefix>\s*(?:selection\.)?save_to_clipboard\s*=).*$"
            )
            if selection_pattern.search(updated):
                updated = selection_pattern.sub(
                    lambda match: f"{match.group('prefix')} true", updated, count=1
                )
            elif re.search(r"(?m)^\s*selection\s*=\s*\{", updated):
                inline_selection = re.compile(
                    r"(?m)^(?P<prefix>\s*selection\s*=\s*\{)(?P<body>[^}]*)"
                    r"(?P<suffix>\}\s*(?:#.*)?)$"
                )

                def update_inline_selection(match: re.Match[str]) -> str:
                    body = match.group("body")
                    property_pattern = re.compile(r"save_to_clipboard\s*=\s*[^,]+")
                    if property_pattern.search(body):
                        body = property_pattern.sub(
                            "save_to_clipboard = true", body, count=1
                        )
                    else:
                        separator = ", " if body.strip() else ""
                        body = f"{body.rstrip()}{separator}save_to_clipboard = true "
                    return f"{match.group('prefix')}{body}{match.group('suffix')}"

                updated = inline_selection.sub(
                    update_inline_selection, updated, count=1
                )
            elif "[selection]" in updated:
                updated = updated.replace(
                    "[selection]", "[selection]\nsave_to_clipboard = true", 1
                )
            else:
                updated += "\n[selection]\nsave_to_clipboard = true\n"
            self._write_updated(alacritty, current, updated, "Alacritty paste")

        ghostty = self.home_path(".config/ghostty/config")
        if ghostty.exists() and not self.upsert_fenced(
            ghostty,
            (
                "keybind = ctrl+v=paste_from_clipboard",
                "copy-on-select = clipboard",
            ),
            "OMARCHY GHOSTTY CUSTOMIZATIONS",
        ):
            self.failures.append("Ghostty paste")

        foot = self.home_path(".config/foot/foot.ini")
        if foot.exists():
            current = foot.read_text()
            updated, count = re.subn(
                r"(?m)^clipboard-paste=.*$",
                "clipboard-paste=Control+v Shift+Insert Control+Shift+v XF86Paste",
                current,
                count=1,
            )
            if count == 0:
                binding = (
                    "clipboard-paste=Control+v Shift+Insert Control+Shift+v XF86Paste"
                )
                if "[key-bindings]" in current:
                    updated = current.replace(
                        "[key-bindings]", f"[key-bindings]\n{binding}", 1
                    )
                else:
                    updated = f"{current.rstrip()}\n\n[key-bindings]\n{binding}\n"
                self._write_updated(foot, current, updated, "Foot paste")
            else:
                self._write_updated(foot, current, updated, "Foot paste")

    def customize_ghostty_mac_keys(self) -> None:
        ghostty = self.home_path(".config/ghostty/config")
        if not ghostty.exists():
            print("- Ghostty config not found; skipping Ghostty tab bindings")
            return
        lines = (
            "keybind = ctrl+t=new_tab",
            "keybind = ctrl+w=close_surface",
            "keybind = ctrl+d=new_split:right",
            "keybind = ctrl+shift+d=new_split:down",
            "keybind = ctrl+shift+left_bracket=previous_tab",
            "keybind = ctrl+shift+right_bracket=next_tab",
            "keybind = ctrl+one=goto_tab:1",
            "keybind = ctrl+two=goto_tab:2",
            "keybind = ctrl+three=goto_tab:3",
            "keybind = ctrl+four=goto_tab:4",
            "keybind = ctrl+five=goto_tab:5",
            "keybind = ctrl+six=goto_tab:6",
            "keybind = ctrl+seven=goto_tab:7",
            "keybind = ctrl+eight=goto_tab:8",
            "keybind = ctrl+nine=goto_tab:9",
        )
        if not self.upsert_fenced(ghostty, lines, "OMARCHY GHOSTTY MAC TABS"):
            self.failures.append("Ghostty Mac tab bindings")

    def _write_updated(
        self, path: Path, current: str, updated: str, description: str
    ) -> None:
        if current == updated:
            print(f"- {description} already current in {path}")
            return
        if self.dry_run:
            print(f"- Would update {description} in {path}")
            return
        self.backup(path)
        path.write_text(updated)
        self.record_applied(path)
        print(f"✓ Updated {description} in {path}")

    def install_and_configure_keyd(self) -> None:
        if self.skip_keyd:
            print("\n- Skipping keyd as requested")
            return

        print("\nInstalling and configuring keyd...")
        keyd_path = self.system_path("/etc/keyd/default.conf")
        if keyd_path.exists() and not self.assume_yes and not self.dry_run:
            response = (
                input(
                    f"{keyd_path} exists and will be replaced after backup. Continue? (y/N): "
                )
                .strip()
                .lower()
            )
            if response not in {"y", "yes"}:
                print("- Skipping keyd configuration")
                return

        if not self.run("omarchy-pkg-add", "keyd"):
            self.failures.append("install keyd")
            return

        backup_path = f"{keyd_path}{BACKUP_SUFFIX}"
        applied_path = f"{keyd_path}{APPLIED_SUFFIX}"
        if (
            keyd_path.exists()
            and not Path(backup_path).exists()
            and not self.run("sudo", "cp", str(keyd_path), backup_path)
        ):
            self.failures.append("back up keyd config")
            return

        if self.dry_run:
            print(f"- Would install keyd config at {keyd_path}")
            return

        with tempfile.NamedTemporaryFile("w", delete=False) as temporary:
            temporary.write(KEYD_CONFIG)
            temporary_path = temporary.name
        try:
            if not self.run(
                "sudo", "install", "-Dm644", temporary_path, str(keyd_path)
            ):
                self.failures.append("write keyd config")
                return
        finally:
            Path(temporary_path).unlink(missing_ok=True)

        if not self.run("sudo", "cp", str(keyd_path), applied_path):
            self.failures.append("record applied keyd config")
            return

        # Restart instead of `keyd reload`: keyd 2.6.0 segfaults on reload after
        # a config swap, and restart also covers a freshly installed daemon.
        if not self.run("sudo", "systemctl", "enable", "keyd"):
            self.failures.append("enable keyd")
        if not self.run("sudo", "systemctl", "restart", "keyd"):
            self.failures.append("restart keyd")

    def finalize(self) -> None:
        print("\nRefreshing desktop and Hyprland state...")
        user_apps = self.home_path(".local/share/applications")
        if not self.run("update-desktop-database", str(user_apps)):
            self.failures.append("desktop database refresh")
        if os.environ.get("HYPRLAND_INSTANCE_SIGNATURE"):
            if not self.run("hyprctl", "reload"):
                self.failures.append("Hyprland reload")
        else:
            print("- No live Hyprland session detected; changes apply next login")

    def apply(self) -> int:
        self.require_quattro()
        print("Applying Omarchy Quattro customizations")
        print("=" * 48)
        self.report_unsupported_legacy_preferences()

        self.install_chrome()
        self.manage_packages()
        self.remove_mise_wrappers()
        self.remove_user_config_directories()
        self.manage_desktop_entries()
        self.create_nautilus_vscode_script()
        self.customize_bash()
        self.customize_ssh_ghostty_truecolor()
        self.customize_hyprland()
        self.customize_terminal_paste()
        self.customize_ghostty_mac_keys()
        self.install_and_configure_keyd()
        self.finalize()

        print("\n" + "=" * 48)
        if self.failures:
            print("! Customization completed with failures:")
            for failure in self.failures:
                print(f"  - {failure}")
            return 1

        print("✓ Omarchy Quattro customization complete")
        print("✓ Quattro-owned files and Chrome flags were preserved")
        print("✓ Legacy Waybar, Walker, Mako, and Hyprland .conf paths were not used")
        return 0


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="show actions without changing the system",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="replace an existing keyd config without prompting",
    )
    parser.add_argument(
        "--skip-keyd", action="store_true", help="do not install or configure keyd"
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    customizer = Customizer(
        dry_run=args.dry_run,
        assume_yes=args.yes,
        skip_keyd=args.skip_keyd,
    )
    try:
        return customizer.apply()
    except KeyboardInterrupt:
        print("\n! Customization interrupted")
        return 130
    except CustomizationError as error:
        print(f"! {error}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
