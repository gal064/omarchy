#!/usr/bin/env python3

"""
Post-install customization script for Omarchy (SIMPLIFIED VERSION)
This script removes unwanted applications and their configurations
and switches from Chromium to Google Chrome.

IMPORTANT: This version leverages Omarchy's browser abstraction layer
(omarchy-launch-browser/omarchy-launch-webapp) and follows best practices
by ONLY modifying user configs, preserving upgrade compatibility.
"""

import os
import re
import shutil
import subprocess
import sys
import json
from pathlib import Path

# Configuration variables
TERMINAL = "alacritty"  # Change this to your preferred terminal (e.g., "kitty", "wezterm", "foot")


def run_command(command, check=False, shell=True):
    """Run a shell command with error handling and show output in terminal"""
    try:
        # Always source bash functions, escape double quotes in command
        command_escaped = command.replace('"', r"\"")
        command = f'bash -c "source ~/.local/share/omarchy/default/bash/functions && {command_escaped}"'

        result = subprocess.run(command, shell=shell, check=check)
        return result.returncode == 0
    except subprocess.CalledProcessError:
        return False


def backup_file_before_edit(file_path):
    """Create a .original backup of a file before editing it"""
    file_path = Path(file_path)

    if not file_path.exists():
        print(f"- File {file_path} doesn't exist, no backup needed")
        return False

    backup_path = file_path.with_suffix(file_path.suffix + ".original")

    # Don't overwrite existing backup
    if backup_path.exists():
        print(f"- Backup {backup_path} already exists, skipping")
        return True

    try:
        shutil.copy2(file_path, backup_path)
        print(f"✓ Created backup: {backup_path}")
        return True
    except Exception as e:
        print(f"! Failed to create backup of {file_path}: {e}")
        return False


def add_fenced_content_to_file(
    file_path, content_lines, fence_label="OMARCHY CUSTOMIZATION"
):
    """Add content to file with clear fencing markers for easy reversal"""
    file_path = Path(file_path)

    # Use CSS comment syntax for .css files, otherwise use shell/config syntax
    if str(file_path).endswith('.css'):
        start_fence = f"/* === START {fence_label} === */"
        end_fence = f"/* === END {fence_label} === */"
    else:
        start_fence = f"# === START {fence_label} ==="
        end_fence = f"# === END {fence_label} ==="

    try:
        if file_path.exists():
            current_content = file_path.read_text()
        else:
            current_content = ""

        # Check if our fenced section already exists
        if start_fence in current_content and end_fence in current_content:
            print(f"- Fenced section '{fence_label}' already exists in {file_path}")
            return True

        # Create the fenced content
        fenced_content = f"\n{start_fence}\n"
        for line in content_lines:
            fenced_content += f"{line}\n"
        fenced_content += f"{end_fence}\n"

        # Append to file
        with open(file_path, "a") as f:
            f.write(fenced_content)

        print(f"✓ Added fenced content to {file_path}")
        return True

    except Exception as e:
        print(f"! Failed to add fenced content to {file_path}: {e}")
        return False


def parse_jsonc_to_json(jsonc_text):
    """Best-effort conversion of JSONC (comments, trailing commas) to valid JSON string"""
    # Remove block comments
    without_block = re.sub(r"/\*[\s\S]*?\*/", "", jsonc_text)
    # Remove line comments (naive, may affect comment-like content in strings)
    without_line = re.sub(r"(?m)//.*$", "", without_block)
    # Remove trailing commas before } or ]
    without_trailing_commas = re.sub(r",\s*([}\]])", r"\1", without_line)
    return without_trailing_commas


def remove_packages_individually(packages, action_description="packages"):
    """Remove packages individually so failure of one doesn't prevent removal of others"""
    print(f"Removing {action_description}...")

    removed_count = 0
    failed_packages = []

    for package in packages:
        success = run_command(f"yay -Rns --noconfirm {package}")
        if success:
            print(f"✓ {package} removed successfully")
            removed_count += 1
        else:
            print(f"- {package} not found or already removed")
            failed_packages.append(package)

    if removed_count > 0:
        print(f"✓ {removed_count} {action_description} removed successfully")

    if failed_packages:
        print(
            f"- {len(failed_packages)} {action_description} were not found or already removed: {', '.join(failed_packages)}"
        )

    return removed_count, failed_packages


