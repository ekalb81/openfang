import pathlib
import re
import unittest


REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
CREDENTIALS_RS = REPO_ROOT / "crates" / "openfang-extensions" / "src" / "credentials.rs"


class CredentialsDotenvLoadObservabilityTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = CREDENTIALS_RS.read_text()

    def test_resolver_logs_dotenv_load_failures_before_fallback(self):
        self.assertRegex(
            self.source,
            re.compile(
                r"match load_dotenv\(path\) \{\s*Ok\(entries\) => entries,\s*Err\(error\) => \{\s*warn!\("
                r".*?Failed to load dotenv credentials; falling back to other credential sources",
                re.S,
            ),
        )

    def test_load_dotenv_requires_regular_file(self):
        self.assertIn("if !path.is_file() {", self.source)
        self.assertNotIn("if !path.exists() {", self.source)

    def test_in_file_rust_regressions_cover_directory_dotenv_paths(self):
        self.assertIn("fn load_dotenv_directory_treated_as_missing()", self.source)
        self.assertIn("fn resolver_directory_dotenv_path_falls_back_to_env()", self.source)


if __name__ == "__main__":
    unittest.main()
