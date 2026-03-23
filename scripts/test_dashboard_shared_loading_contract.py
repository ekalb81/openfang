import pathlib
import re
import unittest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
INDEX_BODY = (REPO_ROOT / 'crates' / 'openfang-api' / 'static' / 'index_body.html').read_text()
PAGES_DIR = REPO_ROOT / 'crates' / 'openfang-api' / 'static' / 'js' / 'pages'

PAGE_CASES = [
    ('approvalsPage', 'approvals.js', 'loadData'),
    ('channelsPage', 'channels.js', 'loadChannels'),
    ('handsPage', 'hands.js', 'loadData'),
    ('logsPage', 'logs.js', 'fetchLogs'),
    ('overviewPage', 'overview.js', 'loadOverview'),
    ('schedulerPage', 'scheduler.js', 'loadData'),
    ('sessionsPage', 'sessions.js', 'loadSessions'),
    ('settingsPage', 'settings.js', 'loadSettings'),
    ('skillsPage', 'skills.js', 'loadSkills'),
    ('workflowsPage', 'workflows.js', 'loadWorkflows'),
]


class DashboardSharedLoadingContractTests(unittest.TestCase):
    def test_dashboard_routes_keep_loading_error_content_visibility_contract(self):
        for component_name, _, _ in PAGE_CASES:
            with self.subTest(component=component_name):
                route_block = self._route_block(component_name)
                self.assertIn('x-show="loading"', route_block)
                self.assertTrue(
                    'x-show="!loading && loadError"' in route_block
                    or 'x-show="!loading && error"' in route_block,
                    msg=f'{component_name} should render a non-loading error state',
                )
                self.assertTrue(
                    'x-show="!loading && !loadError"' in route_block
                    or 'x-if="!loading && !loadError"' in route_block
                    or 'x-show="!loading && !error"' in route_block,
                    msg=f'{component_name} should gate its content on loading/error completion',
                )

    def test_dashboard_routes_keep_bootstrap_load_hook(self):
        for component_name, filename, loader_name in PAGE_CASES:
            route_block = self._route_block(component_name)
            source = (PAGES_DIR / filename).read_text()
            with self.subTest(component=component_name, file=filename, loader=loader_name):
                x_init_calls = re.findall(r'x-init="([^"]+)"', route_block)
                self.assertTrue(
                    x_init_calls,
                    msg=f'{component_name} should keep an x-init bootstrap hook for its initial load path',
                )
                if any(re.search(rf'\b{re.escape(loader_name)}\s*\(', expr) for expr in x_init_calls):
                    continue
                self.assertTrue(
                    any(re.search(r'\binit\s*\(', expr) for expr in x_init_calls),
                    msg=(
                        f'{component_name} should either call {loader_name}() directly from x-init '
                        'or route through init()'
                    ),
                )
                self.assertRegex(
                    source,
                    re.compile(rf'init\(\)\s*\{{.*?\b(?:await\s+)?this\.{re.escape(loader_name)}\(', re.S),
                    msg=f'{filename} init() should bootstrap {loader_name}() when the route uses x-init="init()"',
                )

    def test_page_loader_methods_reset_error_and_finish_loading(self):
        for component_name, filename, loader_name in PAGE_CASES:
            source = (PAGES_DIR / filename).read_text()
            with self.subTest(component=component_name, file=filename, loader=loader_name):
                self.assertRegex(
                    source,
                    re.compile(r'loading:\s*true\s*,.*?loadError:\s*[\"\']', re.S),
                    msg=f'{filename} should initialize shared loading/loadError state',
                )
                self.assertRegex(
                    source,
                    re.compile(rf'async {re.escape(loader_name)}\(\)', re.S),
                    msg=f'{filename} should keep {loader_name}() as its shared loading entry point',
                )
                self.assertRegex(
                    source,
                    re.compile(r'this\.loadError = [\"\'].*?[\"\'];|if \(this\.loading\) this\.loadError = [\"\'].*?[\"\'];', re.S),
                    msg=f'{filename} should clear stale load errors before or during refresh',
                )
                self.assertIn(
                    'this.loading = false;',
                    source,
                    msg=f'{filename} should eventually drop loading after refresh work completes',
                )

    def _route_block(self, component_name: str) -> str:
        marker = f'x-data="{component_name}()"'
        start = INDEX_BODY.find(marker)
        self.assertNotEqual(start, -1, msg=f'could not locate {component_name} route root')
        return INDEX_BODY[start:start + 9000]


if __name__ == '__main__':
    unittest.main()
