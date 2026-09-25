import json
import tempfile
import unittest
from pathlib import Path
from subprocess import CompletedProcess
from unittest.mock import patch

import restore


class RestoreTest(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.home = Path(self.tempdir.name)

    def tearDown(self):
        self.tempdir.cleanup()

    def test_restores_known_file_from_original_backup(self):
        path = self.home / ".config/hypr/input.lua"
        path.parent.mkdir(parents=True)
        path.write_text("customized\n")
        path.with_name("input.lua.quattro-original").write_text("original\n")

        self.assertTrue(
            restore.restore_user_file(self.home, ".config/hypr/input.lua", False)
        )
        self.assertEqual(path.read_text(), "original\n")

    def test_restores_default_editor_state(self):
        path = self.home / ".local/state/omarchy/defaults/editor"
        path.parent.mkdir(parents=True)
        path.write_text("nano\n")
        backup = path.with_name("editor.quattro-original")
        applied = path.with_name("editor.quattro-applied")
        backup.write_text("nvim\n")
        applied.write_text("nano\n")

        self.assertTrue(
            restore.restore_user_file(
                self.home, ".local/state/omarchy/defaults/editor", False
            )
        )
        self.assertEqual(path.read_text(), "nvim\n")
        self.assertFalse(backup.exists())
        self.assertFalse(applied.exists())

    def test_direct_restore_refuses_to_overwrite_newer_user_edits(self):
        path = self.home / ".config/alacritty/alacritty.toml"
        path.parent.mkdir(parents=True)
        path.write_text("customized = true\nuser_edit = true\n")
        backup = path.with_name("alacritty.toml.quattro-original")
        applied = path.with_name("alacritty.toml.quattro-applied")
        backup.write_text("original = true\n")
        applied.write_text("customized = true\n")

        self.assertFalse(
            restore.restore_user_file(
                self.home, ".config/alacritty/alacritty.toml", False
            )
        )
        self.assertEqual(path.read_text(), "customized = true\nuser_edit = true\n")
        self.assertTrue(backup.exists())
        self.assertTrue(applied.exists())

    def test_removes_default_editor_state_created_by_customizer(self):
        path = self.home / ".local/state/omarchy/defaults/editor"
        path.parent.mkdir(parents=True)
        path.write_text("nano\n")
        path.with_name("editor.quattro-original").write_text(
            restore.ABSENT_BACKUP_SENTINEL
        )

        self.assertTrue(
            restore.restore_user_file(
                self.home, ".local/state/omarchy/defaults/editor", False
            )
        )
        self.assertFalse(path.exists())

    def test_main_reports_keyd_restore_failure(self):
        with (
            patch("restore.os.geteuid", return_value=1000),
            patch("restore.Path.home", return_value=self.home),
            patch("restore.restore_keyd", return_value=False),
        ):
            self.assertEqual(restore.main([]), 1)

    def test_keyd_restore_refuses_to_overwrite_newer_config(self):
        path = self.home / "etc/keyd/default.conf"
        path.parent.mkdir(parents=True)
        path.write_text("newer user config\n")
        path.with_name("default.conf.quattro-original").write_text("original\n")
        path.with_name("default.conf.quattro-applied").write_text("applied\n")

        with patch(
            "restore.subprocess.run", return_value=CompletedProcess([], 1)
        ) as run:
            self.assertFalse(restore.restore_keyd(False, path))

        self.assertEqual(run.call_args.args[0][:3], ("sudo", "cmp", "-s"))

    def test_restores_quarantined_application_data(self):
        path = self.home / ".config/nvim"
        quarantine = path.with_name("nvim.quattro-removed")
        quarantine.mkdir(parents=True)
        (quarantine / "init.lua").write_text("-- keep\n")

        self.assertTrue(
            restore.restore_quarantined_target(self.home, ".config/nvim", False)
        )
        self.assertEqual((path / "init.lua").read_text(), "-- keep\n")
        self.assertFalse(quarantine.exists())

    def test_quarantined_restore_refuses_to_overwrite_new_data(self):
        path = self.home / ".config/nvim"
        quarantine = path.with_name("nvim.quattro-removed")
        path.mkdir(parents=True)
        quarantine.mkdir()

        self.assertFalse(
            restore.restore_quarantined_target(self.home, ".config/nvim", False)
        )
        self.assertTrue(path.exists())
        self.assertTrue(quarantine.exists())

    def test_main_rejects_running_as_root(self):
        with patch("restore.os.geteuid", return_value=0):
            self.assertEqual(restore.main([]), 1)

    def test_removes_owned_fence_when_file_has_no_backup(self):
        path = self.home / ".config/hypr/bindings.lua"
        path.parent.mkdir(parents=True)
        path.write_text(
            "-- keep\n"
            "-- === START OMARCHY BINDING CUSTOMIZATIONS ===\n"
            'o.bind("X", "Y", "z")\n'
            "-- === END OMARCHY BINDING CUSTOMIZATIONS ===\n"
        )

        self.assertTrue(
            restore.restore_user_file(self.home, ".config/hypr/bindings.lua", False)
        )
        self.assertEqual(path.read_text(), "-- keep\n")

    def test_fenced_restore_preserves_edits_made_after_customization(self):
        path = self.home / ".config/hypr/input.lua"
        path.parent.mkdir(parents=True)
        path.write_text(
            "-- original\n"
            "-- === START OMARCHY INPUT CUSTOMIZATIONS ===\n"
            "hl.config({ input = { kb_layout = 'us,il' } })\n"
            "-- === END OMARCHY INPUT CUSTOMIZATIONS ===\n"
            "-- edit added later\n"
        )
        path.with_name("input.lua.quattro-original").write_text("-- original\n")

        self.assertTrue(
            restore.restore_user_file(self.home, ".config/hypr/input.lua", False)
        )
        self.assertEqual(path.read_text(), "-- original\n-- edit added later\n")

    def test_removes_customization_created_env_file(self):
        path = self.home / ".config/uwsm/env.d/99-gal-customizations"
        path.parent.mkdir(parents=True)
        path.write_text(
            "# === START PLAYWRIGHT WAYLAND CUSTOMIZATION ===\n"
            "export EXAMPLE=1\n"
            "# === END PLAYWRIGHT WAYLAND CUSTOMIZATION ===\n"
        )

        self.assertTrue(
            restore.restore_user_file(
                self.home, ".config/uwsm/env.d/99-gal-customizations", False
            )
        )
        self.assertFalse(path.exists())

    def test_removes_owned_nautilus_script_without_backup(self):
        path = self.home / ".local/share/nautilus/scripts/open-in-vscode"
        path.parent.mkdir(parents=True)
        path.write_text(f"#!/bin/bash\n{restore.NAUTILUS_MARKER}\n")

        self.assertTrue(
            restore.restore_user_file(
                self.home, ".local/share/nautilus/scripts/open-in-vscode", False
            )
        )
        self.assertFalse(path.exists())

    def test_handy_paste_script_and_bindings_are_removed(self):
        script = self.home / ".local/bin/handy-wayland-paste"
        script.parent.mkdir(parents=True)
        script.write_text(f"#!/bin/bash\n{restore.NAUTILUS_MARKER}\n")
        bindings = self.home / ".config/hypr/bindings.lua"
        bindings.parent.mkdir(parents=True)
        bindings.write_text(
            "-- mine\n-- === START HANDY DICTATION ===\nx()\n-- === END HANDY DICTATION ===\n"
        )

        restore.restore_user_file(self.home, ".local/bin/handy-wayland-paste", False)
        restore.restore_user_file(self.home, ".config/hypr/bindings.lua", False)

        self.assertFalse(script.exists())
        self.assertEqual(bindings.read_text(), "-- mine\n")

    def test_handy_paste_method_is_restored_only_while_handy_is_stopped(self):
        path = self.home / restore.HANDY_SETTINGS
        path.parent.mkdir(parents=True)
        script = str(self.home / ".local/bin/handy-wayland-paste")
        path.write_text(
            json.dumps(
                {"settings": {"paste_method": "external_script", "external_script_path": script}}
            )
        )

        with patch("restore.handy_is_running", return_value=True):
            self.assertFalse(restore.restore_handy_paste_method(self.home, False))
        with patch("restore.handy_is_running", return_value=False):
            self.assertTrue(restore.restore_handy_paste_method(self.home, False))
            self.assertIsNone(restore.restore_handy_paste_method(self.home, False))

        settings = json.loads(path.read_text())["settings"]
        self.assertEqual(settings["paste_method"], "direct")
        self.assertIsNone(settings["external_script_path"])

    def test_unrelated_original_file_is_not_in_restore_allowlist(self):
        unrelated = self.home / ".config/example.conf.original"
        unrelated.parent.mkdir(parents=True)
        unrelated.write_text("do not restore\n")

        for relative in restore.USER_TARGETS:
            restore.restore_user_file(self.home, relative, False)

        self.assertTrue(unrelated.exists())
        self.assertFalse((self.home / ".config/example.conf").exists())


if __name__ == "__main__":
    unittest.main()
