#!/usr/bin/env python3
import pathlib
import tempfile
import unittest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
MAIN_RS = REPO_ROOT / "crates/openfang-cli/src/main.rs"


class CliWorkflowFileSemanticsTests(unittest.TestCase):
    def test_workflow_commands_share_regular_file_loader(self):
        text = MAIN_RS.read_text()
        self.assertIn("fn load_workflow_json_file(file: &PathBuf) -> serde_json::Value {", text)
        self.assertIn("let metadata = std::fs::metadata(file).unwrap_or_else(|e| {", text)
        self.assertIn("if !metadata.is_file() {", text)
        self.assertIn('eprintln!("Workflow file is not a regular file: {}", file.display());', text)
        self.assertIn("let json_body = load_workflow_json_file(&file);", text)
        self.assertEqual(text.count("let json_body = load_workflow_json_file(&file);"), 2)
        self.assertNotIn("if !file.exists() {", text)

    def test_directory_placeholder_is_not_a_regular_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            workflow_path = pathlib.Path(tmp) / "workflow.json"
            workflow_path.mkdir()
            meta = workflow_path.stat()
            self.assertTrue(workflow_path.exists())
            self.assertTrue(workflow_path.is_dir())
            self.assertFalse(workflow_path.is_file())
            self.assertTrue(meta.st_mode)


if __name__ == "__main__":
    unittest.main()
