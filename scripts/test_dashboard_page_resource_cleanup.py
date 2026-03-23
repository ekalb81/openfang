import pathlib
import re
import unittest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
PAGES_DIR = REPO_ROOT / 'crates' / 'openfang-api' / 'static' / 'js' / 'pages'
INDEX_BODY = (REPO_ROOT / 'crates' / 'openfang-api' / 'static' / 'index_body.html').read_text()

RESOURCE_ASSIGN_RE = re.compile(r'this\.(\w+)\s*=\s*(setInterval|setTimeout|new EventSource)')
METHOD_START_TEMPLATE = r'(?:{name}\(\)|{name}\s*:\s*function\s*\(\))\s*\{{'
THIS_METHOD_CALL_RE = re.compile(r'\bthis\.([A-Za-z_][A-Za-z0-9_]*)\s*\(')


def mounted_resource_pages() -> dict[str, str]:
    pages = {}
    for page_file in sorted(PAGES_DIR.glob('*.js')):
        text = page_file.read_text()
        if not RESOURCE_ASSIGN_RE.search(text):
            continue
        page_name = page_file.stem.replace('-', '_')
        component_name = ''.join(part.capitalize() if idx else part for idx, part in enumerate(page_name.split('_'))) + 'Page'
        if f'{component_name}()"' in INDEX_BODY:
            pages[page_file.name] = component_name
    return pages


RESOURCE_PAGES = mounted_resource_pages()


class DashboardPageResourceCleanupTests(unittest.TestCase):
    def test_resource_pages_keep_route_leave_destroy_hook(self):
        for filename, page_name in RESOURCE_PAGES.items():
            with self.subTest(page=filename):
                self.assertIn(
                    f'{page_name}()"',
                    INDEX_BODY,
                    msg=f'{page_name} route should stay mounted in index_body.html',
                )
                self.assertIn(
                    '@page-leave.window="destroy()"',
                    self._route_slice(page_name),
                    msg=f'{page_name} route should tear down long-lived resources on page leave',
                )

    def test_destroy_cleans_every_long_lived_resource_handle(self):
        for filename in RESOURCE_PAGES:
            text = (PAGES_DIR / filename).read_text()
            cleanup_body = self._cleanup_body(text, filename)
            handles = RESOURCE_ASSIGN_RE.findall(text)
            self.assertTrue(handles, msg=f'{filename} should define at least one long-lived resource handle')
            for handle, kind in handles:
                with self.subTest(page=filename, handle=handle, kind=kind):
                    self.assertIn(handle, cleanup_body, msg=f'{filename} cleanup path should mention {handle}')
                    if kind == 'setInterval':
                        self.assertRegex(
                            cleanup_body,
                            rf'clearInterval\(this\.{re.escape(handle)}\)',
                            msg=f'{filename} cleanup path should clearInterval({handle})',
                        )
                    elif kind == 'setTimeout':
                        self.assertRegex(
                            cleanup_body,
                            rf'clearTimeout\(this\.{re.escape(handle)}\)',
                            msg=f'{filename} cleanup path should clearTimeout({handle})',
                        )
                    else:
                        self.assertRegex(
                            cleanup_body,
                            rf'this\.{re.escape(handle)}\.close\(\)',
                            msg=f'{filename} cleanup path should close() {handle}',
                        )

    def test_destroy_nulls_or_resets_handles_after_cleanup(self):
        for filename in RESOURCE_PAGES:
            text = (PAGES_DIR / filename).read_text()
            cleanup_body = self._cleanup_body(text, filename)
            for handle, kind in RESOURCE_ASSIGN_RE.findall(text):
                with self.subTest(page=filename, handle=handle, kind=kind):
                    expected_reset = rf'this\.{re.escape(handle)}\s*=\s*null'
                    self.assertRegex(
                        cleanup_body,
                        expected_reset,
                        msg=f'{filename} cleanup path should reset {handle} after cleanup',
                    )

    def test_cleanup_body_includes_destroy_helper_bodies(self):
        sample = """
function samplePage() {
  return {
    destroy() {
      this.stopPolling();
      this.stopStream();
    },
    stopPolling() {
      if (this.pollTimer) { clearInterval(this.pollTimer); this.pollTimer = null; }
    },
    stopStream() {
      if (this.sseSource) { this.sseSource.close(); this.sseSource = null; }
    }
  };
}
"""
        body = self._cleanup_body(sample, 'sample.js')
        self.assertIn('this.stopPolling();', body)
        self.assertIn('clearInterval(this.pollTimer)', body)
        self.assertIn('this.sseSource.close()', body)
        self.assertIn('this.sseSource = null', body)

    def test_method_body_parser_handles_inline_guards(self):
        sample = """
function channelsPage() {
  return {
    destroy() {
      if (this.pollTimer) { clearInterval(this.pollTimer); this.pollTimer = null; }
      if (this.qrPollTimer) { clearInterval(this.qrPollTimer); this.qrPollTimer = null; }
    }
  };
}
"""
        body = self._method_body(sample, 'destroy', 'sample.js')
        self.assertIn('clearInterval(this.pollTimer)', body)
        self.assertIn('this.qrPollTimer = null', body)

    def _cleanup_body(self, text: str, filename: str) -> str:
        cleanup_parts = []
        visited = set()

        def visit(method_name: str) -> None:
            if method_name in visited:
                return
            visited.add(method_name)
            body = self._method_body(text, method_name, filename)
            cleanup_parts.append(body)
            for called_method in THIS_METHOD_CALL_RE.findall(body):
                if called_method != method_name and self._has_method(text, called_method):
                    visit(called_method)

        visit('destroy')
        return '\n'.join(cleanup_parts)

    def _has_method(self, text: str, method_name: str) -> bool:
        return re.search(METHOD_START_TEMPLATE.format(name=re.escape(method_name)), text) is not None

    def _destroy_body(self, text: str, filename: str) -> str:
        return self._method_body(text, 'destroy', filename)

    def _method_body(self, text: str, method_name: str, filename: str) -> str:
        method_start = re.search(METHOD_START_TEMPLATE.format(name=re.escape(method_name)), text)
        self.assertIsNotNone(method_start, msg=f'{filename} should define {method_name}()')
        body_start = method_start.end()
        depth = 1
        idx = body_start
        while idx < len(text):
            char = text[idx]
            if char == '{':
                depth += 1
            elif char == '}':
                depth -= 1
                if depth == 0:
                    return text[body_start:idx]
            idx += 1
        self.fail(f'{filename} {method_name}() body should have balanced braces')

    def _route_slice(self, page_name: str) -> str:
        start = INDEX_BODY.index(f'{page_name}()"')
        return INDEX_BODY[start:start + 240]


if __name__ == '__main__':
    unittest.main()
