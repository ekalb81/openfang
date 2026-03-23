from pathlib import Path
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
CRON_RS = REPO_ROOT / 'crates' / 'openfang-kernel' / 'src' / 'cron.rs'


class CronAtomicPersistCleanupTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = CRON_RS.read_text()

    def test_persist_uses_same_directory_unique_temp_file(self):
        self.assertIn(
            '.with_file_name(format!(".{file_name}.tmp-{}", uuid::Uuid::new_v4()))',
            self.source,
        )
        self.assertIn('Failed to determine cron persist file name', self.source)

    def test_persist_cleans_temp_file_on_failure(self):
        self.assertIn('let write_result = (|| -> OpenFangResult<()> {', self.source)
        self.assertIn('if write_result.is_err() {', self.source)
        self.assertIn('let _ = std::fs::remove_file(&tmp_path);', self.source)
        self.assertIn('write_result?;', self.source)

    def test_rust_regression_covers_temp_cleanup(self):
        self.assertIn('fn test_persist_write_failure_cleans_temp_file()', self.source)
        self.assertIn('Failed to write cron jobs temp file', self.source)
        self.assertIn('.cron_jobs.json.tmp-', self.source)
        self.assertIn('temporary cron persist file should be cleaned up after write failure', self.source)


if __name__ == '__main__':
    unittest.main()
