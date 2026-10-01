#!/bin/bash

# Remove phantom windows: windows AeroSpace still tiles but macOS no longer has.
# They show up as empty/white holes in the layout (AeroSpace discussions #1582, #1979).
# Runs on every workspace change and after Option+W / Option+Q.

A=/opt/homebrew/bin/aerospace

# Ask AeroSpace first, then macOS, so a window opened in between is never seen as phantom.
tracked=$($A list-windows --monitor all --format '%{window-id}') || exit 0
existing=$(osascript -l JavaScript -e '
ObjC.import("CoreGraphics");
const list = ObjC.castRefToObject($.CGWindowListCopyWindowInfo($.kCGWindowListOptionAll, 0));
const ids = [];
for (let i = 0; i < list.count; i++) ids.push(list.objectAtIndex(i).objectForKey("kCGWindowNumber").intValue);
ids.join("\n");
') || exit 0
# Never act on an empty or failed lookup: every window would look like a phantom.
[[ -n $existing ]] || exit 0

for window in $(comm -23 <(sort <<<"$tracked") <(sort <<<"$existing")); do
  $A close --window-id "$window"
done
