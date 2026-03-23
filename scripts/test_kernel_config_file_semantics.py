import pathlib
import unittest


REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
SOURCE = REPO_ROOT / "crates/openfang-kernel/src/config.rs"


class KernelConfigFileSemanticsTests(unittest.TestCase):
    def test_kernel_config_loader_requires_real_config_file(self):
        source = SOURCE.read_text()
        self.assertIn("if config_path.is_file() {", source)
        self.assertNotIn("if config_path.exists() {", source)

    def test_directory_placeholder_is_not_treated_as_config_file(self):
        workspace = REPO_ROOT / ".tmp_kernel_config_file_semantics"
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

        config_dir = workspace / "config.toml"
        workspace.mkdir(parents=True)
        config_dir.mkdir()

        self.assertTrue(config_dir.exists())
        self.assertFalse(config_dir.is_file())

        config_dir.rmdir()
        workspace.rmdir()


if __name__ == "__main__":
    unittest.main()
