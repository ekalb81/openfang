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

    def test_direct_method_calls_ignores_string_literal_and_builtin_calls(self):
        expr = "style = 'transform: translateY(var(--drag-offset))'; resize(Number($event.target.value)); save()"
        self.assertEqual(module.direct_method_calls(expr), ['resize', 'save'])

    def test_undefined_method_calls_ignore_known_global_template_helpers(self):
        expr = 'renderMarkdown(msg.text); toolIcon(tool.name); actionIcon(event.action); escapeHtml(raw)'
        self.assertEqual(module.undefined_method_calls(expr, {'actionIcon'}), [])

    def test_undefined_method_calls_ignores_property_calls_and_reports_missing_methods(self):
        expr = 'loadOverview().then(() => startAutoRefresh()); missingMethod()'
        self.assertEqual(
            module.undefined_method_calls(expr, {'loadOverview', 'startAutoRefresh'}),
            ['missingMethod'],
        )

    def test_defined_members_in_includes_state_methods_and_getters(self):
        js = """
        function settingsPage() {
            return {
                loading: true,
                loadError: '',
                secLoading: false,
                get filteredModels() { return []; },
                async loadSettings() {},
                saveProviderUrl() {},
            };
        }
        """

        self.assertEqual(
            module.defined_members_in(js),
            {'loading', 'loadError', 'secLoading', 'filteredModels', 'loadSettings', 'saveProviderUrl'},
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

    def test_event_attr_re_captures_route_handlers(self):
        line = '<button @click="refreshRuntime()" @keydown.escape.window="closeModal()">Refresh</button>'
        self.assertEqual(module.EVENT_ATTR_RE.findall(line), ['refreshRuntime()', 'closeModal()'])

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

    def test_simple_member_root_handles_simple_xfor_sources(self):
        self.assertEqual(module.simple_member_root('filteredSessions'), 'filteredSessions')
        self.assertEqual(module.simple_member_root('advancedFields()'), 'advancedFields')
        self.assertIsNone(module.simple_member_root('req.install.steps'))
        self.assertIsNone(module.simple_member_root('(condition) ? a : b'))

    def test_model_member_root_supports_dot_bracket_and_call_forms(self):
        self.assertEqual(module.model_member_root('formValues[field.key]'), 'formValues')
        self.assertEqual(module.model_member_root('configForm.name'), 'configForm')
        self.assertEqual(module.model_member_root('spawnForm.caps.memory_read'), 'spawnForm')

    def test_xmodel_xfor_and_xhtml_regexes_capture_route_bindings(self):
        line = (
            '<input x-model="formValues[field.key]">'
            '<template x-for="session in filteredSessions">'
            '<div x-html="highlightSearch(renderMarkdown(msg.text))"></div>'
            '<button @click="refreshRuntime()">Refresh</button>'
        )
        self.assertEqual(module.XMODEL_RE.findall(line), ['formValues[field.key]'])
        self.assertEqual(module.XFOR_RE.findall(line), ['session in filteredSessions'])
        self.assertEqual(module.XHTML_RE.findall(line), ['highlightSearch(renderMarkdown(msg.text))'])

    def test_undefined_method_calls_detect_xfor_helper_typos(self):
        self.assertEqual(
            module.undefined_method_calls('configSectionField(fields)', {'configSectionFields'}),
            ['configSectionField'],
        )
        self.assertEqual(
            module.undefined_method_calls('advancedFields()', {'advancedFields'}),
            [],
        )

    def test_page_leave_hook_regex_matches_expected_hook(self):
        hook_re = module.page_leave_hook_re('destroy')
        self.assertIsNotNone(hook_re.search('@page-leave.window="destroy()"'))
        self.assertIsNone(hook_re.search('@page-leave.window="stopSSE()"'))

    def test_route_leave_fallbacks_allow_destroy_for_stream_cleanup(self):
        self.assertEqual(module.ROUTE_LEAVE_FALLBACKS['stopSSE'], ('destroy',))
        self.assertEqual(module.ROUTE_LEAVE_FALLBACKS['stopAutoRefresh'], ('destroy',))

    def test_main_allows_destroy_hook_to_cover_stop_sse_cleanup(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pages_dir = root / 'crates/openfang-api/static/js/pages'
            pages_dir.mkdir(parents=True)
            (pages_dir / 'comms.js').write_text(
                """
                function commsPage() {
                    return {
                        loading: false,
                        loadError: '',
                        stopSSE() {},
                        destroy() { this.stopSSE(); },
                        loadData() {},
                    };
                }
                """,
                encoding='utf-8',
            )
            (root / 'crates/openfang-api/static/index_body.html').write_text(
                """
                <template x-if=\"page === 'comms'\">
                  <section x-data=\"commsPage()\" x-init=\"loadData()\" @page-leave.window=\"destroy()\"></section>
                </template>
                """,
                encoding='utf-8',
            )

            old_repo_root = module.REPO_ROOT
            old_pages_dir = module.PAGES_DIR
            old_index_body = module.INDEX_BODY
            try:
                module.REPO_ROOT = root
                module.PAGES_DIR = pages_dir
                module.INDEX_BODY = root / 'crates/openfang-api/static/index_body.html'
                self.assertEqual(module.main(), 0)
            finally:
                module.REPO_ROOT = old_repo_root
                module.PAGES_DIR = old_pages_dir
                module.INDEX_BODY = old_index_body

    def test_main_flags_route_scoped_xinit_typo_outside_nested_xdata(self):
        # Use a TemporaryDirectory so the checker reads a minimal synthetic repo.
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pages_dir = root / 'crates/openfang-api/static/js/pages'
            pages_dir.mkdir(parents=True)
            (pages_dir / 'sessions.js').write_text(
                """
                function sessionsPage() {
                    return {
                        loading: true,
                        loadError: '',
                        loadSessions() {},
                    };
                }
                """,
                encoding='utf-8',
            )
            (root / 'crates/openfang-api/static/index_body.html').write_text(
                """
                <template x-if="page === 'sessions'">
                  <div x-data="sessionsPage()">
                    <div class="page-body" x-init="loadSessons()"></div>
                    <div x-data="childWidget()" x-init="init()"></div>
                  </div>
                </template>
                """,
                encoding='utf-8',
            )

            old_repo_root = module.REPO_ROOT
            old_pages_dir = module.PAGES_DIR
            old_index_body = module.INDEX_BODY
            try:
                module.REPO_ROOT = root
                module.PAGES_DIR = pages_dir
                module.INDEX_BODY = root / 'crates/openfang-api/static/index_body.html'
                self.assertEqual(module.main(), 1)
            finally:
                module.REPO_ROOT = old_repo_root
                module.PAGES_DIR = old_pages_dir
                module.INDEX_BODY = old_index_body

    def test_main_flags_route_scoped_event_handler_typos_outside_nested_xdata(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pages_dir = root / 'crates/openfang-api/static/js/pages'
            pages_dir.mkdir(parents=True)
            (pages_dir / 'runtime.js').write_text(
                """
                function runtimePage() {
                    return {
                        loading: false,
                        loadError: '',
                        refreshRuntime() {},
                        closeModal() {},
                    };
                }
                """,
                encoding='utf-8',
            )
            (root / 'crates/openfang-api/static/index_body.html').write_text(
                """
                <template x-if="page === 'runtime'">
                  <section x-data="runtimePage()">
                    <button @click="refreshRuntme()">Refresh</button>
                    <div @keydown.escape.window="closeModal()"></div>
                    <div x-data="childWidget()">
                      <button @click="missingChildMethod()">Child action</button>
                    </div>
                  </section>
                </template>
                """,
                encoding='utf-8',
            )

            old_repo_root = module.REPO_ROOT
            old_pages_dir = module.PAGES_DIR
            old_index_body = module.INDEX_BODY
            try:
                module.REPO_ROOT = root
                module.PAGES_DIR = pages_dir
                module.INDEX_BODY = root / 'crates/openfang-api/static/index_body.html'
                self.assertEqual(module.main(), 1)
            finally:
                module.REPO_ROOT = old_repo_root
                module.PAGES_DIR = old_pages_dir
                module.INDEX_BODY = old_index_body

    def test_main_flags_route_scoped_xhtml_method_typos_but_allows_global_helpers(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pages_dir = root / 'crates/openfang-api/static/js/pages'
            pages_dir.mkdir(parents=True)
            (pages_dir / 'chat.js').write_text(
                """
                function chatPage() {
                    return {
                        loading: false,
                        loadError: '',
                        highlightSearch() {},
                    };
                }
                """,
                encoding='utf-8',
            )
            (root / 'crates/openfang-api/static/index_body.html').write_text(
                """
                <template x-if="page === 'chat'">
                  <section x-data="chatPage()">
                    <div x-html="highlightSerch(renderMarkdown(msg.text))"></div>
                    <div x-html="toolIcon(tool.name)"></div>
                    <div x-data="childWidget()">
                      <div x-html="missingChildMethod()"></div>
                    </div>
                  </section>
                </template>
                """,
                encoding='utf-8',
            )

            old_repo_root = module.REPO_ROOT
            old_pages_dir = module.PAGES_DIR
            old_index_body = module.INDEX_BODY
            try:
                module.REPO_ROOT = root
                module.PAGES_DIR = pages_dir
                module.INDEX_BODY = root / 'crates/openfang-api/static/index_body.html'
                self.assertEqual(module.main(), 1)
            finally:
                module.REPO_ROOT = old_repo_root
                module.PAGES_DIR = old_pages_dir
                module.INDEX_BODY = old_index_body

    def test_main_flags_route_scoped_xfor_helper_typos_outside_nested_xdata(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pages_dir = root / 'crates/openfang-api/static/js/pages'
            pages_dir.mkdir(parents=True)
            (pages_dir / 'settings.js').write_text(
                """
                function settingsPage() {
                    return {
                        loading: false,
                        loadError: '',
                        configSchema: {},
                        configSectionFields() { return []; },
                    };
                }
                """,
                encoding='utf-8',
            )
            (root / 'crates/openfang-api/static/index_body.html').write_text(
                """
                <template x-if="page === 'settings'">
                  <section x-data="settingsPage()">
                    <template x-for="(fields, section) in configSchema" :key="section">
                      <template x-for="field in configSectionField(fields)" :key="field.name">
                        <div x-text="field.name"></div>
                      </template>
                    </template>
                    <div x-data="childWidget()">
                      <template x-for="field in missingChildHelper(fields)" :key="field.name"></template>
                    </div>
                  </section>
                </template>
                """,
                encoding='utf-8',
            )

            old_repo_root = module.REPO_ROOT
            old_pages_dir = module.PAGES_DIR
            old_index_body = module.INDEX_BODY
            try:
                module.REPO_ROOT = root
                module.PAGES_DIR = pages_dir
                module.INDEX_BODY = root / 'crates/openfang-api/static/index_body.html'
                self.assertEqual(module.main(), 1)
            finally:
                module.REPO_ROOT = old_repo_root
                module.PAGES_DIR = old_pages_dir
                module.INDEX_BODY = old_index_body


if __name__ == '__main__':
    unittest.main()
