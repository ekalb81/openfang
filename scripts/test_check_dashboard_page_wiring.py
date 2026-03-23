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

    def test_expression_member_roots_ignores_calls_and_member_access_suffixes(self):
        self.assertEqual(
            module.expression_member_roots('selectedSession && selectedSession.agent_name && formatLabel(selectedSession)'),
            {'selectedSession'},
        )
        self.assertEqual(
            module.expression_member_roots("toolIcon('hammer') || customState"),
            {'customState'},
        )
        self.assertEqual(
            module.expression_member_roots("{ active: filterStatus === 'all', done: step > 1 }"),
            {'filterStatus', 'step'},
        )

    def test_undefined_expression_member_roots_flags_compound_state_typos(self):
        defined_members = {'selectedSession', 'loading', 'loadError'}
        self.assertEqual(
            module.undefined_expression_member_roots('selectedSesion && !loading && !loadError', defined_members),
            {'selectedSesion'},
        )
        self.assertEqual(
            module.undefined_expression_member_roots('selectedSession && !loading', defined_members),
            set(),
        )
        self.assertEqual(
            module.undefined_expression_member_roots('idx * 50 + 30', defined_members),
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

    def test_collect_component_block_lines_returns_nested_component_scope(self):
        index_lines = [
            '<template x-if="page === \'workflows\'">',
            '  <section x-data="workflowsPage()">',
            '    <div x-data="workflowBuilder()">',
            '      <button @click="save()">Save</button>',
            '    </div>',
            '  </section>',
            '</template>',
        ]

        self.assertEqual(
            module.collect_component_block_lines(index_lines, 3),
            [
                (3, '    <div x-data="workflowBuilder()">'),
                (4, '      <button @click="save()">Save</button>'),
                (5, '    </div>'),
            ],
        )

    def test_simple_member_root_handles_simple_xfor_sources(self):
        self.assertEqual(module.simple_member_root('filteredSessions'), 'filteredSessions')
        self.assertEqual(module.simple_member_root('advancedFields()'), 'advancedFields')
        self.assertIsNone(module.simple_member_root('req.install.steps'))
        self.assertIsNone(module.simple_member_root('(condition) ? a : b'))

    def test_model_member_root_supports_dot_bracket_and_call_forms(self):
        self.assertEqual(module.model_member_root('formValues[field.key]'), 'formValues')
        self.assertEqual(module.model_member_root('configForm.name'), 'configForm')
        self.assertEqual(module.model_member_root('spawnForm.caps.memory_read'), 'spawnForm')

    def test_direct_member_root_supports_simple_unary_and_member_access_forms(self):
        self.assertEqual(module.direct_member_root('selectedSession.agent_name'), 'selectedSession')
        self.assertEqual(module.direct_member_root('!loadError'), 'loadError')
        self.assertEqual(module.direct_member_root('formValues[field.key]'), 'formValues')
        self.assertIsNone(module.direct_member_root("loading ? 'yes' : 'no'"))
        self.assertIsNone(module.direct_member_root('$event.target.value'))

    def test_top_level_expr_parts_splits_semicolon_delimited_effects(self):
        self.assertEqual(
            module.top_level_expr_parts('nodes.length; selectedNode; scheduleRender(); !loadError'),
            ['nodes.length', 'selectedNode', 'scheduleRender()', '!loadError'],
        )

    def test_xmodel_xfor_xhtml_and_xeffect_regexes_capture_route_bindings(self):
        line = (
            '<input x-model="formValues[field.key]">'
            '<input x-model.number="retryCount">'
            '<template x-for="session in filteredSessions">'
            '<div x-html="highlightSearch(renderMarkdown(msg.text))"></div>'
            '<g x-effect="nodes.length; scheduleRender()"></g>'
            '<button @click="refreshRuntime()">Refresh</button>'
        )
        self.assertEqual(module.XMODEL_RE.findall(line), ['formValues[field.key]', 'retryCount'])
        self.assertEqual(module.XFOR_RE.findall(line), ['session in filteredSessions'])
        self.assertEqual(module.XHTML_RE.findall(line), ['highlightSearch(renderMarkdown(msg.text))'])
        self.assertEqual(module.XEFFECT_RE.findall(line), ['nodes.length; scheduleRender()'])

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

    def test_main_flags_nested_component_route_typo_when_route_name_differs_from_file_stem(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pages_dir = root / 'crates/openfang-api/static/js/pages'
            pages_dir.mkdir(parents=True)
            (pages_dir / 'workflow-builder.js').write_text(
                """
                function workflowBuilder() {
                    return {
                        nodes: [],
                        scheduleRender() {},
                    };
                }
                """,
                encoding='utf-8',
            )
            (root / 'crates/openfang-api/static/index_body.html').write_text(
                """
                <template x-if=\"page === 'workflows'\">
                  <section x-data=\"workflowsPage()\">
                    <div x-data=\"workflowBuilder()\">
                      <svg x-effect=\"connectons.length; scheduleRender()\"></svg>
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

    def test_main_flags_route_scoped_xmodel_modifiers_outside_nested_xdata(self):
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
                        customModelContext: 0,
                    };
                }
                """,
                encoding='utf-8',
            )
            (root / 'crates/openfang-api/static/index_body.html').write_text(
                """
                <template x-if="page === 'settings'">
                  <section x-data="settingsPage()">
                    <input x-model.number="customModelCntxt">
                    <div x-data="childWidget()">
                      <input x-model.number="missingChildField">
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

    def test_main_flags_direct_route_expression_member_typos_outside_nested_xdata(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pages_dir = root / 'crates/openfang-api/static/js/pages'
            pages_dir.mkdir(parents=True)
            (pages_dir / 'sessions.js').write_text(
                """
                function sessionsPage() {
                    return {
                        loading: false,
                        selectedSession: null,
                    };
                }
                """,
                encoding='utf-8',
            )
            (root / 'crates/openfang-api/static/index_body.html').write_text(
                """
                <template x-if="page === 'sessions'">
                  <section x-data="sessionsPage()">
                    <div x-show="selectedSesion"></div>
                    <div x-text="selectedSesion.agent_name"></div>
                    <div x-show="selectedSesion && selectedSession.agent_name"></div>
                    <div x-data="childWidget()">
                      <div x-text="missingChildState.name"></div>
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

    def test_main_flags_route_scoped_xeffect_typos(self):
        import tempfile
        import io
        from contextlib import redirect_stderr

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pages_dir = root / 'crates/openfang-api/static/js/pages'
            pages_dir.mkdir(parents=True)
            (pages_dir / 'workflow.js').write_text(
                """
                function workflowPage() {
                    return {
                        nodes: [],
                        connections: [],
                        selectedNode: null,
                        selectedConnection: null,
                        connecting: false,
                        connectPreview: null,
                        scheduleRender() {},
                    };
                }
                """,
                encoding='utf-8',
            )
            (root / 'crates/openfang-api/static/index_body.html').write_text(
                """
                <template x-if="page === 'workflow'">
                  <section x-data="workflowPage()">
                    <g x-effect="nodes.length; connectons.length; scheduleRnder()"></g>
                  </section>
                </template>
                """,
                encoding='utf-8',
            )

            old_repo_root = module.REPO_ROOT
            old_pages_dir = module.PAGES_DIR
            old_index_body = module.INDEX_BODY
            stderr = io.StringIO()
            try:
                module.REPO_ROOT = root
                module.PAGES_DIR = pages_dir
                module.INDEX_BODY = root / 'crates/openfang-api/static/index_body.html'
                with redirect_stderr(stderr):
                    self.assertEqual(module.main(), 1)
            finally:
                module.REPO_ROOT = old_repo_root
                module.PAGES_DIR = old_pages_dir
                module.INDEX_BODY = old_index_body

            output = stderr.getvalue()
            self.assertIn('route x-effect references connectons but workflowPage does not define it', output)
            self.assertIn('route x-effect references scheduleRnder() but workflowPage does not define it', output)

    def test_main_requires_invoked_xdata_for_alpine_registered_pages(self):
        import tempfile
        import io
        from contextlib import redirect_stderr

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pages_dir = root / 'crates/openfang-api/static/js/pages'
            pages_dir.mkdir(parents=True)
            (pages_dir / 'runtime.js').write_text(
                """
                document.addEventListener('alpine:init', function() {
                    Alpine.data('runtimePage', function() {
                        return {
                            loading: false,
                        };
                    });
                });
                """,
                encoding='utf-8',
            )
            (root / 'crates/openfang-api/static/index_body.html').write_text(
                """
                <template x-if="page === 'runtime'">
                  <section x-data="runtimePage"></section>
                </template>
                """,
                encoding='utf-8',
            )

            old_repo_root = module.REPO_ROOT
            old_pages_dir = module.PAGES_DIR
            old_index_body = module.INDEX_BODY
            stderr = io.StringIO()
            try:
                module.REPO_ROOT = root
                module.PAGES_DIR = pages_dir
                module.INDEX_BODY = root / 'crates/openfang-api/static/index_body.html'
                with redirect_stderr(stderr):
                    self.assertEqual(module.main(), 1)
            finally:
                module.REPO_ROOT = old_repo_root
                module.PAGES_DIR = old_pages_dir
                module.INDEX_BODY = old_index_body

            self.assertIn(
                'missing x-data="runtimePage()" route binding',
                stderr.getvalue(),
            )


if __name__ == '__main__':
    unittest.main()
