import pathlib
import unittest


REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
CLI_MAIN = REPO_ROOT / "crates" / "openfang-cli" / "src" / "main.rs"


class CliSkillNewEntryPathTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = CLI_MAIN.read_text()

    def test_entry_path_variable_matches_runtime_split(self):
        self.assertIn(
            'let entry_path = if runtime == "python" {\n        "src/main.py"\n    } else {\n        "src/index.js"\n    };',
            self.source,
        )

    def test_manifest_uses_runtime_specific_entry_path(self):
        self.assertIn(
            '[runtime]\ntype = "{runtime}"\nentry = "{entry_path}"',
            self.source,
            "skill new manifest should interpolate the runtime-specific entry_path",
        )

    def test_no_hard_coded_python_entry_remains_in_manifest_template(self):
        self.assertNotIn('entry = "src/main.py"\n\n[[tools.provided]]', self.source)


if __name__ == "__main__":
    unittest.main()