def remove_packages():
    """Remove chromium and neovim packages, install Google Chrome"""
    print("Removing chromium and installing Google Chrome...")

    # Remove chromium
    success = run_command("yay -Rns --noconfirm chromium")
    if success:
        print("✓ Chromium removed successfully")
    else:
        print("! Chromium removal failed or was already removed")

    # Install Google Chrome
    success = run_command("yay -S --noconfirm --needed google-chrome")
    if success:
        print("✓ Google Chrome installed successfully")
    else:
        print("! Google Chrome installation failed")

    remove_packages_individually(
        ["nvim", "luarocks", "tree-sitter-cli"], "neovim and related packages"
    )

    print("Installing nano as replacement editor...")
    success = run_command("yay -S --noconfirm --needed nano")
    if success:
        print("✓ nano installed successfully")
    else:
        print("! nano installation failed")

    print("Installing bash-completion...")
    success = run_command("yay -S --noconfirm --needed bash-completion")
    if success:
        print("✓ bash-completion installed successfully")
    else:
        print("! bash-completion installation failed")

    print("Installing Joplin...")
    success = run_command("yay -S --noconfirm --needed joplin-appimage")
    if success:
        print("✓ Joplin installed successfully")
    else:
        print("! Joplin installation failed")

    print("Installing clipse clipboard manager...")
    success = run_command("yay -S --noconfirm --needed clipse")
    if success:
        print("✓ clipse installed successfully")
    else:
        print("! clipse installation failed")

    remove_packages_individually(
        [
            "mariadb-libs",
            "cargo",
            "clang",
            "llvm",
            # intentionally skip core runtime libs that are depended upon system-wide
            # "llvm-libs",
            "mise",
            "ruby",
            # "gcc",
            # "gcc-libs",
            "gcc14",
            "wl-clip-persist",
        ],
        "additional unwanted packages",
    )

    remove_packages_individually(
        [
            "zoom",
            "obsidian-bin",
            "signal-desktop",
            "dropbox-cli",
            "1password-beta",
            "1password-cli",
            "localsend-bin",
        ],
        "zoom, obsidian, signal, dropbox, 1password, and localsend",
    )


def manage_font_packages():
    """Manage font packages according to fork preferences"""
    print("Managing font packages...")

    # Remove unwanted CJK and extra fonts
    remove_packages_individually(
        ["noto-fonts-cjk", "noto-fonts-extra"], "unwanted font packages"
    )

    # Install ttf-liberation for Hebrew support
    print("Installing ttf-liberation for Hebrew support...")
    success = run_command("yay -S --noconfirm --needed ttf-liberation")
    if success:
        print("✓ ttf-liberation installed successfully")
    else:
        print("! ttf-liberation installation failed")


def remove_user_config_directories():
    """Remove user configuration directories for uninstalled applications"""
    print("Removing user configuration directories...")

    home = Path.home()

    # Remove neovim configurations
    nvim_dirs = [
        home / ".config/nvim",
        home / ".local/share/nvim",
        home / ".local/state/nvim",
        home / ".cache/nvim",
    ]

    for nvim_dir in nvim_dirs:
        if nvim_dir.exists():
            shutil.rmtree(nvim_dir)
            print(f"✓ Removed {nvim_dir}")

    # Remove 1Password configurations
    password_dirs = [
        home / ".config/1Password",
        home / ".local/share/1Password",
        home / ".cache/1Password",
        home / ".ssh/1Password",
    ]

    for password_dir in password_dirs:
        if password_dir.exists():
            shutil.rmtree(password_dir)
            print(f"✓ Removed {password_dir}")

    # Remove mise configurations
    mise_dirs = [
        home / ".config/mise",
        home / ".local/share/mise",
        home / ".cache/mise",
    ]

    for mise_dir in mise_dirs:
        if mise_dir.exists():
            shutil.rmtree(mise_dir)
            print(f"✓ Removed {mise_dir}")


def remove_system_asdcontrol():
    """Remove system-installed asdcontrol components (NOT internal Omarchy files)

    This removes the asdcontrol installation created by Omarchy's install/asdcontrol.sh,
    which differs from the official asdcontrol installation method.
    """
    print("Removing system asdcontrol components...")

    # Remove asdcontrol binary (installed by 'sudo make install')
    asdcontrol_bin = Path("/usr/local/bin/asdcontrol")
    if asdcontrol_bin.exists():
        success = run_command("sudo rm -f /usr/local/bin/asdcontrol")
        if success:
            print("✓ Removed asdcontrol binary")
        else:
            print("! Failed to remove asdcontrol binary")
    else:
        print("- asdcontrol binary not found")

    # Remove Omarchy's custom sudoers file (not part of official asdcontrol)
    # Official asdcontrol uses udev rules instead of sudoers for permissions
    try:
        sudoers_file = Path("/etc/sudoers.d/asdcontrol")
        if sudoers_file.exists():
            success = run_command("sudo rm -f /etc/sudoers.d/asdcontrol")
            if success:
                print("✓ Removed Omarchy's asdcontrol sudoers file")
            else:
                print("! Failed to remove asdcontrol sudoers file")
        else:
            print("- asdcontrol sudoers file not found")
    except PermissionError:
        # Can't check if file exists due to permissions, try to remove anyway
        print("- Cannot check asdcontrol sudoers file existence, attempting removal...")
        success = run_command("sudo rm -f /etc/sudoers.d/asdcontrol")
        if success:
            print("✓ Removed Omarchy's asdcontrol sudoers file (if it existed)")
        else:
            print("- asdcontrol sudoers file not found or removal failed")

    # Remove any udev rules that might have been created (official asdcontrol method)
    udev_rules = [
        "/etc/udev/rules.d/50-apple-xdr.rules",
        "/etc/udev/rules.d/50-apple-studio.rules",
    ]

    for rule_file in udev_rules:
        rule_path = Path(rule_file)
        if rule_path.exists():
            success = run_command(f"sudo rm -f {rule_file}")
            if success:
                print(f"✓ Removed udev rule: {rule_file}")
            else:
                print(f"! Failed to remove udev rule: {rule_file}")
        else:
            print(f"- udev rule not found: {rule_file}")

    # Reload udev rules if any were removed
    print("Reloading udev rules...")
    success = run_command("sudo udevadm control --reload-rules")
    if success:
        print("✓ Reloaded udev rules")
    else:
        print("! Failed to reload udev rules")


