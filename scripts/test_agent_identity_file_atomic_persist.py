import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
ROUTES_RS = REPO_ROOT / "crates" / "openfang-api" / "src" / "routes.rs"


class AgentIdentityFileAtomicPersistTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = ROUTES_RS.read_text()

    def test_set_agent_file_uses_same_directory_unique_temp_file(self):
        self.assertIn(
            'let tmp_path = file_path.with_file_name(format!(".{file_name}.tmp-{}", uuid::Uuid::new_v4()));',
            self.source,
        )

    def test_set_agent_file_cleans_up_temp_file_on_write_and_rename_failure(self):
        anchor = 'pub async fn set_agent_file('
        start = self.source.index(anchor)
        end = self.source.index('    let size_bytes = req.content.len();', start)
        body = self.source[start:end]

        self.assertIn('let _ = std::fs::remove_file(&tmp_path);', body)
        self.assertEqual(body.count('let _ = std::fs::remove_file(&tmp_path);'), 2)
        self.assertIn('Json(serde_json::json!({"error": format!("Write failed: {e}")})),', body)
        self.assertIn('Json(serde_json::json!({"error": format!("Rename failed: {e}")})),', body)


if __name__ == "__main__":
    unittest.main()
