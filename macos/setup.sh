#!/bin/bash

# Omarchy-like keyboard workflow on macOS, using native Spaces:
# - Option+1..9 switches desktops (Mission Control shortcuts, no slide-to-app jumps)
# - skhd for app shortcuts (Option+Return terminal, Option+Shift+B browser, ...)
# Safe to re-run. A replaced skhdrc is backed up with a .pre-omarchy suffix.
# Undo with macos/uninstall.sh.

set -euo pipefail

MACOS_DIR="$(cd "$(dirname "$0")" && pwd)"
SKHD_DIR="$HOME/.config/skhd"
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

echo "Installing skhd..."
if ! command -v brew >/dev/null; then
  echo "Homebrew is required: https://brew.sh" >&2
  exit 1
fi

# Newer Homebrew refuses third-party formulae until they are trusted.
# Trust only this package, not the whole tap.
brew tap koekeishiya/formulae
if brew trust --help >/dev/null 2>&1; then
  brew trust --formula koekeishiya/formulae/skhd
fi
brew list --formula skhd >/dev/null 2>&1 || brew install koekeishiya/formulae/skhd

echo
echo "Installing skhd config..."
mkdir -p "$SKHD_DIR"
install_file "$MACOS_DIR/skhd/skhdrc" "$SKHD_DIR/skhdrc" 644

echo
echo "Setting Option+1..9 to switch desktops..."
# Mission Control "Switch to Desktop N" = symbolic hotkeys 118..126.
# Parameters: (no character, key code of N, Option modifier).
for pair in 118:18 119:19 120:20 121:21 122:23 123:22 124:26 125:28 126:25; do
  id=${pair%:*}
  key=${pair#*:}
  defaults write com.apple.symbolichotkeys AppleSymbolicHotKeys -dict-add "$id" \
    "<dict><key>enabled</key><true/><key>value</key><dict><key>type</key><string>standard</string><key>parameters</key><array><integer>65535</integer><integer>$key</integer><integer>524288</integer></array></dict></dict>"
done
/System/Library/PrivateFrameworks/SystemAdministration.framework/Resources/activateSettings -u

echo "Stopping apps from pulling you to the desktop where they already have a window..."
defaults write com.apple.dock workspaces-auto-swoosh -bool false
echo "Keeping desktops in a fixed order..."
defaults write com.apple.dock mru-spaces -bool false
killall Dock

echo
echo "Starting skhd..."
if pgrep -x skhd >/dev/null; then
  skhd --restart-service
else
  skhd --start-service
fi

cat <<'EOF'

Done. Remaining manual steps:
- Allow skhd in System Settings > Privacy & Security > Accessibility
  (add /opt/homebrew/bin/skhd), then run: skhd --restart-service
- Create desktops 1-9: open Mission Control and click + until there are 9.
- Option+Return opens a terminal. If Ghostty binds it globally (e.g. the Quick
  Terminal), rebind it in ~/.config/ghostty/config, e.g.
    keybind = global:alt+grave_accent=toggle_quick_terminal
  then quit and reopen Ghostty.
- Optional: System Settings > Accessibility > Display > Reduce motion turns the
  desktop slide into a short fade.
EOF
