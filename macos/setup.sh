#!/bin/bash

# Set up an Omarchy-like tiling desktop on macOS with AeroSpace + borders.
# Safe to re-run. Files it replaces are backed up with a .pre-omarchy suffix.
# Undo with macos/uninstall.sh.

set -euo pipefail

MACOS_DIR="$(cd "$(dirname "$0")" && pwd)"
AEROSPACE_DIR="$HOME/.config/aerospace"
BACKUP_SUFFIX=".pre-omarchy"

install_file() {
  local source=$1 target=$2 mode=$3

  if [[ -e $target ]] && ! cmp -s "$source" "$target"; then
    if [[ ! -e $target$BACKUP_SUFFIX ]]; then
      cp -p "$target" "$target$BACKUP_SUFFIX"
      echo "- Backed up $target"
    fi
  fi

  install -m "$mode" "$source" "$target"
  echo "✓ Installed $target"
}

echo "Installing AeroSpace and borders..."
if ! command -v brew >/dev/null; then
  echo "Homebrew is required: https://brew.sh" >&2
  exit 1
fi

# Newer Homebrew refuses third-party formulae until they are trusted.
# Trust only these two packages, not their whole taps.
brew tap nikitabobko/tap
brew tap FelixKratz/formulae
if brew trust --help >/dev/null 2>&1; then
  brew trust --cask nikitabobko/tap/aerospace
  brew trust --formula felixkratz/formulae/borders
fi
brew list --cask aerospace >/dev/null 2>&1 || brew install --cask nikitabobko/tap/aerospace
brew list --formula borders >/dev/null 2>&1 || brew install felixkratz/formulae/borders

echo
echo "Installing AeroSpace config..."
mkdir -p "$AEROSPACE_DIR"
install_file "$MACOS_DIR/aerospace/aerospace.toml" "$AEROSPACE_DIR/aerospace.toml" 644
install_file "$MACOS_DIR/aerospace/scratchpad.sh" "$AEROSPACE_DIR/scratchpad.sh" 755
install_file "$MACOS_DIR/aerospace/close.sh" "$AEROSPACE_DIR/close.sh" 755

echo
echo "Recommended macOS setting: group windows by app in Mission Control..."
defaults write com.apple.dock expose-group-apps -bool true
killall Dock

echo
echo "Starting AeroSpace..."
if pgrep -x AeroSpace >/dev/null; then
  aerospace reload-config
else
  open -a AeroSpace
fi

cat <<'EOF'

Done. Remaining manual steps:
- Allow AeroSpace and borders in System Settings > Privacy & Security > Accessibility.
- Option+Return opens a terminal. If Ghostty binds it globally (e.g. the Quick
  Terminal), rebind it in ~/.config/ghostty/config, e.g.
    keybind = global:alt+grave_accent=toggle_quick_terminal
  then quit and reopen Ghostty.
- Optional: auto-hide the Dock in System Settings > Desktop & Dock.
EOF
