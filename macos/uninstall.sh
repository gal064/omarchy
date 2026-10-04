#!/bin/bash

# Undo macos/setup.sh: remove skhd and its config (restoring any skhdrc that
# setup.sh backed up) and return the Spaces settings to macOS defaults.

set -uo pipefail

SKHD_DIR="$HOME/.config/skhd"
BACKUP_SUFFIX=".pre-omarchy"

echo "Stopping skhd..."
skhd --uninstall-service 2>/dev/null
pkill -x skhd 2>/dev/null

echo "Uninstalling skhd..."
brew uninstall skhd
if brew untrust --help >/dev/null 2>&1; then
  brew untrust --formula koekeishiya/formulae/skhd
fi
brew untap koekeishiya/formulae

echo "Removing config..."
if [[ -e $SKHD_DIR/skhdrc$BACKUP_SUFFIX ]]; then
  mv "$SKHD_DIR/skhdrc$BACKUP_SUFFIX" "$SKHD_DIR/skhdrc"
  echo "✓ Restored previous skhdrc"
else
  rm -f "$SKHD_DIR/skhdrc"
fi
rmdir "$SKHD_DIR" 2>/dev/null

echo "Restoring Spaces settings to macOS defaults..."
for id in 118 119 120 121 122 123 124 125 126; do
  /usr/libexec/PlistBuddy -c "Delete :AppleSymbolicHotKeys:$id" \
    "$HOME/Library/Preferences/com.apple.symbolichotkeys.plist" 2>/dev/null
done
/System/Library/PrivateFrameworks/SystemAdministration.framework/Resources/activateSettings -u
defaults delete com.apple.dock workspaces-auto-swoosh 2>/dev/null
# mru-spaces is left off: the macOS default (on) reorders desktops by recent use.
killall Dock

echo "Done. Remove skhd from Privacy & Security > Accessibility if it is still listed."
