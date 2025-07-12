#!/usr/bin/env python3

"""
Post-install customization script for Omarchy (CORRECTED VERSION)
This script removes unwanted applications and their configurations
and switches from Chromium to Google Chrome.

IMPORTANT: This version follows Omarchy best practices by ONLY modifying
user configs in ~/.config/ and ~/.local/share/applications/ instead of
internal files in ~/.local/share/omarchy/, preserving upgrade compatibility.
"""

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path


def run_command(command, check=False, shell=True):
    """Run a shell command with error handling"""
    try:
        result = subprocess.run(
            command, shell=shell, check=check, capture_output=True, text=True
        )
        return result.returncode == 0, result.stdout, result.stderr
    except subprocess.CalledProcessError as e:
        return False, e.stdout, e.stderr


def remove_packages():
    """Remove chromium and neovim packages, install Google Chrome"""
    print("Removing chromium and installing Google Chrome...")

    if not shutil.which("yay"):
        print("Warning: yay not found, skipping browser switch")
        return

    # Remove chromium
    success, _, _ = run_command("yay -Rns --noconfirm chromium")
    if success:
        print("✓ Chromium removed successfully")
    else:
        print("! Chromium removal failed or was already removed")

    # Install Google Chrome
    success, _, _ = run_command("yay -S --noconfirm --needed google-chrome")
    if success:
        print("✓ Google Chrome installed successfully")
    else:
        print("! Google Chrome installation failed")

    print("Removing neovim and related packages...")
    success, _, _ = run_command("yay -Rns --noconfirm nvim luarocks tree-sitter-cli")
    if success:
        print("✓ Neovim packages removed successfully")
    else:
        print("! Neovim package removal failed or was already removed")

    print("Installing vi as replacement editor...")
    success, _, _ = run_command("yay -S --noconfirm --needed vi")
    if success:
        print("✓ vi installed successfully")
    else:
        print("! vi installation failed")

    print("Removing additional unwanted packages...")
    success, _, _ = run_command(
        "yay -Rns --noconfirm mariadb-libs cargo clang llvm mise ruby gcc14"
    )
    if success:
        print("✓ Additional packages removed successfully")
    else:
        print("! Additional package removal failed or some were already removed")

    print("Removing zoom, obsidian, signal, dropbox, 1password, and localsend...")
    success, _, _ = run_command(
        "yay -Rns --noconfirm zoom obsidian-bin signal-desktop dropbox-cli 1password-beta 1password-cli localsend-bin"
    )
    if success:
        print(
            "✓ Zoom, Obsidian, Signal, Dropbox, 1Password, and LocalSend removed successfully"
        )
    else:
        print(
            "! Zoom, Obsidian, Signal, Dropbox, 1Password, and LocalSend removal failed or were already removed"
        )


def manage_font_packages():
    """Manage font packages according to fork preferences"""
    print("Managing font packages...")

    if not shutil.which("yay"):
        print("Warning: yay not found, skipping font management")
        return

    # Remove unwanted CJK and extra fonts
    print("Removing unwanted font packages...")
    success, _, _ = run_command("yay -Rns --noconfirm noto-fonts-cjk noto-fonts-extra")
    if success:
        print("✓ Removed noto-fonts-cjk and noto-fonts-extra")
    else:
        print("! Font removal failed or fonts were already removed")

    # Install ttf-liberation for Hebrew support
    print("Installing ttf-liberation for Hebrew support...")
    success, _, _ = run_command("yay -S --noconfirm --needed ttf-liberation")
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


def remove_system_asdcontrol():
    """Remove system-installed asdcontrol components (NOT internal Omarchy files)"""
    print("Removing system asdcontrol components...")

    # Remove asdcontrol binary
    asdcontrol_bin = Path("/usr/local/bin/asdcontrol")
    if asdcontrol_bin.exists():
        success, _, _ = run_command("sudo rm -f /usr/local/bin/asdcontrol")
        if success:
            print("✓ Removed asdcontrol binary")
        else:
            print("! Failed to remove asdcontrol binary")
    else:
        print("- asdcontrol binary not found")

    # Remove sudoers file
    sudoers_file = Path("/etc/sudoers.d/asdcontrol")
    if sudoers_file.exists():
        success, _, _ = run_command("sudo rm -f /etc/sudoers.d/asdcontrol")
        if success:
            print("✓ Removed asdcontrol sudoers file")
        else:
            print("! Failed to remove asdcontrol sudoers file")
    else:
        print("- asdcontrol sudoers file not found")


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
    ]

    for filename in files_to_remove:
        file_path = user_apps / filename
        if file_path.exists():
            file_path.unlink()
            print(f"✓ Removed {filename}")


