import pathlib
import unittest


MODEL_CATALOG = pathlib.Path(__file__).resolve().parents[1] / "crates" / "openfang-runtime" / "src" / "model_catalog.rs"


class ModelCatalogFileSemanticsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = MODEL_CATALOG.read_text()

    def test_regular_file_helper_guards_non_file_paths(self):
        self.assertIn("fn read_text_file_if_regular(path: &Path, context: &str) -> Option<String>", self.source)
        self.assertIn("std::fs::metadata(path)", self.source)
        self.assertIn("metadata.is_file()", self.source)
        self.assertIn('context = context', self.source)
        self.assertIn('"Expected regular file; ignoring non-file path"', self.source)

    def test_custom_model_load_uses_regular_file_helper(self):
        self.assertIn('let data = match read_text_file_if_regular(path, "custom models")', self.source)

    def test_credential_json_load_uses_regular_file_helper(self):
        self.assertIn('let content = read_text_file_if_regular(path, "credential JSON")?;', self.source)

    def test_directory_regressions_exist_for_custom_models_and_credentials(self):
        self.assertIn("fn test_load_custom_models_directory_path_preserves_existing_custom_models()", self.source)
        self.assertIn("fn test_read_json_file_returns_none_for_directory_path()", self.source)


if __name__ == "__main__":
    unittest.main()
