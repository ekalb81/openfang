import pathlib
import unittest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
KERNEL_RS = REPO_ROOT / "crates/openfang-kernel/src/kernel.rs"


class KernelReloadConfigFileSemanticsTest(unittest.TestCase):
    def test_reload_config_requires_real_config_file(self):
        source = KERNEL_RS.read_text(encoding="utf-8")
        self.assertIn(
            'let new_config = if config_path.is_file() {',
            source,
            "reload_config should require config.toml to be a real file before loading",
        )
        self.assertNotIn(
            'let new_config = if config_path.exists() {',
            source,
            "reload_config should not treat directory placeholders as readable config files",
        )
        self.assertIn(
            'return Err("Config file not found".to_string());',
            source,
            "reload_config should keep the friendly missing-config error path",
        )


if __name__ == "__main__":
    unittest.main()
