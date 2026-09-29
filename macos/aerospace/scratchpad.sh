#!/bin/bash
# Omarchy-style scratchpad: toggle between the current workspace and workspace S.
A=/opt/homebrew/bin/aerospace
if [ "$($A list-workspaces --focused)" = S ]; then
  $A workspace-back-and-forth
else
  $A workspace S
fi