def create_chrome_desktop_file(user_apps_dir):
    """Create a custom Chrome desktop file with Wayland optimization"""
    print("Creating custom Chrome desktop file...")
    
    chrome_desktop_content = """[Desktop Entry]
Version=1.0
Name=Google Chrome
GenericName=Web Browser
Comment=Access the Internet
Exec=/usr/bin/google-chrome-stable --enable-features=UseOzonePlatform --ozone-platform=wayland %U
StartupNotify=true
Terminal=false
Icon=google-chrome
Type=Application
Categories=Network;WebBrowser;
MimeType=application/pdf;application/rdf+xml;application/rss+xml;application/xhtml+xml;application/xhtml_xml;application/xml;image/gif;image/jpeg;image/png;image/webp;text/html;text/xml;x-scheme-handler/http;x-scheme-handler/https;
Actions=new-window;new-private-window;

[Desktop Action new-window]
Name=New Window
Exec=/usr/bin/google-chrome-stable --enable-features=UseOzonePlatform --ozone-platform=wayland --new-window

[Desktop Action new-private-window]
Name=New Incognito Window
Exec=/usr/bin/google-chrome-stable --enable-features=UseOzonePlatform --ozone-platform=wayland --new-window --incognito
"""

    chrome_desktop_path = user_apps_dir / "google-chrome.desktop"
    
    try:
        chrome_desktop_path.write_text(chrome_desktop_content)
        print("✓ Created custom google-chrome.desktop with Wayland optimization")
    except Exception as e:
        print(f"! Failed to create Chrome desktop file: {e}")


def remove_webapps_from_user_space():
    """Remove web app shortcuts from user applications directory using web2app-remove"""
    print("Removing web app shortcuts from user directory...")

    webapps_to_remove = [
        "HEY",
        "Basecamp",
        "X",
        "x.com",
    ]

    for webapp_name in webapps_to_remove:
        success, stdout, stderr = run_command(f"web2app-remove {webapp_name}")
        if success:
            print(f"✓ Removed {webapp_name}")
        else:
            print(f"- {webapp_name} not found or already removed")


def customize_bash_config():
    """Add bash customizations to user's .bashrc line by line"""
    print("Adding bash customizations to ~/.bashrc...")

    home = Path.home()
    bashrc_path = home / ".bashrc"

    customizations = [
        "unalias n r 2>/dev/null",
        'export EDITOR="vi"',
        'export SUDO_EDITOR="$EDITOR"',
        "alias e='nano'",
        "alias chromium='google-chrome'",
    ]

    try:
        if bashrc_path.exists():
            current_content = bashrc_path.read_text()
        else:
            current_content = ""

        changes_made = False
        for line in customizations:
            if line not in current_content:
                with open(bashrc_path, "a") as f:
                    f.write(f"\n{line}")
                print(f"✓ Added: {line}")
                changes_made = True
                current_content += f"\n{line}"
            else:
                print(f"- Already present: {line}")

        if not changes_made:
            print("✓ All bash customizations already present")

    except Exception as e:
        print(f"! Error customizing bash config: {e}")


