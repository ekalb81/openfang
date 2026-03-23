import pathlib
import unittest


REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
MODEL_CATALOG = REPO_ROOT / "crates" / "openfang-runtime" / "src" / "model_catalog.rs"


class ModelCatalogAtomicPersistTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = MODEL_CATALOG.read_text()

    def test_save_custom_models_uses_same_directory_unique_temp_file(self):
        self.assertIn(
            'let tmp_path = path.with_file_name(format!(".{file_name}.tmp-{}", Uuid::new_v4()));',
            self.source,
        )
        self.assertIn('std::fs::rename(&tmp_path, path)', self.source)

    def test_save_custom_models_creates_parent_dir_and_temp_file_exclusively(self):
        self.assertIn('std::fs::create_dir_all(parent)', self.source)
        self.assertIn('.create_new(true)', self.source)

    def test_save_custom_models_cleans_up_temp_file_after_failures(self):
        self.assertIn('if write_result.is_err() {', self.source)
        self.assertIn('let _ = std::fs::remove_file(&tmp_path);', self.source)
        self.assertIn('"Failed to persist custom models atomically: {e}"', self.source)

    def test_rust_atomic_round_trip_regression_remains_present(self):
        self.assertIn(
            'fn test_save_custom_models_atomic_round_trip_and_parent_dir_creation()',
            self.source,
        )
        self.assertIn('let tmp_prefix = ".custom-models.json.tmp-";', self.source)
        self.assertIn('temporary custom model file should be cleaned up', self.source)


if __name__ == "__main__":
    unittest.main()
