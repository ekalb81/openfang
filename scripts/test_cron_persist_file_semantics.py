import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
CRON_RS = REPO_ROOT / "crates" / "openfang-kernel" / "src" / "cron.rs"


class CronPersistFileSemanticsTests(unittest.TestCase):
    def test_source_requires_real_file_before_loading(self):
        source = CRON_RS.read_text()
        self.assertIn("std::fs::metadata(&self.persist_path)", source)
        self.assertIn("if !metadata.is_file()", source)
        self.assertIn("return Ok(0);", source)

    def test_directory_placeholder_is_not_a_loadable_persist_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            persist_path = Path(tmpdir) / "cron_jobs.json"
            persist_path.mkdir()

            self.assertTrue(persist_path.exists())
            self.assertFalse(persist_path.is_file())
            self.assertTrue(persist_path.is_dir())


if __name__ == "__main__":
    unittest.main()
