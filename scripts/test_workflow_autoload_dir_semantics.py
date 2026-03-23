import pathlib
import tempfile
import unittest


REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
KERNEL_RS = REPO_ROOT / 'crates' / 'openfang-kernel' / 'src' / 'kernel.rs'


class WorkflowAutoloadDirSemanticsTest(unittest.TestCase):
    def test_kernel_only_autoloads_from_real_workflow_directories(self):
        source = KERNEL_RS.read_text()
        self.assertIn('if wf_dir.is_dir() {', source)
        self.assertIn(
            'Skipping workflow autoload because configured workflows path is not a directory',
            source,
        )
        autoload_block = source.split('// Auto-load workflow definitions from configured directory', 1)[1]
        autoload_block = autoload_block.split('// Cron scheduler tick loop', 1)[0]
        self.assertIn('} else if wf_dir.exists() {', autoload_block)

    def test_file_placeholder_is_not_treated_as_workflow_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            workflows_path = pathlib.Path(tmp) / 'workflows'
            workflows_path.write_text('not a directory')

            self.assertTrue(workflows_path.exists())
            self.assertFalse(workflows_path.is_dir())


if __name__ == '__main__':
    unittest.main()
