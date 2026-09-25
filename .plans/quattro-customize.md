# Update `customize.py` for Omarchy Quattro

## Context

Omarchy Quattro replaces the legacy git-backed desktop shell and Hyprland `.conf` configuration with package-owned `/usr/share/omarchy` content, a Quickshell shell, and user-owned Lua/JSON overrides. The current customization script still targets Waybar, Walker, Mako, Hypridle, legacy command paths, and Hyprland `.conf` files. It also overwrites Chrome flags that Quattro now owns and removes Mise state that Quattro's agent tooling requires.

## Implementation

1. Refactor command execution to use Quattro commands from `PATH` without sourcing the legacy checkout.
2. Use Omarchy package/browser helpers (`omarchy-pkg-add`, `omarchy-pkg-drop`, `omarchy-install-browser`, `omarchy-default-browser`) and current package names.
3. Preserve the intended app/font cleanup, Chrome/Joplin/Nano setup, Bash aliases, Ghostty behavior, keyd mapping, web apps, and desktop cleanup.
4. Remove `mise-bin`, `luarocks`, and the selected editor/development packages as explicit user policy while preserving Mise state for recovery. Keep `lua51`, `cargo`, `clang`, `llvm`, and `gcc14`. Accept that Quattro's Mise-managed agent/tool wrappers require alternate installations, and stop deleting package-owned asdcontrol support.
5. Replace legacy Hyprland `.conf` edits with idempotent fenced Lua overrides in:
   - `~/.config/hypr/bindings.lua`
   - `~/.config/hypr/input.lua`
   - `~/.config/hypr/looknfeel.lua`
6. Let the official Chrome installer own browser flags/extensions. Drop the inert `PLAYWRIGHT_CHROMIUM_ARGS` environment variable because Playwright does not consume it; Wayland flags must be set in each project's `launchOptions.args`.
7. Remove Waybar, Mako, Walker, and Hypridle code. Use Quattro's built-in keyboard widget, clipboard shell plugin, capture commands, notification history, and shell restart/reload behavior. Quattro has no supported per-app notification-timeout rule or Apple-only brightness-disable switch, so report those two behavior changes rather than modifying package-owned internals.
8. Make fenced sections update in place so rerunning the script upgrades prior customizations instead of silently keeping stale content.
9. Update `restore.py` for the Quattro files, avoid restoring unrelated `.original` files, surgically remove owned fences so newer edits survive, record applied-state snapshots so stale direct-file/keyd rollback is refused, and quarantine excluded app data as recoverable `.quattro-removed` siblings instead of deleting it.
10. Add sandboxed Python tests for idempotency, generated Quattro config, command selection, and absence of retired integrations.

## Verification

- Compile both Python scripts without writing bytecode.
- Run the customization unit tests under `uv`.
- Run relevant Omarchy shell tests for Hyprland defaults, browser setup, keyboard layout, notifications, and web apps.
- Run `git diff --check` and independent subagent reviews.
- Do not run the real customization script on Gal's live machine; report commands requiring post-upgrade live verification.