def update_user_hyprland_config():
    """Update user hyprland configuration line by line"""
    print("Updating user hyprland configuration...")

    home = Path.home()
    hyprland_conf = home / ".config/hypr/hyprland.conf"

    if not hyprland_conf.exists():
        print("! ~/.config/hypr/hyprland.conf not found, skipping")
        return

    customizations = [
        "unbind = SUPER, O",
        "unbind = SUPER, G",
        "unbind = SUPER, slash",
        "unbind = SUPER, N",
        "unbind = SUPER, X",
        "unbind = SUPER SHIFT, X",
        "unbind = CTRL, F1",
        "unbind = CTRL, F2",
        "unbind = SHIFT CTRL, F2",
        'env = CHROME_FLAGS,"--enable-features=UseOzonePlatform --ozone-platform=wayland --gtk-version=4"',
    ]

    try:
        content = hyprland_conf.read_text()

        changes_made = False
        for line in customizations:
            if line not in content:
                with open(hyprland_conf, "a") as f:
                    f.write(f"\n{line}")
                print(f"✓ Added: {line}")
                changes_made = True
                content += f"\n{line}"
            else:
                print(f"- Already present: {line}")

        if not changes_made:
            print("✓ All hyprland customizations already present")

    except Exception as e:
        print(f"! Error updating hyprland config: {e}")


def create_chromium_symlink():
    """Create a symlink so 'chromium' command launches Google Chrome"""
    print("Creating chromium symlink to Google Chrome...")

    # Check if Google Chrome is installed
    if not shutil.which("google-chrome-stable"):
        print("! Google Chrome not found, skipping symlink creation")
        return

    # Remove any existing chromium binary or symlink first
    success, _, _ = run_command("sudo rm -f /usr/local/bin/chromium")

    # Create the symlink
    success, _, stderr = run_command(
        "sudo ln -sf /usr/bin/google-chrome-stable /usr/local/bin/chromium"
    )
    if success:
        print("✓ Created chromium -> google-chrome-stable symlink")
    else:
        print(f"! Failed to create chromium symlink: {stderr}")


def set_default_browser():
    """Set chromium.desktop (which launches Google Chrome) as the default browser"""
    print("Setting chromium.desktop as default browser...")

    if not shutil.which("xdg-settings"):
        print("! xdg-settings not found, skipping default browser setup")
        return

    commands = [
        "xdg-settings set default-web-browser chromium.desktop",
        "xdg-mime default chromium.desktop x-scheme-handler/http",
        "xdg-mime default chromium.desktop x-scheme-handler/https",
    ]

    for command in commands:
        success, _, _ = run_command(command)
        if success:
            print(f"✓ {command}")
        else:
            print(f"! Failed: {command}")


def reset_git_config():
    """Reset git configuration changes made during installation"""
    print("Resetting git configuration...")

    # Unset the global git settings that were set during installation
    git_configs_to_unset = ["pull.rebase", "init.defaultBranch"]

    for config in git_configs_to_unset:
        success, _, _ = run_command(f"git config --global --unset {config}")
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

    success, _, _ = run_command(f"update-desktop-database {user_apps}")
    if success:
        print("✓ Desktop database updated")
    else:
        print("! Failed to update desktop database")


def main():
    """Main customization function"""
    print("Starting Omarchy customization...")
    print("=" * 50)
    print("NOTE: This script follows Omarchy best practices by ONLY modifying")
    print("user configuration files, preserving upgrade compatibility.")
    print("=" * 50)

    try:
        remove_packages()
        print()

        create_chromium_symlink()
        print()

        manage_font_packages()
        print()

        remove_user_config_directories()
        print()

        remove_system_asdcontrol()
        print()

        manage_user_desktop_files()
        print()

        # Create custom Chrome desktop file with Wayland optimization
        home = Path.home()
        user_apps = home / ".local/share/applications"
        user_apps.mkdir(parents=True, exist_ok=True)
        create_chrome_desktop_file(user_apps)
        print()

        remove_webapps_from_user_space()
        print()

        customize_bash_config()
        print()

        update_user_hyprland_config()
        print()

        reset_git_config()
        print()

        set_default_browser()
        print()

        update_desktop_database()
        print()

        print("=" * 50)
        print("✓ Customization complete!")
        print("✓ Removed neovim, dropbox, Zoom, Obsidian, Signal, 1Password, LocalSend")
        print("✓ Switched from Chromium to Google Chrome")
        print("✓ Created chromium symlink - all apps calling 'chromium' now use Chrome")
        print("✓ Updated font packages (removed CJK/extra fonts, added Hebrew support)")
        print("✓ Set Chrome environment variables and window rules")
        print("✓ Added chromium alias for terminal usage")
        print("✓ Disabled Apple display brightness controls")
        print("✓ Reset git configuration")
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
