import pathlib
import unittest


REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
SOURCE = REPO_ROOT / "crates/openfang-runtime/src/workspace_context.rs"


class WorkspaceContextFileSemanticsTests(unittest.TestCase):
    def test_context_file_loader_requires_real_file(self):
        source = SOURCE.read_text()
        self.assertIn("if !meta.is_file() {", source)
        self.assertIn(
            '"Skipping workspace context entry because it is not a regular file"',
            source,
        )

    def test_directory_placeholder_is_not_treated_as_context_file(self):
        workspace = REPO_ROOT / ".tmp_workspace_context_file_semantics"
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

        context_dir = workspace / "SOUL.md"
        context_dir.mkdir(parents=True)

        self.assertTrue(context_dir.exists())
        self.assertFalse(context_dir.is_file())

        context_dir.rmdir()
        workspace.rmdir()


if __name__ == "__main__":
    unittest.main()
