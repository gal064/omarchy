# customize.py follow-ups for Omarchy 4 (v4.0.4)

Status: applied to the working tree (uncommitted); 41 tests pass. All decisions resolved.

## Approved

1. Keep removing `mise-bin`, and add cleanup for the fallout: delete the mise wrappers `install/user/mise.sh` writes into `~/.local/bin` (detected by their `mise use -g` / `exec mise x` body), then relink `claude` to the newest `~/.local/share/claude/versions/*` and `codex` to `~/.codex/packages/standalone/current/bin/codex` when those native installs exist; otherwise report the reinstall command. Extend the compatibility note: `omarchy-refresh-applications` recreates the wrappers, rerun the script if they reappear.
2. Drop the five `hl.unbind` lines for keys Omarchy 4 no longer binds by default: SUPER+E, SUPER+SHIFT+J, CTRL+SHIFT+C, CTRL+SHIFT+code:13, CTRL+SHIFT+code:12. Keep the `o.bind` lines for them (CTRL+SHIFT+C clipboard manager stays). Keep unbinding SUPER+SHIFT+E, which is still bound to HEY email.
3. Keep all DHH apps (omawrite, omacalc, omacut, ttfx, herdr, moonlight-qt); no additions to `REMOVE_PACKAGES`.

## Pending Gal's decision

- Opacity rule: change `o.window(".*", { opacity = "1 1" })` to `o.window({ tag = "default-opacity" }, { opacity = "1 1" })` (recommended; see explanation in chat).
- Git defaults step (`reset_git_config`): keep as a one-time v3 cleanup, or replace with explicit `git config --global` values.
- Readline `bind` lines and `alias open='xdg-open'` in the Bash fence: safe duplicates of Omarchy defaults; keep or drop.
- Web apps: keep every new default launcher (Discord, Google Contacts, Maps, Messages, WhatsApp, YouTube, Zoom); `REMOVE_WEBAPPS` unchanged.

## Rejected

- `omarchy_preinstalled_bindings = false` one-liner (would also disable WhatsApp and other bindings Gal uses).

## Reference

- Proposed diff for items 1, 2 and the opacity change was drafted and saved in the session scratchpad as `approved-changes.patch`; tests for it still need to be written.
- Merge `upstream/quattro` (522 commits ahead of master, tag v4.0.4) before finalizing.
