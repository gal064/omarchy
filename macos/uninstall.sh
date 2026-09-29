#!/bin/bash

# Undo macos/setup.sh: remove AeroSpace, borders, and their config, and restore
# any files setup.sh backed up. The expose-group-apps Dock setting is left as is.

set -uo pipefail

AEROSPACE_DIR="$HOME/.config/aerospace"
BACKUP_SUFFIX=".pre-omarchy"

echo "Stopping AeroSpace and borders..."
osascript -e 'quit app "AeroSpace"' 2>/dev/null
pkill -x AeroSpace 2>/dev/null
pkill -x borders 2>/dev/null

echo "Uninstalling packages..."
brew uninstall --cask aerospace
brew uninstall borders
if brew untrust --help >/dev/null 2>&1; then
  brew untrust --cask nikitabobko/tap/aerospace
  brew untrust --formula felixkratz/formulae/borders
fi
brew untap nikitabobko/tap
brew untap FelixKratz/formulae

echo "Removing config..."
for file in aerospace.toml scratchpad.sh; do
  if [[ -e $AEROSPACE_DIR/$file$BACKUP_SUFFIX ]]; then
    mv "$AEROSPACE_DIR/$file$BACKUP_SUFFIX" "$AEROSPACE_DIR/$file"
    echo "✓ Restored previous $file"
  else
    rm -f "$AEROSPACE_DIR/$file"
  fi
done
rmdir "$AEROSPACE_DIR" 2>/dev/null

echo "Removing AeroSpace preferences and Accessibility permission..."
defaults delete bobko.aerospace 2>/dev/null
tccutil reset Accessibility bobko.aerospace 2>/dev/null

echo "Done."
