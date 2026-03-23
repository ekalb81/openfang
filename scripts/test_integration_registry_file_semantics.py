import pathlib
import unittest


REGISTRY = pathlib.Path(__file__).resolve().parents[1] / "crates" / "openfang-extensions" / "src" / "registry.rs"


class IntegrationRegistryFileSemanticsTest(unittest.TestCase):
    def test_load_installed_requires_real_file(self):
        source = REGISTRY.read_text()
        self.assertIn(
            "if !self.integrations_path.is_file() {",
            source,
            "load_installed should ignore missing paths and non-file placeholders",
        )
        self.assertNotIn(
            "if !self.integrations_path.exists() {",
            source,
            "load_installed should not treat arbitrary existing paths as installed config files",
        )

    def test_rust_regression_covers_directory_placeholder(self):
        source = REGISTRY.read_text()
        self.assertIn(
            "fn registry_load_installed_ignores_directory_placeholder()",
            source,
            "registry.rs should keep a focused regression for directory-shaped placeholders",
        )
        self.assertIn(
            'std::fs::create_dir(dir.path().join("integrations.toml")).unwrap();',
            source,
            "the regression should exercise a directory placeholder at integrations.toml",
        )
        self.assertIn(
            "let count = reg.load_installed().unwrap();",
            source,
            "the regression should prove load_installed succeeds instead of erroring",
        )


if __name__ == '__main__':
    unittest.main()
