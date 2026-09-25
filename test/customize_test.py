import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import tomllib

import customize


class RecordingCustomizer(customize.Customizer):
    def __init__(self, home: Path, root: Path | None = None):
        super().__init__(home=home, root=root or Path("/"), assume_yes=True)
        self.commands: list[tuple[str, ...]] = []

    def run(self, *command: str, quiet: bool = False) -> bool:
        del quiet
        self.commands.append(command)
        return True


class CustomizeTest(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        self.home = self.root / "home"
        self.home.mkdir()

    def tearDown(self):
        self.tempdir.cleanup()

    def test_fenced_lua_section_is_idempotent_and_upgradeable(self):
        path = self.home / ".config/hypr/input.lua"
        path.parent.mkdir(parents=True)
        path.write_text("-- existing\n")
        customizer = customize.Customizer(home=self.home)

        self.assertTrue(customizer.upsert_fenced(path, ("first = true",), "TEST"))
        self.assertTrue(customizer.upsert_fenced(path, ("second = true",), "TEST"))

        content = path.read_text()
        self.assertEqual(content.count("-- === START TEST ==="), 1)
        self.assertNotIn("first = true", content)
        self.assertIn("second = true", content)
        self.assertEqual(
            path.with_name("input.lua.quattro-original").read_text(), "-- existing\n"
        )

    def test_incomplete_fence_is_refused(self):
        path = self.home / ".bashrc"
        original = "# === START TEST ===\nbroken\n"
        path.write_text(original)

        self.assertFalse(
            customize.Customizer(home=self.home).upsert_fenced(
                path, ("replacement",), "TEST"
            )
        )
        self.assertEqual(path.read_text(), original)

    def test_hyprland_customizations_use_quattro_lua_and_shell_commands(self):
        customizer = customize.Customizer(home=self.home)
        customizer.customize_hyprland()

        bindings = (self.home / ".config/hypr/bindings.lua").read_text()
        input_config = (self.home / ".config/hypr/input.lua").read_text()
        looknfeel = (self.home / ".config/hypr/looknfeel.lua").read_text()

        self.assertIn("omarchy-shell shell toggle omarchy.clipboard", bindings)
        self.assertIn("omarchy-capture-screenshot", bindings)
        self.assertIn("omarchy-capture-screenrecording", bindings)
        for removed_binding in (
            "SUPER + SHIFT + G",
            "SUPER + SHIFT + O",
            "SUPER + SHIFT + SLASH",
            "SUPER + SHIFT + C",
            "SUPER + SHIFT + ALT + E",
            "SUPER + SHIFT + P",
            "SUPER + SHIFT + X",
            "SUPER + SHIFT + ALT + X",
        ):
            self.assertIn(f'hl.unbind("{removed_binding}")', bindings)
        # Omarchy 4 no longer binds these by default, so they are only bound.
        for unbound_key in (
            "SUPER + E",
            "SUPER + SHIFT + J",
            "CTRL + SHIFT + C",
            "CTRL + SHIFT + code:13",
            "CTRL + SHIFT + code:12",
        ):
            self.assertNotIn(f'hl.unbind("{unbound_key}")', bindings)
            self.assertIn(f'o.bind("{unbound_key}"', bindings)
        self.assertIn(
            'o.window({ tag = "default-opacity" }, { opacity = "1 1" })', looknfeel
        )
        self.assertNotIn('o.window(".*", { opacity', looknfeel)
        self.assertIn('kb_layout = "us,il"', input_config)
        self.assertIn("scroll_factor = 1.2", input_config)
        self.assertIn("on_focus_under_fullscreen = 2", looknfeel)
        self.assertFalse(
            (self.home / ".config/uwsm/env.d/99-gal-customizations").exists()
        )
        self.assertNotIn("bind =", bindings)
        generated = bindings + input_config + looknfeel
        self.assertNotIn("bindings.conf", generated)
        self.assertNotIn("input.conf", generated)
        self.assertNotIn("hyprland.conf", generated)
        for path in (
            self.home / ".config/hypr/bindings.lua",
            self.home / ".config/hypr/input.lua",
            self.home / ".config/hypr/looknfeel.lua",
        ):
            result = subprocess.run(
                ["luac", "-p", str(path)], check=False, capture_output=True, text=True
            )
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_chrome_uses_official_installer_before_removing_chromium(self):
        customizer = RecordingCustomizer(self.home)
        customizer.install_chrome()

        self.assertEqual(
            customizer.commands,
            [
                ("omarchy-install-browser", "chrome"),
                ("omarchy-default-browser", "chrome"),
                ("omarchy-pkg-drop", "chromium"),
            ],
        )

    def test_chrome_removes_only_the_legacy_owned_desktop_override(self):
        desktop = self.home / ".local/share/applications/google-chrome.desktop"
        desktop.parent.mkdir(parents=True)
        desktop.write_text(
            "Exec=/usr/bin/google-chrome-stable --ozone-platform=wayland "
            "--ozone-platform-hint=wayland "
            "--enable-features=TouchpadOverscrollHistoryNavigation %U\n"
        )

        customize.Customizer(home=self.home).remove_legacy_chrome_desktop_override()

        self.assertFalse(desktop.exists())
        self.assertTrue(
            desktop.with_name("google-chrome.desktop.quattro-original").exists()
        )

        desktop.write_text("Exec=/usr/bin/google-chrome-stable --custom-flag %U\n")
        customize.Customizer(home=self.home).remove_legacy_chrome_desktop_override()
        self.assertTrue(desktop.exists())

    def test_package_policy_removes_mise_but_keeps_selected_toolchains(self):
        customizer = RecordingCustomizer(self.home)
        customizer.manage_packages()
        flattened = {
            argument for command in customizer.commands for argument in command
        }

        self.assertNotIn("mise", flattened)
        self.assertIn(("omarchy-pkg-drop", "mise-bin"), customizer.commands)
        for retained in ("cargo", "clang", "llvm", "gcc14", "lua51"):
            self.assertNotIn(retained, flattened)
        self.assertNotIn("joplin-bin", flattened)
        self.assertIn("localsend", flattened)
        self.assertIn(("omarchy-pkg-add", "nano"), customizer.commands)
        self.assertIn(("omarchy-pkg-drop", "neovim"), customizer.commands)

    def write_mise_wrapper(self, name: str) -> Path:
        local_bin = self.home / ".local/bin"
        local_bin.mkdir(parents=True, exist_ok=True)
        path = local_bin / name
        path.write_text(
            "#!/bin/bash\n"
            "export MISE_MINIMUM_RELEASE_AGE=0\n"
            f'mise use -g --quiet "{name}" || exit 1\n'
            f'exec mise x "{name}" -- "{name}" "$@"\n'
        )
        path.chmod(0o755)
        return path

    def test_mise_wrappers_are_removed_and_natives_relinked(self):
        for name in ("claude", "codex", "gh"):
            self.write_mise_wrapper(name)
        script = self.home / ".local/bin/mine"
        script.write_text("#!/bin/bash\necho mine\n")
        versions = self.home / ".local/share/claude/versions"
        versions.mkdir(parents=True)
        (versions / "2.1.9").write_text("old")
        (versions / "2.1.282").write_text("new")
        codex = self.home / ".codex/packages/standalone/current/bin/codex"
        codex.parent.mkdir(parents=True)
        codex.write_text("codex")

        customizer = customize.Customizer(home=self.home)
        customizer.package_removals["mise-bin"] = True
        customizer.remove_mise_wrappers()

        self.assertFalse((self.home / ".local/bin/gh").exists())
        self.assertTrue(script.exists())
        claude = self.home / ".local/bin/claude"
        self.assertTrue(claude.is_symlink())
        self.assertEqual(claude.resolve(), (versions / "2.1.282").resolve())
        self.assertEqual(
            (self.home / ".local/bin/codex").resolve(), codex.resolve()
        )
        self.assertEqual(customizer.failures, [])

    def test_mise_wrappers_are_preserved_when_mise_stays_installed(self):
        wrapper = self.write_mise_wrapper("claude")

        customizer = customize.Customizer(home=self.home)
        customizer.package_removals["mise-bin"] = False
        customizer.remove_mise_wrappers()

        self.assertTrue(wrapper.exists())
        self.assertFalse(wrapper.is_symlink())

    def test_missing_native_install_is_reported_after_wrapper_removal(self):
        self.write_mise_wrapper("codex")

        customizer = customize.Customizer(home=self.home)
        customizer.package_removals["mise-bin"] = True
        customizer.remove_mise_wrappers()

        codex = self.home / ".local/bin/codex"
        self.assertFalse(codex.exists() or codex.is_symlink())
        self.assertIn("relink native codex", customizer.failures)

    def test_failed_nano_install_preserves_neovim(self):
        customizer = customize.Customizer(home=self.home)
        commands: list[tuple[str, ...]] = []

        def run(*command: str, quiet: bool = False) -> bool:
            del quiet
            commands.append(command)
            return command != ("omarchy-pkg-add", "nano")

        with patch.object(customizer, "run", side_effect=run):
            self.assertFalse(customizer.manage_packages())

        self.assertNotIn(("omarchy-pkg-drop", "nvim"), commands)
        self.assertNotIn(("omarchy-pkg-drop", "neovim"), commands)
        self.assertNotIn(("omarchy-pkg-drop", "omarchy-nvim"), commands)

    def test_user_data_is_preserved_when_package_removal_fails(self):
        nvim = self.home / ".config/nvim"
        one_password = self.home / ".config/1Password"
        nvim.mkdir(parents=True)
        one_password.mkdir(parents=True)
        customizer = customize.Customizer(home=self.home)
        customizer.package_removals = {
            "omarchy-nvim": True,
            "neovim": False,
            "nvim": True,
            "1password": True,
            "1password-beta": False,
            "1password-cli": True,
        }

        customizer.remove_user_config_directories()

        self.assertTrue(nvim.exists())
        self.assertTrue(one_password.exists())

    def test_user_data_is_removed_only_after_all_packages_are_removed(self):
        nvim = self.home / ".config/nvim"
        one_password = self.home / ".config/1Password"
        nvim.mkdir(parents=True)
        one_password.mkdir(parents=True)
        customizer = customize.Customizer(home=self.home)
        customizer.package_removals = {
            package: True
            for package in (
                "omarchy-nvim",
                "neovim",
                "nvim",
                "1password",
                "1password-beta",
                "1password-cli",
            )
        }

        customizer.remove_user_config_directories()

        self.assertFalse(nvim.exists())
        self.assertFalse(one_password.exists())
        self.assertTrue(nvim.with_name("nvim.quattro-removed").exists())
        self.assertTrue(one_password.with_name("1Password.quattro-removed").exists())

    def test_default_editor_state_uses_nano(self):
        customizer = RecordingCustomizer(self.home)
        customizer.configure_default_editor()

        editor_file = self.home / ".local/state/omarchy/defaults/editor"
        self.assertEqual(editor_file.read_text(), "nano\n")
        self.assertEqual(
            editor_file.with_name("editor.quattro-applied").read_text(), "nano\n"
        )
        self.assertIn(("omarchy-cmd-present", "nano"), customizer.commands)

    def test_absence_marker_becomes_real_backup_when_file_later_exists(self):
        editor_file = self.home / ".local/state/omarchy/defaults/editor"
        editor_file.parent.mkdir(parents=True)
        backup = editor_file.with_name("editor.quattro-original")
        backup.write_text(customize.ABSENT_BACKUP_SENTINEL)
        editor_file.write_text("code\n")

        RecordingCustomizer(self.home).configure_default_editor()

        self.assertEqual(backup.read_text(), "code\n")

    def test_handy_setup_is_idempotent_and_preserves_settings(self):
        settings_path = self.home / customize.HANDY_SETTINGS
        settings_path.parent.mkdir(parents=True)
        settings_path.write_text(
            '{"settings": {"auto_submit": true, "paste_method": "direct"}, "other": 1}'
        )
        customizer = RecordingCustomizer(self.home)

        customizer.configure_handy()
        first_commands = list(customizer.commands)
        customizer.commands.clear()
        customizer.configure_handy()

        script = self.home / customize.HANDY_PASTE_SCRIPT
        store = json.loads(settings_path.read_text())
        bindings = (self.home / ".config/hypr/bindings.lua").read_text()
        self.assertEqual(store["other"], 1)
        self.assertTrue(store["settings"]["auto_submit"])
        self.assertEqual(store["settings"]["paste_method"], "external_script")
        self.assertEqual(store["settings"]["external_script_path"], str(script))
        self.assertEqual(bindings.count("START HANDY DICTATION"), 1)
        self.assertEqual(bindings.count('"SUPER + D", "Handy dictation"'), 1)
        self.assertTrue(script.stat().st_mode & 0o111)
        self.assertEqual(
            subprocess.run(["bash", "-n", str(script)], check=False).returncode, 0
        )
        self.assertIn(("omarchy-cmd-present", "handy"), first_commands)
        self.assertIn(("setsid", "-f", "uwsm-app", "--", "handy"), first_commands)
        self.assertEqual(customizer.commands, [("omarchy-cmd-present", "handy")])
        self.assertTrue(
            settings_path.with_name("settings_store.json.quattro-original").exists()
        )

    def test_handy_setup_is_skipped_when_handy_is_not_installed(self):
        customizer = RecordingCustomizer(self.home)
        customizer.run = lambda *command, quiet=False: command[0] != "omarchy-cmd-present"

        customizer.configure_handy()

        self.assertEqual(customizer.failures, [])
        self.assertFalse((self.home / customize.HANDY_PASTE_SCRIPT).exists())
        self.assertFalse((self.home / ".config/hypr/bindings.lua").exists())
        self.assertFalse((self.home / customize.HANDY_SETTINGS).exists())

    def test_handy_settings_are_created_before_first_launch(self):
        customizer = RecordingCustomizer(self.home)
        customizer.configure_handy_paste_method(self.home / customize.HANDY_PASTE_SCRIPT)

        store = json.loads((self.home / customize.HANDY_SETTINGS).read_text())
        self.assertEqual(store["settings"]["paste_method"], "external_script")

    def test_webapps_are_managed_through_path_commands(self):
        customizer = RecordingCustomizer(self.home)
        customizer.manage_desktop_entries()

        command_names = [command[0] for command in customizer.commands]
        self.assertIn("omarchy-webapp-remove", command_names)
        self.assertIn("omarchy-webapp-install", command_names)
        self.assertTrue(
            all("/.local/share/omarchy/" not in name for name in command_names)
        )

    def test_generated_bash_is_syntactically_valid(self):
        bashrc = self.home / ".bashrc"
        bashrc.write_text("# existing\n")
        customizer = customize.Customizer(home=self.home)
        customizer.customize_bash()
        customizer.customize_ssh_ghostty_truecolor()

        result = subprocess.run(
            ["bash", "-n", str(bashrc)],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_keyd_config_is_valid(self):
        path = self.root / "keyd.conf"
        path.write_text(customize.KEYD_CONFIG)
        result = subprocess.run(
            ["keyd", "check", str(path)],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_terminal_customizations_cover_foot_and_ghostty(self):
        foot = self.home / ".config/foot/foot.ini"
        ghostty = self.home / ".config/ghostty/config"
        foot.parent.mkdir(parents=True)
        ghostty.parent.mkdir(parents=True)
        foot.write_text("[key-bindings]\nclipboard-paste=Shift+Insert\n")
        ghostty.write_text("font-size = 12\n")

        customizer = customize.Customizer(home=self.home)
        customizer.customize_terminal_paste()
        customizer.customize_ghostty_mac_keys()

        self.assertIn("clipboard-paste=Control+v", foot.read_text())
        self.assertIn("copy-on-select = clipboard", ghostty.read_text())
        self.assertIn("keybind = ctrl+t=new_tab", ghostty.read_text())

    def test_terminal_customizations_handle_minimal_valid_configs(self):
        alacritty = self.home / ".config/alacritty/alacritty.toml"
        foot = self.home / ".config/foot/foot.ini"
        alacritty.parent.mkdir(parents=True)
        foot.parent.mkdir(parents=True)
        alacritty.write_text("[keyboard]\n\n[selection]\nsave_to_clipboard = false\n")
        foot.write_text("[main]\nfont=monospace:size=10\n")

        customizer = RecordingCustomizer(self.home)
        customizer.customize_terminal_paste()

        parsed = tomllib.loads(alacritty.read_text())
        self.assertTrue(parsed["selection"]["save_to_clipboard"])
        self.assertEqual(parsed["keyboard"]["bindings"][0]["key"], "V")
        self.assertIn("[key-bindings]", foot.read_text())
        self.assertIn("clipboard-paste=Control+v", foot.read_text())

    def test_alacritty_handles_compact_dotted_and_inline_toml(self):
        samples = (
            "keyboard.bindings=[]\nselection.save_to_clipboard=false\n",
            'selection = { save_to_clipboard = false, semantic_escape_chars = "," }\n[keyboard]\nbindings=[]\n',
        )
        for index, sample in enumerate(samples):
            with self.subTest(index=index):
                home = self.root / f"alacritty-{index}"
                path = home / ".config/alacritty/alacritty.toml"
                path.parent.mkdir(parents=True)
                path.write_text(sample)

                customize.Customizer(home=home).customize_terminal_paste()

                parsed = tomllib.loads(path.read_text())
                self.assertTrue(parsed["selection"]["save_to_clipboard"])

    def test_preflight_rejects_non_quattro_install(self):
        customizer = customize.Customizer(home=self.home, root=self.root)
        with (
            patch("customize.shutil.which", return_value=None),
            self.assertRaises(customize.CustomizationError),
        ):
            customizer.require_quattro()

    def test_preflight_rejects_running_as_root(self):
        customizer = customize.Customizer(home=self.home)
        with (
            patch("customize.os.geteuid", return_value=0),
            self.assertRaises(customize.CustomizationError),
        ):
            customizer.require_quattro()

    def test_preflight_accepts_complete_quattro_install(self):
        omarchy_root = self.root / "usr/share/omarchy"
        (omarchy_root / "config/hypr").mkdir(parents=True)
        (omarchy_root / "shell").mkdir()
        (omarchy_root / "config/hypr/hyprland.lua").write_text("")
        (omarchy_root / "shell/shell.qml").write_text("")
        (self.home / ".config/hypr").mkdir(parents=True)
        (self.home / ".config/omarchy").mkdir(parents=True)
        (self.home / ".config/hypr/hyprland.lua").write_text("")
        (self.home / ".config/omarchy/shell.json").write_text("{}\n")
        customizer = customize.Customizer(home=self.home, root=self.root)

        with (
            patch("customize.shutil.which", return_value="/usr/bin/omarchy"),
            patch.object(customizer, "run", return_value=True),
        ):
            customizer.require_quattro()

    def test_preflight_rejects_pre_reboot_quattro_files_without_live_shell(self):
        omarchy_root = self.root / "usr/share/omarchy"
        (omarchy_root / "config/hypr").mkdir(parents=True)
        (omarchy_root / "shell").mkdir()
        (omarchy_root / "config/hypr/hyprland.lua").write_text("")
        (omarchy_root / "shell/shell.qml").write_text("")
        (self.home / ".config/hypr").mkdir(parents=True)
        (self.home / ".config/omarchy").mkdir(parents=True)
        (self.home / ".config/hypr/hyprland.lua").write_text("")
        (self.home / ".config/omarchy/shell.json").write_text("{}\n")
        customizer = customize.Customizer(home=self.home, root=self.root)

        with (
            patch("customize.shutil.which", return_value="/usr/bin/omarchy"),
            patch.object(customizer, "run", return_value=False),
            self.assertRaises(customize.CustomizationError),
        ):
            customizer.require_quattro()

    def test_sandboxed_apply_is_idempotent(self):
        omarchy_root = self.root / "usr/share/omarchy"
        (omarchy_root / "config/hypr").mkdir(parents=True)
        (omarchy_root / "shell").mkdir()
        (omarchy_root / "config/hypr/hyprland.lua").write_text("")
        (omarchy_root / "shell/shell.qml").write_text("")

        for directory in (
            ".config/hypr",
            ".config/omarchy",
            ".config/ghostty",
            ".config/foot",
            ".config/alacritty",
        ):
            (self.home / directory).mkdir(parents=True)
        (self.home / ".config/hypr/hyprland.lua").write_text("")
        (self.home / ".config/omarchy/shell.json").write_text("{}\n")
        (self.home / ".config/ghostty/config").write_text("font-size = 12\n")
        (self.home / ".config/foot/foot.ini").write_text(
            "[key-bindings]\nclipboard-paste=Shift+Insert\n"
        )
        (self.home / ".config/alacritty/alacritty.toml").write_text(
            "[keyboard]\nbindings = []\n\n[selection]\nsave_to_clipboard = false\n"
        )
        (self.home / ".bashrc").write_text("# base\n")

        customizer = RecordingCustomizer(self.home, self.root)
        customizer.skip_keyd = True
        with patch("customize.shutil.which", return_value="/usr/bin/omarchy"):
            self.assertEqual(customizer.apply(), 0)
            self.assertEqual(customizer.apply(), 0)

        bindings = (self.home / ".config/hypr/bindings.lua").read_text()
        bashrc = (self.home / ".bashrc").read_text()
        self.assertEqual(bindings.count("START OMARCHY BINDING CUSTOMIZATIONS"), 1)
        self.assertEqual(bindings.count("START HANDY DICTATION"), 1)
        self.assertEqual(bashrc.count("START BASH CUSTOMIZATIONS"), 1)
        self.assertEqual(
            subprocess.run(
                ["bash", "-n", str(self.home / ".bashrc")], check=False
            ).returncode,
            0,
        )
        tomllib.loads((self.home / ".config/alacritty/alacritty.toml").read_text())

    def test_source_does_not_reference_retired_integrations(self):
        source = Path(customize.__file__).read_text()
        retired = (
            "omarchy-launch-walker",
            "omarchy-cmd-screenshot",
            ".config/waybar",
            ".config/mako",
            ".config/hypr/hyprland.conf",
            "chrome-flags.conf",
            "source ~/.local/share/omarchy",
        )
        for reference in retired:
            self.assertNotIn(reference, source)


if __name__ == "__main__":
    unittest.main()
