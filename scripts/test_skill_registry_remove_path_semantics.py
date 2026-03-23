import pathlib
import tempfile
import unittest


REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
REGISTRY_RS = REPO_ROOT / "crates/openfang-skills/src/registry.rs"


class SkillRegistryRemovePathSemanticsTest(unittest.TestCase):
    def setUp(self):
        self.source = REGISTRY_RS.read_text()

    def test_remove_requires_directory_metadata(self):
        self.assertIn("match std::fs::metadata(&skill.path)", self.source)
        self.assertIn("installed skill path is not a directory", self.source)
        self.assertNotIn("if skill.path.exists() {\n            std::fs::remove_dir_all(&skill.path)?;\n        }", self.source)

    def test_non_directory_placeholder_demo(self):
        with tempfile.TemporaryDirectory() as td:
            skill_path = pathlib.Path(td) / "removable"
            skill_path.write_text("not a directory")
            self.assertTrue(skill_path.exists())
            self.assertTrue(skill_path.is_file())
            self.assertFalse(skill_path.is_dir())


if __name__ == "__main__":
    unittest.main()
