#!/usr/bin/env python3
import importlib.util
from pathlib import Path
import unittest

MODULE_PATH = Path(__file__).with_name('check_dashboard_page_wiring.py')
spec = importlib.util.spec_from_file_location('check_dashboard_page_wiring', MODULE_PATH)
module = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(module)


class DashboardPageWiringTests(unittest.TestCase):
    def test_normalize_button_label_strips_nested_markup(self):
        self.assertEqual(
            module.normalize_button_label('<span class="icon">↻</span> Refresh <strong>QR</strong>'),
            '↻ Refresh QR',
        )

    def test_retry_or_refresh_detection_allows_qualifiers(self):
        self.assertTrue(module.is_retry_or_refresh_label('Refresh QR'))
        self.assertTrue(module.is_retry_or_refresh_label('Retry now'))
        self.assertTrue(module.is_retry_or_refresh_label('<span>Refresh</span> dashboard'))
        self.assertFalse(module.is_retry_or_refresh_label('Delete'))

    def test_defined_methods_in_supports_shorthand_and_function_properties(self):
        js = """
        function logsPage() {
            return {
                async load() {},
                stopSSE: function() {},
                stopAutoRefresh: async function() {},
                plainMethod() {},
            };
        }
        """

        self.assertEqual(
            module.defined_methods_in(js),
            {'load', 'stopSSE', 'stopAutoRefresh', 'plainMethod'},
        )

    def test_direct_method_calls_ignores_if_keyword(self):
        expr = 'if (loadError) refreshRuntime(); bootstrapOverview()'
        self.assertEqual(module.direct_method_calls(expr), ['refreshRuntime', 'bootstrapOverview'])

    def test_defined_members_in_includes_state_and_methods(self):
        js = """
        function settingsPage() {
            return {
                loading: true,
                loadError: '',
                secLoading: false,
                async loadSettings() {},
                saveProviderUrl() {},
            };
        }
        """

        self.assertEqual(
            module.defined_members_in(js),
            {'loading', 'loadError', 'secLoading', 'loadSettings', 'saveProviderUrl'},
        )

    def test_undefined_state_like_identifiers_flags_missing_loading_symbol(self):
        defined_members = {'loading', 'loadError', 'refreshRuntime'}

        self.assertEqual(
            module.undefined_state_like_identifiers('!settingsLoading && !loadError', defined_members),
            {'settingsLoading'},
        )
        self.assertEqual(
            module.undefined_state_like_identifiers('!loading && !loadError', defined_members),
            set(),
        )

    def test_route_expr_re_matches_text_and_bound_attributes(self):
        line = (
            '<button :disabled="settingsLoading || saveError" '
            'x-text="settingsLoading ? \'Saving...\' : \'Save\'" '
            'x-show="!loadError"></button>'
        )

        self.assertEqual(
            module.ROUTE_EXPR_RE.findall(line),
            [
                'settingsLoading || saveError',
                "settingsLoading ? 'Saving...' : 'Save'",
                '!loadError',
            ],
        )

    def test_route_expr_re_ignores_event_handlers(self):
        line = '<button @click="refreshRuntime()" :disabled="runtimeLoading">Refresh</button>'
        self.assertEqual(module.ROUTE_EXPR_RE.findall(line), ['runtimeLoading'])

    def test_collect_route_lines_groups_nested_template_body(self):
        index_lines = [
            '<template x-if="page === \'runtime\'">',
            '  <section x-data="runtimePage()">',
            '    <template x-if="loadError">',
            '      <button @click="refreshRuntime()">Refresh Runtime</button>',
            '    </template>',
            '  </section>',
            '</template>',
        ]

        self.assertEqual(
            module.collect_route_lines(index_lines),
            {
                'runtime': [
                    (1, '<template x-if="page === \'runtime\'">'),
                    (2, '  <section x-data="runtimePage()">'),
                    (3, '    <template x-if="loadError">'),
                    (4, '      <button @click="refreshRuntime()">Refresh Runtime</button>'),
                    (5, '    </template>'),
                    (6, '  </section>'),
                    (7, '</template>'),
                ]
            },
        )

    def test_html_tag_depth_delta_tracks_open_and_close_tags(self):
        self.assertEqual(module.html_tag_depth_delta('<div x-data="budgetPage()">'), 1)
        self.assertEqual(module.html_tag_depth_delta('</div>'), -1)
        self.assertEqual(module.html_tag_depth_delta('<input type="text">'), 0)

    def test_page_leave_hook_regex_matches_expected_hook(self):
        hook_re = module.page_leave_hook_re('destroy')
        self.assertIsNotNone(hook_re.search('@page-leave.window="destroy()"'))
        self.assertIsNone(hook_re.search('@page-leave.window="stopSSE()"'))


if __name__ == '__main__':
    unittest.main()
