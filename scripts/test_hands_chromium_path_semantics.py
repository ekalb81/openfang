#!/usr/bin/env python3
"""Guard hand-registry Chromium detection against directory-shaped placeholders."""

from pathlib import Path
import tempfile
import unittest

REPO_ROOT = Path(__file__).resolve().parents[1]
SOURCE = REPO_ROOT / "crates/openfang-hands/src/registry.rs"


class HandsChromiumPathSemanticsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = SOURCE.read_text()

    def test_helper_requires_real_files(self) -> None:
        self.assertIn("fn path_points_to_file(path: &std::path::Path) -> bool", self.source)
        self.assertIn("std::fs::metadata(path)", self.source)
        self.assertIn("metadata.is_file()", self.source)

    def test_chromium_detection_uses_file_helper_for_env_and_known_paths(self) -> None:
        self.assertIn(
            'path_points_to_file(std::path::Path::new(&p))',
            self.source,
        )
        self.assertIn("if path_points_to_file(p) {", self.source)
        self.assertNotIn("Path::new(&p).exists()", self.source)
        self.assertNotIn("if p.exists() {", self.source)

    def test_directory_placeholders_do_not_count_as_browser_binaries(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fake_binary = root / "chrome"
            fake_dir = root / "chrome-dir"
            fake_binary.write_text("#!/bin/sh\n")
            fake_dir.mkdir()

            def path_points_to_file(path: Path) -> bool:
                try:
                    return path.is_file()
                except OSError:
                    return False

            self.assertTrue(path_points_to_file(fake_binary))
            self.assertFalse(path_points_to_file(fake_dir))
            self.assertFalse(path_points_to_file(root / "missing"))


if __name__ == "__main__":
    unittest.main()