def manage_user_desktop_files():
    """Manage desktop files in user applications directory ONLY"""
    print("Managing .desktop files in user applications directory...")

    home = Path.home()
    user_apps = home / ".local/share/applications"

    # Ensure user applications directory exists
    user_apps.mkdir(parents=True, exist_ok=True)

    # Remove unwanted desktop files from user directory
    files_to_remove = [
        "nvim.desktop",
        "dropbox.desktop",
        "Zoom.desktop",
        "chromium.desktop",
        "obsidian.desktop",
        "signal-desktop.desktop",
        "1password.desktop",
        "1password-beta.desktop",
        "Google Photos.desktop",
    ]

    for filename in files_to_remove:
        file_path = user_apps / filename
        if file_path.exists():
            file_path.unlink()
            print(f"✓ Removed {filename}")






def create_nautilus_vscode_script():
    """Create Nautilus script for opening files in VS Code or Cursor"""
    print("Creating Nautilus script for VS Code/Cursor...")

    # Create nautilus scripts directory if it doesn't exist
    nautilus_scripts_dir = Path.home() / ".local/share/nautilus/scripts"
    nautilus_scripts_dir.mkdir(parents=True, exist_ok=True)

    script_content = """#!/bin/bash

# Nautilus script to open selected files/directories in VS Code or Cursor

# Check which editor command is available (prefer code over cursor)
EDITOR_CMD=""
if command -v code &> /dev/null; then
    EDITOR_CMD="code"
elif command -v cursor &> /dev/null; then
    EDITOR_CMD="cursor"
else
    zenity --error --text="Neither VS Code (code) nor Cursor (cursor) command found. Please make sure at least one is installed and accessible from the command line."
    exit 1
fi

# Get selected files from Nautilus
# Nautilus provides selected files through environment variables
IFS=$'\\n'
if [ -n "$NAUTILUS_SCRIPT_SELECTED_FILE_PATHS" ]; then
    # Use the file paths provided by Nautilus
    selected_files=($(echo "$NAUTILUS_SCRIPT_SELECTED_FILE_PATHS"))
elif [ -n "$NAUTILUS_SCRIPT_SELECTED_URIS" ]; then
    # Convert URIs to file paths if needed
    selected_files=()
    for uri in $(echo "$NAUTILUS_SCRIPT_SELECTED_URIS"); do
        # Remove file:// prefix and decode URI
        file_path=$(echo "$uri" | sed 's|^file://||' | python3 -c "import sys, urllib.parse; print(urllib.parse.unquote(sys.stdin.read().strip()))")
        selected_files+=("$file_path")
    done
else
    zenity --error --text="No files selected."
    exit 1
fi

# Open each selected file/directory in the available editor
for file in "${selected_files[@]}"; do
    if [ -e "$file" ]; then
        $EDITOR_CMD "$file" &
    fi
done

# Disown the background processes so they don't get killed when script exits
disown
"""

    script_path = nautilus_scripts_dir / "open-in-vscode"

    try:
        script_path.write_text(script_content)
        script_path.chmod(0o755)  # Make executable
        print("✓ Created Nautilus script for VS Code/Cursor")
    except Exception as e:
        print(f"! Failed to create Nautilus script: {e}")


def remove_webapps_from_user_space():
    """Remove web app shortcuts using repo helper"""
    print("Removing web app shortcuts from user directory...")

    webapps_to_remove = [
        "HEY",
        "Basecamp",
        "X",
        "x.com",
    ]

    for webapp_name in webapps_to_remove:
        success = run_command(f"~/.local/share/omarchy/bin/omarchy-webapp-remove '{webapp_name}'")
        if success:
            print(f"✓ Removed {webapp_name}")
        else:
            print(f"- {webapp_name} not found or already removed")


def create_webapps():
    """Create web apps using web2app"""
    print("Creating web apps...")

    webapps = [
        {
            "name": "Gmail",
            "url": "https://mail.google.com",
            "icon": "https://cdn.jsdelivr.net/gh/homarr-labs/dashboard-icons/png/gmail.png",
        },
        {
            "name": "Google Calendar",
            "url": "https://calendar.google.com",
            "icon": "https://cdn.jsdelivr.net/gh/homarr-labs/dashboard-icons/png/google-calendar.png",
        },
        {
            "name": "Google AI",
            "url": "https://aistudio.google.com/",
            "icon": "https://cdn.jsdelivr.net/gh/homarr-labs/dashboard-icons/png/google-gemini.png",
        },
    ]

    # Use repo helper which integrates with this setup
    for app in webapps:
        success = run_command(
            f'~/.local/share/omarchy/bin/omarchy-webapp-install "{app["name"]}" "{app["url"]}" "{app["icon"]}"'
        )
        if success:
            print(f"✓ Created {app['name']} web app")
        else:
            print(f"! Failed to create {app['name']} web app")


