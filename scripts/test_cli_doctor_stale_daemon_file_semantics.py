#!/usr/bin/env python3
import pathlib
import tempfile
import unittest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
MAIN_RS = REPO_ROOT / "crates/openfang-cli/src/main.rs"


class CliDoctorStaleDaemonFileSemanticsTests(unittest.TestCase):
    def test_stale_daemon_check_requires_regular_file_metadata(self):
        text = MAIN_RS.read_text()
        self.assertIn('let daemon_json_path = openfang_dir.join("daemon.json");', text)
        self.assertIn('if let Ok(meta) = std::fs::metadata(&daemon_json_path) {', text)
        self.assertIn('if meta.is_file() {', text)
        self.assertIn('"daemon.json exists but is not a regular file; remove or replace it before retrying doctor --repair."', text)
        self.assertIn('stale_daemon_status = "fail";', text)
        self.assertIn('match std::fs::remove_file(&daemon_json_path)', text)
        self.assertNotIn('let _ = std::fs::remove_file(&daemon_json_path);', text)

    def test_directory_placeholder_is_not_a_regular_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            daemon_path = pathlib.Path(tmp) / 'daemon.json'
            daemon_path.mkdir()
            meta = daemon_path.stat()
            self.assertTrue(daemon_path.exists())
            self.assertTrue(daemon_path.is_dir())
            self.assertFalse(daemon_path.is_file())
            self.assertTrue(meta.st_mode)


if __name__ == '__main__':
    unittest.main()
