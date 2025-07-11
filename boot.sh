#!/usr/bin/env bash
set -euo pipefail

ascii_art=' ▄██████▄    ▄▄▄▄███▄▄▄▄      ▄████████    ▄████████  ▄████████    ▄█    █▄    ▄██   ▄  
███    ███ ▄██▀▀▀███▀▀▀██▄   ███    ███   ███    ███ ███    ███   ███    ███   ███   ██▄
███    ███ ███   ███   ███   ███    ███   ███    ███ ███    █▀    ███    ███   ███▄▄▄███
███    ███ ███   ███   ███   ███    ███  ▄███▄▄▄▄██▀ ███         ▄███▄▄▄▄███▄▄ ▀▀▀▀▀▀███
███    ███ ███   ███   ███ ▀███████████ ▀▀███▀▀▀▀▀   ███        ▀▀███▀▀▀▀███▀  ▄██   ███
███    ███ ███   ███   ███   ███    ███ ▀███████████ ███    █▄    ███    ███   ███   ███
███    ███ ███   ███   ███   ███    ███   ███    ███ ███    ███   ███    ███   ███   ███
 ▀██████▀   ▀█   ███   █▀    ███    █▀    ███    ███ ████████▀    ███    █▀     ▀█████▀ 
                                          ███    ███                                    '

echo -e "\n$ascii_art\n"

# ensure git is installed
if ! command -v git &>/dev/null; then
  echo "Installing git…"
  sudo pacman -Sy --noconfirm --needed git
fi

echo -e "\nCloning Omarchy from your fork…"
rm -rf ~/.local/share/omarchy/
git clone https://github.com/gal064/omarchy.git ~/.local/share/omarchy >/dev/null 2>&1

# if you set OMARCHY_REF, use that branch/tag instead of master
if [[ -n "${OMARCHY_REF:-}" ]]; then
  echo -e "Using branch/tag: $OMARCHY_REF"
  (
    cd ~/.local/share/omarchy
    git fetch origin "$OMARCHY_REF"
    git checkout "$OMARCHY_REF"
  )
fi

echo -e "\nStarting installation…"
# load and run the real installer script from your fork
source ~/.local/share/omarchy/install.sh
