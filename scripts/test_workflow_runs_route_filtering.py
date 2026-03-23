import pathlib
import unittest


REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
ROUTES_RS = REPO_ROOT / 'crates' / 'openfang-api' / 'src' / 'routes.rs'


def extract_function(source: str, name: str) -> str:
    marker = f'pub async fn {name}'
    start = source.index(marker)
    brace_start = source.index('{', start)
    depth = 0
    for idx in range(brace_start, len(source)):
        ch = source[idx]
        if ch == '{':
            depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0:
                return source[start : idx + 1]
    raise AssertionError(f'Could not extract function body for {name}')


class WorkflowRunsRouteFilteringTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = ROUTES_RS.read_text()
        cls.list_runs_fn = extract_function(cls.source, 'list_workflow_runs')

    def test_route_validates_workflow_id_path_parameter(self):
        self.assertIn('Path(id): Path<String>', self.list_runs_fn)
        self.assertIn('let workflow_id = WorkflowId(match id.parse() {', self.list_runs_fn)
        self.assertIn('StatusCode::BAD_REQUEST', self.list_runs_fn)
        self.assertIn('"Invalid workflow ID"', self.list_runs_fn)

    def test_route_returns_not_found_for_missing_workflow(self):
        self.assertIn(
            'if state.kernel.workflows.get_workflow(workflow_id).await.is_none() {',
            self.list_runs_fn,
        )
        self.assertIn('StatusCode::NOT_FOUND', self.list_runs_fn)
        self.assertIn('"Workflow not found"', self.list_runs_fn)

    def test_route_filters_runs_to_requested_workflow(self):
        self.assertIn('let runs = state.kernel.workflows.list_runs(None).await;', self.list_runs_fn)
        self.assertIn('.filter(|r| r.workflow_id == workflow_id)', self.list_runs_fn)
        self.assertLess(
            self.list_runs_fn.index('let runs = state.kernel.workflows.list_runs(None).await;'),
            self.list_runs_fn.index('.filter(|r| r.workflow_id == workflow_id)'),
            'workflow run filtering should happen when building the response list',
        )


if __name__ == '__main__':
    unittest.main()
