#!/bin/bash

# Close the focused window (Option+W / Option+Q) and stay on the workspace even
# if it was the last window there.
#
# Closing the focused window makes macOS focus another window, and AeroSpace
# follows it to that window's workspace. For the last window, first hand focus
# to AeroSpace itself (an app with no windows), then close the window. It is no
# longer focused, so macOS has nothing to move focus to and nothing jumps.

A=/opt/homebrew/bin/aerospace

if (( $($A list-windows --workspace focused --count) == 1 )); then
  window=$($A list-windows --focused --format '%{window-id}')
  open -a AeroSpace
  $A close --window-id "$window"
else
  $A close
fi

# The closed window may leave a phantom tile behind; clear it once macOS has dropped the window.
sleep 0.3
~/.config/aerospace/cleanup.sh