def customize_bash_config():
    """Add bash customizations to user's .bashrc with backup and fencing"""
    print("Adding bash customizations to ~/.bashrc...")

    home = Path.home()
    bashrc_path = home / ".bashrc"

    # Create backup before editing
    backup_file_before_edit(bashrc_path)

    customizations = [
        "unalias n r 2>/dev/null",
        'export EDITOR="nano"',
        'export SUDO_EDITOR="$EDITOR"',
        "alias e='nano'",
        # Add code function for cursor with Alacritty auto-close
        "code() {",
        "    /usr/bin/code \"$@\" &",
        "    if [[ \"$(ps -o comm= -p $PPID 2>/dev/null)\" == \"alacritty\" ]]; then",
        "        sleep 0.5",
        "        kill $PPID 2>/dev/null",
        "    fi",
        "}",
        "",
        "# Only set bind commands in interactive shells",
        "if [[ $- == *i* ]]; then",
        "    # First Tab lists all matches",
        "    bind 'set show-all-if-ambiguous on'",
        "",
        "    # Second Tab (after showing list) begins menu completion",
        "    bind '\"\\t\":menu-complete'",
        "    bind 'set menu-complete-display-prefix on'   # optional, shows common prefix while cycling",
        "fi",
        "",
        "# Enable bash-completion",
        "if [ -f /usr/share/bash-completion/bash_completion ]; then",
        "    source /usr/share/bash-completion/bash_completion",
        "fi",
        "alias c='claude'",
        "alias cy='claude --permission-mode bypassPermissions'",
    ]


    # Use fenced content addition
    success = add_fenced_content_to_file(
        bashrc_path, customizations, "BASH CUSTOMIZATIONS"
    )

    if success:
        print("✓ Bash customizations added with fencing")
    else:
        print("! Failed to add bash customizations")
    return success


def update_user_hypridle_config():
    """Update user hypridle configuration with backup and fencing"""
    print("Updating user hypridle configuration...")

    home = Path.home()
    hypridle_conf = home / ".config/hypr/hypridle.conf"

    if not hypridle_conf.exists():
        print("! ~/.config/hypr/hypridle.conf not found, skipping")
        return

    # Create backup before editing
    backup_file_before_edit(hypridle_conf)

    idle_customizations = [
        "listener {",
        "    timeout = 900",
        "    on-timeout = systemctl suspend",
        "}"
    ]

    # Use fenced content addition
    success = add_fenced_content_to_file(
        hypridle_conf, idle_customizations, "HYPRIDLE CUSTOMIZATIONS"
    )

    if success:
        print("✓ Hypridle customizations added with fencing")
    else:
        print("! Failed to add hypridle customizations")
    return success


def update_user_hyprland_config():
    """Update user hyprland configuration with backup and fencing"""
    print("Updating user hyprland configuration...")

    home = Path.home()
    hypr_dir = home / ".config/hypr"
    
    # Check if hyprland config directory exists
    if not hypr_dir.exists():
        print("! ~/.config/hypr/ directory not found, skipping")
        return False

    # Define configurations for each file
    config_files = {
        "bindings.conf": [
            "unbind = SUPER, O",
            "unbind = SUPER, G", 
            "unbind = SUPER, slash",
            "unbind = SUPER, N",
            "unbind = SUPER, X",
            "unbind = SUPER SHIFT, X",
            "unbind = SUPER, C",
            "unbind = SUPER, E",
            "unbind = CTRL, F1",
            "unbind = CTRL, F2",
            "unbind = SHIFT CTRL, F2",
            "unbind = SUPER, P",
            "bind = SUPER, P, exec, joplin-desktop",
            "unbind = SUPER, V",
            f"bind = CTRL SHIFT, C, exec, {TERMINAL} --class clipse -e clipse && hyprctl dispatch sendshortcut 'CTRL,V,'",
            "bind = SUPER, E, fullscreen, 1",
            "unbind = SUPER SHIFT, A",
            'bind = SUPER SHIFT, A, exec, omarchy-launch-webapp "https://aistudio.google.com/"',
            "bind = CTRL SHIFT, 4, exec, ~/.local/share/omarchy/bin/omarchy-cmd-screenshot",
            "bind = CTRL SHIFT, 3, exec, ~/.local/share/omarchy/bin/omarchy-cmd-screenrecord region audio",
            "bind = SUPER SHIFT, E, resizeactive, 67% 0",
        ],
        "envs.conf": [
            'env = CHROME_FLAGS,"--enable-features=UseOzonePlatform --ozone-platform=wayland --gtk-version=4"',
            'env = PLAYWRIGHT_CHROMIUM_ARGS,"--enable-features=UseOzonePlatform --ozone-platform=wayland"',
        ],
        "autostart.conf": [
            "exec-once = clipse -listen",
        ],
        "input.conf": [
            "input { \n  kb_layout = us,il \n  kb_options = grp:caps_toggle \n scroll_factor = 2.0 \n}",
        ],
    }
    
    # Window rules and misc settings go to main hyprland.conf
    hyprland_conf = hypr_dir / "hyprland.conf"
    main_config = [
        "windowrule = float, class:(clipse)",
        "windowrule = size 622 652, class:(clipse)",
        "windowrule = stayfocused, class:(clipse)",
        "windowrule = opacity 1 1, class:.*",
        "misc { \n  new_window_takes_over_fullscreen = 2 \n }\n",
    ]

    all_success = True

    # Update specific config files
    for config_file, customizations in config_files.items():
        config_path = hypr_dir / config_file
        
        # Create backup if file exists
        if config_path.exists():
            backup_file_before_edit(config_path)
        
        # Add customizations to file
        success = add_fenced_content_to_file(
            config_path, customizations, f"OMARCHY {config_file.upper()} CUSTOMIZATIONS"
        )
        
        if success:
            print(f"✓ {config_file} customizations added")
        else:
            print(f"! Failed to add {config_file} customizations")
            all_success = False

    # Update main hyprland.conf with window rules and misc settings
    if hyprland_conf.exists():
        backup_file_before_edit(hyprland_conf)
        
        success = add_fenced_content_to_file(
            hyprland_conf, main_config, "OMARCHY HYPRLAND CUSTOMIZATIONS"
        )
        
        if success:
            print("✓ Main hyprland.conf customizations added")
        else:
            print("! Failed to add main hyprland.conf customizations")
            all_success = False
    else:
        print("! ~/.config/hypr/hyprland.conf not found, skipping main config")
        all_success = False

    return all_success




