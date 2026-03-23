import pathlib
import re
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


class WorkflowApiPersistenceHooksTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = ROUTES_RS.read_text()

    def test_create_workflow_persists_registered_definition(self):
        create_fn = extract_function(self.source, 'create_workflow')
        self.assertIn('let id = state.kernel.register_workflow(workflow.clone()).await;', create_fn)
        self.assertIn('persist_workflow_definition(&state, &workflow);', create_fn)
        self.assertLess(
            create_fn.index('let id = state.kernel.register_workflow(workflow.clone()).await;'),
            create_fn.index('persist_workflow_definition(&state, &workflow);'),
            'workflow persistence should happen after registration succeeds',
        )

    def test_update_workflow_persists_updated_definition_after_successful_in_memory_update(self):
        update_fn = extract_function(self.source, 'update_workflow')
        success_match = re.search(
            r'if\s+state\s*\.\s*kernel\s*\.\s*workflows\s*\.\s*update_workflow\(workflow_id,\s*updated\.clone\(\)\)\s*\.\s*await\s*\{(?P<body>.*?)\n\s*\}\s*else\s*\{',
            update_fn,
            re.S,
        )
        self.assertIsNotNone(success_match, 'expected update_workflow success branch')
        success_body = success_match.group('body')
        self.assertIn('persist_workflow_definition(&state, &updated);', success_body)

    def test_delete_workflow_removes_persisted_definition_after_successful_in_memory_delete(self):
        delete_fn = extract_function(self.source, 'delete_workflow')
        success_match = re.search(
            r'if\s+state\.kernel\.workflows\.remove_workflow\(workflow_id\)\.await\s*\{(?P<body>.*?)\n\s*\}\s*else\s*\{',
            delete_fn,
            re.S,
        )
        self.assertIsNotNone(success_match, 'expected delete_workflow success branch')
        success_body = success_match.group('body')
        self.assertIn('remove_workflow_definition(&state, workflow_id);', success_body)


if __name__ == '__main__':
    unittest.main()
