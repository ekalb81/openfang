#!/usr/bin/env python3
"""Regression guard for agent identity file listing semantics."""

from pathlib import Path
import unittest

REPO_ROOT = Path(__file__).resolve().parents[1]
ROUTES_RS = REPO_ROOT / "crates/openfang-api/src/routes.rs"


class AgentIdentityFileListingSourceTest(unittest.TestCase):
    def test_list_endpoint_only_marks_real_files_as_existing(self) -> None:
        text = ROUTES_RS.read_text(encoding="utf-8")
        start = text.index("let mut files = Vec::new();")
        end = text.index("(StatusCode::OK, Json(serde_json::json!({ \"files\": files })))", start)
        block = text[start:end]

        self.assertIn("match std::fs::metadata(&path)", block)
        self.assertIn("Ok(metadata) if metadata.is_file() => (true, metadata.len())", block)
        self.assertNotIn("if path.exists()", block)


if __name__ == "__main__":
    unittest.main()
