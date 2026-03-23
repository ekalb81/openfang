import pathlib
import unittest


REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
SOURCE = REPO_ROOT / "crates/openfang-runtime/src/workspace_context.rs"


class WorkspaceStateFileSemanticsTests(unittest.TestCase):
    def test_workspace_state_loader_requires_real_file(self):
        source = SOURCE.read_text()
        self.assertIn("let metadata = match std::fs::metadata(&path)", source)
        self.assertIn("if !metadata.is_file() {", source)

    def test_directory_placeholder_is_not_treated_as_workspace_state_file(self):
        workspace = REPO_ROOT / ".tmp_workspace_state_file_semantics"
        if workspace.exists():
            if workspace.is_dir():
                for child in sorted(workspace.rglob('*'), reverse=True):
                    if child.is_file() or child.is_symlink():
                        child.unlink()
                    elif child.is_dir():
                        child.rmdir()
                workspace.rmdir()
            else:
                workspace.unlink()

        state_dir = workspace / ".openfang" / "workspace-state.json"
        state_dir.mkdir(parents=True)

        self.assertTrue(state_dir.exists())
        self.assertFalse(state_dir.is_file())

        state_dir.rmdir()
        (workspace / ".openfang").rmdir()
        workspace.rmdir()


if __name__ == "__main__":
    unittest.main()
