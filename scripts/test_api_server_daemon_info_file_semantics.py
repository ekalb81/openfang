#!/usr/bin/env python3
"""Regression guard for daemon info file semantics in API server startup."""

from pathlib import Path
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
SERVER_RS = REPO_ROOT / "crates/openfang-api/src/server.rs"


class DaemonInfoFileSemanticsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = SERVER_RS.read_text(encoding="utf-8")

    def test_existing_path_requires_real_file_before_stale_cleanup(self):
        self.assertIn("if info_path.is_file()", self.source)
        self.assertIn("else if info_path.exists()", self.source)
        self.assertIn("Daemon info path exists but is not a file", self.source)

    def test_stale_file_removal_and_write_failures_are_not_silent(self):
        self.assertIn("Failed to remove stale daemon info file {}: {e}", self.source)
        self.assertIn("Failed to write daemon info file {}: {e}", self.source)
        self.assertIn("std::fs::remove_file(info_path).map_err(|e|", self.source)
        self.assertIn("std::fs::write(info_path, json).map_err(|e|", self.source)


if __name__ == "__main__":
    unittest.main()