def set_default_browser():
    """Set Google Chrome as the default browser"""
    print("Setting google-chrome.desktop as default browser...")

    if not shutil.which("xdg-settings"):
        print("! xdg-settings not found, skipping default browser setup")
        return

    commands = [
        # Prefer setting Chrome directly
        "xdg-settings set default-web-browser google-chrome.desktop",
        "xdg-mime default google-chrome.desktop x-scheme-handler/http",
        "xdg-mime default google-chrome.desktop x-scheme-handler/https",
    ]

    all_ok = True
    for command in commands:
        success = run_command(command)
        if success:
            print(f"✓ {command}")
        else:
            print(f"! Failed: {command}")
            all_ok = False
    return all_ok


def reset_git_config():
    """Reset git configuration changes made during installation"""
    print("Resetting git configuration...")

    # Unset the global git settings that were set during installation
    git_configs_to_unset = ["pull.rebase", "init.defaultBranch"]

    for config in git_configs_to_unset:
        success = run_command(f"git config --global --unset {config}")
        if success:
            print(f"✓ Unset git config {config}")
        else:
            print(f"- git config {config} was not set or already unset")


def update_desktop_database():
    """Update the desktop database"""
    print("Updating desktop database...")

    if not shutil.which("update-desktop-database"):
        print("! update-desktop-database not found, skipping")
        return

    home = Path.home()
    user_apps = home / ".local/share/applications"

    success = run_command(f"update-desktop-database {user_apps}")
    if success:
        print("✓ Desktop database updated")
        return True
    else:
        print("! Failed to update desktop database")
        return False


def customize_waybar():
    """Configure Waybar to display current keyboard language/layout with backup and fencing.

    Supports Omarchy's default JSONC config at ~/.config/waybar/config.jsonc.
    """
    print("Configuring Waybar language display...")

    home = Path.home()
    # Prefer JSONC file used by this repo; fallback to plain config if present
    waybar_config_jsonc = home / ".config/waybar/config.jsonc"
    waybar_config_plain = home / ".config/waybar/config"
    waybar_config = waybar_config_jsonc if waybar_config_jsonc.exists() else waybar_config_plain
    waybar_style = home / ".config/waybar/style.css"

    if not waybar_config.exists():
        print("! Waybar config file not found, skipping language display setup")
        return

    try:
        # Create backups before editing
        backup_file_before_edit(waybar_config)
        if waybar_style.exists():
            backup_file_before_edit(waybar_style)

        # Read config; parse JSONC if necessary
        content = waybar_config.read_text()
        if waybar_config.suffix == ".jsonc":
            parsed = parse_jsonc_to_json(content)
        else:
            parsed = content

        config_data = json.loads(parsed)

        # Check if hyprland/language module is already configured
        if "hyprland/language" in config_data:
            print("- Waybar language module already configured")
        else:
            # Add hyprland/language to modules-right if not already present
            if "modules-right" in config_data:
                if "hyprland/language" not in config_data["modules-right"]:
                    config_data["modules-right"].append("hyprland/language")
                    print("✓ Added hyprland/language to modules-right")
            else:
                # Create modules-right if it doesn't exist
                config_data["modules-right"] = ["hyprland/language"]
                print("✓ Created modules-right with hyprland/language")

            # Add the hyprland/language module configuration for Hebrew/English
            config_data["hyprland/language"] = {
                "format": "{}",
                "format-en": "EN",
                "format-he": "עב",
                "on-click": "hyprctl switchxkblayout at-translated-set-2-keyboard next",
                "tooltip": True,
                "tooltip-format": "Keyboard Layout: {}",
            }
            print("✓ Added hyprland/language module configuration")

            # Write the updated configuration back. Preserve .jsonc extension by
            # writing JSON with a header comment if file is .jsonc
            rendered_json = json.dumps(config_data, indent=2)
            if waybar_config.suffix == ".jsonc":
                config_with_comment = f"// OMARCHY CUSTOMIZATION: Added hyprland/language module\n{rendered_json}\n"
                waybar_config.write_text(config_with_comment)
            else:
                waybar_config.write_text(rendered_json)
            print("✓ Updated Waybar configuration file")

        # Add CSS styling for the language indicator using fencing
        if waybar_style.exists():
            style_css_lines = [
                "/* Language indicator styling */",
                "#language {",
                "    background-color: #2e3440;",
                "    color: #88c0d0;",
                "    border-radius: 3px;",
                "    padding: 0 8px;",
                "    margin: 0 2px;",
                "    font-weight: bold;",
                "}",
                "",
                "#language:hover {",
                "    background-color: #3b4252;",
                "    color: #eceff4;",
                "}",
            ]

            success = add_fenced_content_to_file(
                waybar_style, style_css_lines, "WAYBAR LANGUAGE STYLING"
            )
            if success:
                print("✓ Added CSS styling with fencing")
            else:
                print("! Failed to add CSS styling")
        else:
            print("! Waybar style.css not found, skipping CSS styling")

    except json.JSONDecodeError as e:
        print(f"! Could not parse Waybar config as JSON: {e}")
        return False
    except Exception as e:
        print(f"! Error configuring Waybar language display: {e}")
        return False
    return True


