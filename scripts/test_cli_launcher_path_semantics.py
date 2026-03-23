import pathlib
import unittest


REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
SOURCE = REPO_ROOT / "crates/openfang-cli/src/launcher.rs"


class LauncherPathSemanticsTests(unittest.TestCase):
    def test_launcher_uses_real_file_for_first_run_config(self):
        source = SOURCE.read_text()
        self.assertIn('!of_home.join("config.toml").is_file()', source)
        self.assertNotIn('!of_home.join("config.toml").exists()', source)

    def test_launcher_requires_real_directory_for_openclaw_detection(self):
        source = SOURCE.read_text()
        self.assertIn('h.join(".openclaw").is_dir()', source)
        self.assertNotIn('h.join(".openclaw").exists()', source)

    def test_filesystem_semantics_match_launcher_expectations(self):
        workspace = REPO_ROOT / ".tmp_launcher_path_semantics"
        if workspace.exists():
            if workspace.is_dir():
                for child in sorted(workspace.rglob('*'), reverse=True):
                    if child.is_file() or child.is_symlink():
                        child.unlink()
                    elif child.is_dir():
                        child.rmdir()
                workspace.rmdir()
            else:
                workspace.unlink()

        openfang_home = workspace / ".openfang"
        openclaw_home = workspace / ".openclaw"
        openfang_home.mkdir(parents=True)
        openclaw_home.mkdir(parents=True)

        fake_config = openfang_home / "config.toml"
        fake_config.mkdir()
        self.assertTrue(fake_config.exists())
        self.assertFalse(fake_config.is_file())

        fake_openclaw_file = workspace / ".openclaw-file"
        fake_openclaw_file.write_text("placeholder")
        self.assertTrue(fake_openclaw_file.exists())
        self.assertFalse(fake_openclaw_file.is_dir())

        # Cleanup
        fake_config.rmdir()
        (openfang_home).rmdir()
        fake_openclaw_file.unlink()
        openclaw_home.rmdir()
        workspace.rmdir()


if __name__ == "__main__":
    unittest.main()
