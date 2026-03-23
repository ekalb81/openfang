from pathlib import Path
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
REGISTRY_RS = REPO_ROOT / 'crates' / 'openfang-extensions' / 'src' / 'registry.rs'


class IntegrationRegistryAtomicPersistTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = REGISTRY_RS.read_text()

    def test_save_installed_uses_same_directory_unique_temp_file(self):
        self.assertIn(
            '.with_file_name(format!(".{file_name}.tmp-{}", Uuid::new_v4()))',
            self.source,
        )
        self.assertIn(
            '"Failed to determine integrations registry file name"',
            self.source,
        )

    def test_save_installed_cleans_temp_file_on_failure(self):
        self.assertIn('let write_result = (|| -> ExtensionResult<()> {', self.source)
        self.assertIn('if write_result.is_err() {', self.source)
        self.assertIn('let _ = std::fs::remove_file(&tmp_path);', self.source)
        self.assertIn('write_result', self.source)

    def test_rust_regression_covers_atomic_cleanup_contract(self):
        self.assertIn(
            'fn registry_save_installed_uses_atomic_same_directory_temp_file()',
            self.source,
        )
        self.assertIn('.integrations.toml.tmp-', self.source)
        self.assertIn(
            'temporary integrations registry file should be cleaned up after save',
            self.source,
        )


if __name__ == '__main__':
    unittest.main()