def configure_toshy_keyboard_layout():
    """Configure custom Toshy keyboard layout with Mac-style modifier mapping and backup"""
    print("Configuring custom Toshy keyboard layout...")

    home = Path.home()
    toshy_config = home / ".config/toshy/toshy_config.py"

    if not toshy_config.exists():
        print("! Toshy config file not found")
        return

    # Create backup before editing
    backup_file_before_edit(toshy_config)

    try:
        content = toshy_config.read_text()

        # Check if our custom configuration already exists
        if "OMARCHY CUSTOMIZATION: Override keyboard type" in content:
            print("- Custom keyboard layout already configured")
            return

        # 1. Add keyboard type override to disable built-in modmaps
        settings_marker = "cnfg.watch_shared_devices()     # Look for network KVM apps and watch logs (on server only)"
        if settings_marker in content:
            override_config = """
        # === START OMARCHY CUSTOMIZATION: Override keyboard type ===
        cnfg.override_kbtype = 'IBM'     # Use IBM type to avoid Windows/Mac/Chromebook built-in modmaps
        # === END OMARCHY CUSTOMIZATION: Override keyboard type ==="""

            content = content.replace(
                settings_marker, settings_marker + override_config
            )
            print("✓ Added keyboard type override with clear marking")

        # 2. Add custom modmaps to user_custom_modmaps slice
        start_marker = "###  SLICE_MARK_START: user_custom_modmaps  ###"
        end_marker = "###  SLICE_MARK_END: user_custom_modmaps  ###"

        custom_modmaps = """# === START OMARCHY CUSTOMIZATION: Custom modmaps ===
modmap("OMARCHY custom layout: Cmd→Ctrl, Ctrl→Alt, keep Super - GUI", {
    # Left-hand modifiers
    Key.LEFT_ALT:  Key.LEFT_CTRL,   # Alt (Cmd) → Ctrl
    Key.LEFT_CTRL: Key.LEFT_ALT,    # Ctrl      → Alt
    Key.LEFT_META: Key.LEFT_META,   # Win/Super stays Super

    # Right-hand modifiers (optional)
    Key.RIGHT_ALT:  Key.RIGHT_CTRL,
    Key.RIGHT_CTRL: Key.RIGHT_ALT,
    Key.RIGHT_META: Key.RIGHT_META,
}, when = lambda ctx:
    not matchProps(clas=termStr)(ctx)
)

modmap("OMARCHY custom layout: Terminals - preserve Ctrl/Alt, keep Super", {
    # In terminals: keep normal Ctrl/Alt behavior but preserve Super
    Key.LEFT_ALT:  Key.LEFT_ALT,    # Alt stays Alt
    Key.LEFT_CTRL: Key.LEFT_CTRL,   # Ctrl stays Ctrl  
    Key.LEFT_META: Key.LEFT_META,   # Win/Super stays Super

    # Right-hand modifiers
    Key.RIGHT_ALT:  Key.RIGHT_ALT,
    Key.RIGHT_CTRL: Key.RIGHT_CTRL,
    Key.RIGHT_META: Key.RIGHT_META,
}, when = lambda ctx:
    matchProps(clas=termStr)(ctx)
)
# === END OMARCHY CUSTOMIZATION: Custom modmaps ==="""

        if start_marker in content and end_marker in content:
            # Find the slice and insert the modmaps
            start_idx = content.find(start_marker) + len(start_marker)
            end_idx = content.find(end_marker)

            # Check if there's already content between the markers
            slice_content = content[start_idx:end_idx]
            if "modmap(" not in slice_content:
                # Insert our custom modmaps between the markers
                new_content = (
                    content[:start_idx]
                    + f"\n\n{custom_modmaps}\n\n"
                    + content[end_idx:]
                )
                content = new_content
                print("✓ Added custom keyboard layout to user_custom_modmaps slice")
            else:
                print("- Custom modmap already exists in user_custom_modmaps slice")
        else:
            print("! user_custom_modmaps slice not found in Toshy config")
            return

        # 3. Disable emacs-style Super key mappings that interfere with Hyprland
        emacs_mappings = [
            'C("Super-a"):               C("Home"),                      # Beginning of Line',
            'C("Super-e"):               C("End"),                       # End of Line',
            'C("Super-b"):               C("Left"),',
            'C("Super-f"):               C("Right"),',
            'C("Super-n"):               C("Down"),',
            'C("Super-p"):               C("Up"),',
            'C("Super-k"):              [C("Shift-End"), C("Backspace")],',
            'C("Super-d"):               C("Delete"),',
        ]

        for mapping in emacs_mappings:
            if mapping in content:
                content = content.replace(
                    f"    {mapping}",
                    f"    # {mapping}  # DISABLED by OMARCHY for Hyprland",
                )
        print("✓ Disabled emacs-style Super key mappings with clear marking")

        # Write the updated content
        toshy_config.write_text(content)
        print("✓ Updated Toshy configuration file")

        # Restart Toshy service to apply keyboard layout changes
        print("Restarting Toshy service to apply changes...")
        success = run_command("systemctl --user restart toshy-config.service")
        if success:
            print("✓ Restarted Toshy service")
        else:
            print("! Failed to restart Toshy service")

    except Exception as e:
        print(f"! Error configuring Toshy keyboard layout: {e}")


