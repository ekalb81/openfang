import pathlib
import unittest


REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
ROUTES_RS = REPO_ROOT / 'crates' / 'openfang-api' / 'src' / 'routes.rs'


class WorkflowPersistHelperSemanticsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = ROUTES_RS.read_text()

    def test_workflows_dir_prefers_configured_path_then_home_default(self):
        self.assertIn('fn workflows_dir(state: &AppState) -> PathBuf {', self.source)
        self.assertIn('.workflows_dir', self.source)
        self.assertIn('.clone()', self.source)
        self.assertIn('unwrap_or_else(|| state.kernel.config.home_dir.join("workflows"))', self.source)

    def test_persist_helper_uses_atomic_writer_via_json_serializer(self):
        self.assertIn('fn persist_workflow_definition_to_path(', self.source)
        self.assertIn('let json = serde_json::to_string_pretty(workflow).map_err(std::io::Error::other)?;', self.source)
        self.assertIn('write_text_file_atomically(path, &json)', self.source)

    def test_persist_and_remove_helpers_share_resolved_workflows_dir_and_warn_selectively(self):
        self.assertIn('fn persist_workflow_definition(state: &AppState, workflow: &Workflow) {', self.source)
        self.assertIn('let wf_dir = workflows_dir(state);', self.source)
        self.assertIn('std::fs::create_dir_all(&wf_dir)', self.source)
        self.assertIn('Failed to create workflows directory', self.source)
        self.assertIn('let wf_path = wf_dir.join(format!("{}.json", workflow.id));', self.source)
        self.assertIn('persist_workflow_definition_to_path(&wf_path, workflow)', self.source)
        self.assertIn('Failed to persist workflow definition', self.source)
        self.assertIn('fn remove_workflow_definition(state: &AppState, workflow_id: WorkflowId) {', self.source)
        self.assertIn('let wf_path = workflows_dir(state).join(format!("{}.json", workflow_id));', self.source)
        self.assertIn('std::fs::remove_file(&wf_path)', self.source)
        self.assertIn('if e.kind() != std::io::ErrorKind::NotFound {', self.source)
        self.assertIn('Failed to remove persisted workflow definition', self.source)

    def test_in_file_rust_regressions_cover_atomic_write_and_cleanup_contract(self):
        self.assertIn(
            'fn test_persist_workflow_definition_to_path_writes_atomically_without_temp_leaks()',
            self.source,
        )
        self.assertIn(
            'fn test_persist_workflow_definition_to_path_cleans_up_temp_file_on_write_error()',
            self.source,
        )
        self.assertIn('.tmp-', self.source)


if __name__ == '__main__':
    unittest.main()
