#!/usr/bin/env python3
"""Regression guard for agent identity file read/write path semantics."""

from pathlib import Path
import unittest

REPO_ROOT = Path(__file__).resolve().parents[1]
ROUTES_RS = REPO_ROOT / "crates/openfang-api/src/routes.rs"


class AgentIdentityFilePathSemanticsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.text = ROUTES_RS.read_text(encoding="utf-8")

    def test_get_endpoint_requires_regular_file_metadata(self) -> None:
        start = self.text.index("pub async fn get_agent_file(")
        end = self.text.index("/// Request body for writing a workspace identity file.", start)
        block = self.text[start:end]

        self.assertIn("match std::fs::metadata(&canonical)", block)
        self.assertIn("Ok(metadata) if metadata.is_file() => {}", block)

    def test_set_endpoint_rejects_non_file_placeholders(self) -> None:
        start = self.text.index("pub async fn set_agent_file(")
        end = self.text.index("// ---------------------------------------------------------------------------\n// File Upload endpoints", start)
        block = self.text[start:end]

        self.assertIn("match std::fs::metadata(&file_path)", block)
        self.assertIn("Ok(metadata) if metadata.is_file() => file_path", block)
        self.assertIn('"Target path is not a regular file"', block)
        self.assertNotIn("if file_path.exists()", block)


if __name__ == "__main__":
    unittest.main()