def configure_toshy_systemd():
    """Configure Toshy systemd service with proper environment variables"""
    print("Configuring Toshy systemd service...")

    home = Path.home()
    service_template = (
        home / ".config/toshy/systemd-user-service-units/toshy-config.service"
    )
    user_systemd_dir = home / ".config/systemd/user"
    service_dest = user_systemd_dir / "toshy-config.service"

    if not service_template.exists():
        print("! Toshy service template not found")
        return

    # Ensure user systemd directory exists
    user_systemd_dir.mkdir(parents=True, exist_ok=True)

    try:
        # Read the template service file
        content = service_template.read_text()

        # Add XDG_SESSION_TYPE=wayland if not already present
        if "Environment=XDG_SESSION_TYPE=wayland" not in content:
            content = content.replace(
                "Environment=TERM=xterm",
                "Environment=TERM=xterm\nEnvironment=XDG_SESSION_TYPE=wayland",
            )
            print("✓ Added XDG_SESSION_TYPE=wayland to service file")

        # Write the updated service file to user systemd directory
        service_dest.write_text(content)
        print("✓ Updated Toshy systemd service file")

        # Reload systemd and enable/start the service
        success = run_command("systemctl --user daemon-reload")
        if success:
            print("✓ Reloaded systemd daemon")

        success = run_command("systemctl --user enable toshy-config.service --now")
        if success:
            print("✓ Enabled and started Toshy service")
        else:
            print("! Failed to enable/start Toshy service")

    except Exception as e:
        print(f"! Error configuring Toshy systemd service: {e}")


def install_and_configure_keyd():
    """Install keyd and configure Mac-like keyboard behavior with backup"""
    print("Installing and configuring keyd...")

    # Check if keyd config already exists and create backup
    keyd_config_path = Path("/etc/keyd/default.conf")
    if keyd_config_path.exists():
        print("✓ Found existing keyd configuration")
        # Create backup by copying to .original
        backup_path = Path("/etc/keyd/default.conf.original")
        if not backup_path.exists():
            success = run_command(
                "sudo cp /etc/keyd/default.conf /etc/keyd/default.conf.original"
            )
            if success:
                print("✓ Created backup: /etc/keyd/default.conf.original")
            else:
                print("! Failed to create backup")
        else:
            print("- Backup already exists: /etc/keyd/default.conf.original")

        print("⚠️  WARNING: Will overwrite existing keyd configuration!")
        response = (
            input("Do you want to continue and overwrite it? (y/N): ").strip().lower()
        )
        if response != "y" and response != "yes":
            print("Skipping keyd configuration.")
            return

    # Install keyd
    print("Installing keyd...")
    success = run_command("yay -S --noconfirm --needed keyd")

    if success:
        print("✓ keyd installed successfully")
    else:
        print("! keyd installation failed")
        return

    # Enable and start keyd service
    print("Enabling and starting keyd service...")
    success = run_command("sudo systemctl enable --now keyd")
    if success:
        print("✓ keyd service enabled and started")
    else:
        print("! Failed to enable/start keyd service")

    # Create keyd configuration with clear fencing
    print("Creating keyd configuration...")
    keyd_config = """# === START OMARCHY CUSTOMIZATION ===
# OMARCHY: Mac-like keyboard behavior configuration
# This file can be reverted by restoring from /etc/keyd/default.conf.original

# Apply to every keyboard
[ids]
*

# ----  MAIN LAYER  -------------------------------------------------
[main]
# Map physical Alt to a custom layer that acts like Control but with special arrow behavior
leftalt = layer(mac_control)
leftcontrol = layer(alt)
rightalt = layer(mac_control)  
rightcontrol = layer(alt)

# ----  MAC_CONTROL LAYER (acts like Control but with Mac-style arrows) ----
[mac_control:C]
left = home
right = end

# ----  ALT LAYER (physical Ctrl now acts as Alt) ----
[alt:A]
# Exception: preserve Ctrl+C for terminal interrupt
c = C-c

# === END OMARCHY CUSTOMIZATION ===
"""

    try:
        # Ensure /etc/keyd directory exists
        run_command("sudo mkdir -p /etc/keyd")

        # Write configuration to temporary file first
        temp_config = Path("/tmp/keyd_default.conf")
        temp_config.write_text(keyd_config)

        # Copy to /etc/keyd/default.conf
        success = run_command("sudo cp /tmp/keyd_default.conf /etc/keyd/default.conf")
        if success:
            print("✓ Created keyd configuration at /etc/keyd/default.conf")
        else:
            print("! Failed to create keyd configuration")
            return

        # Clean up temp file
        temp_config.unlink()

        # Reload keyd configuration
        print("Reloading keyd configuration...")
        success = run_command("sudo keyd reload")
        if success:
            print("✓ keyd configuration reloaded")
        else:
            print("! Failed to reload keyd configuration")

    except Exception as e:
        print(f"! Error creating keyd configuration: {e}")


