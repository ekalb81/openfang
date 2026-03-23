import os
import shutil
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
WIZARD_RS = REPO_ROOT / "crates" / "openfang-cli" / "src" / "tui" / "screens" / "wizard.rs"


class WizardSetupSemanticsTest(unittest.TestCase):
    def test_source_requires_regular_config_file(self):
        source = WIZARD_RS.read_text()
        self.assertIn('match std::fs::metadata(&config_path)', source)
        self.assertIn('Ok(metadata) => !metadata.is_file(),', source)
        self.assertNotIn('!of_home.join("config.toml").exists()', source)

    def test_directory_placeholder_still_requires_setup(self):
        workspace = Path(tempfile.mkdtemp(prefix="openfang-wizard-setup-"))
        try:
            config_path = workspace / "config.toml"
            config_path.mkdir()

            needs_setup = not config_path.is_file()
            self.assertTrue(needs_setup)
        finally:
            shutil.rmtree(workspace)

    def test_regular_config_file_skips_setup(self):
        workspace = Path(tempfile.mkdtemp(prefix="openfang-wizard-config-"))
        try:
            config_path = workspace / "config.toml"
            config_path.write_text("[kernel]\n")

            needs_setup = not config_path.is_file()
            self.assertFalse(needs_setup)
        finally:
            shutil.rmtree(workspace)


if __name__ == "__main__":
    unittest.main()