def install_toshy():
    """Install Toshy keymapper for Mac-like keyboard behavior using official bootstrap"""
    print("Installing Toshy keymapper...")

    # Check if Toshy is already installed
    toshy_config_dir = Path.home() / ".config/toshy"
    if toshy_config_dir.exists():
        print(
            "- Toshy appears to be already installed, configuring systemd service and keyboard layout"
        )
        configure_toshy_systemd()
        configure_toshy_keyboard_layout()
        return

    # Check for required tools (curl or wget)
    if not shutil.which("curl") and not shutil.which("wget"):
        print("! Neither curl nor wget found, skipping Toshy installation")
        return

    # Use official Toshy bootstrap installation
    print("Running Toshy bootstrap installation...")
    bootstrap_cmd = 'bash -c "$(curl -L https://raw.githubusercontent.com/RedBearAK/toshy/main/scripts/bootstrap.sh || wget -O - https://raw.githubusercontent.com/RedBearAK/toshy/main/scripts/bootstrap.sh)"'

    success = run_command(bootstrap_cmd)
    if success:
        print("✓ Toshy installed successfully")
        # Configure systemd service and keyboard layout after installation
        configure_toshy_systemd()
        configure_toshy_keyboard_layout()
    else:
        print("! Toshy installation failed")


def main():
    """Main customization function"""
    print("Starting Omarchy customization...")
    print("=" * 50)
    print("NOTE: This script follows Omarchy best practices by ONLY modifying")
    print("user configuration files, preserving upgrade compatibility.")
    print("=" * 50)

    # Check for yay at the beginning - required for package management
    if not shutil.which("yay"):
        print("! ERROR: yay package manager not found")
        print("! yay is required for package installation and removal")
        print("! Please install yay first: https://github.com/Jguer/yay")
        sys.exit(1)

    try:
        remove_packages()
        print()


        manage_font_packages()
        print()

        # install_toshy()  # Commented out - using keyd instead
        install_and_configure_keyd()
        print()

        remove_user_config_directories()
        print()

        remove_system_asdcontrol()
        print()

        manage_user_desktop_files()
        print()


        create_nautilus_vscode_script()
        print()

        remove_webapps_from_user_space()
        print()

        create_webapps()
        print()

        bash_ok = customize_bash_config()
        print()

        hyprland_ok = update_user_hyprland_config()
        print()

        # update_user_hypridle_config()  # Commented out - user prefers original hypridle config
        # print()

        reset_git_config()
        print()

        default_browser_ok = set_default_browser()
        print()

        desktop_db_ok = update_desktop_database()
        print()

        waybar_ok = customize_waybar()
        print()

        print("Restarting Waybar...")
        run_command("killall waybar")
        run_command("waybar &>/dev/null &")
        print("✓ Waybar restarted")
        print()

        print("=" * 50)
        print("✓ Customization complete!")
        print("✓ Removed dev/editor/misc apps where present (neovim, dropbox, Zoom, Obsidian, Signal, 1Password, LocalSend)")
        print("✓ Switched from Chromium to Google Chrome")
        print("✓ Updated font packages (removed CJK/extra fonts, added Hebrew support)")
        print("✓ keyd setup step executed (install or reuse existing configuration)")
        if hyprland_ok:
            print("✓ Set Chrome environment variables and window rules in Hyprland")
        if bash_ok:
            print("✓ Added Bash improvements and completion")
        print("✓ Disabled Apple display brightness controls")
        print("✓ Reset git configuration")
        print("✓ Installed Joplin and set Super+P keybinding")
        print("✓ Installed clipse clipboard manager and set Super+V keybinding")
        if waybar_ok:
            print("✓ Configured Waybar language display for Hebrew/English layouts")
        print("✓ Created Nautilus script for opening files in VS Code/Cursor")
        if default_browser_ok:
            print("✓ Set default browser handlers to google-chrome.desktop")
        if desktop_db_ok:
            print("✓ Updated desktop database")
        print("✓ All changes made to USER configuration files only")
        print("✓ Internal Omarchy files preserved for upgrade compatibility")

    except KeyboardInterrupt:
        print("\n! Customization interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n! Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
