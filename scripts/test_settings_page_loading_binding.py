import pathlib
import re
import unittest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
INDEX_BODY = REPO_ROOT / "crates/openfang-api/static/index_body.html"
SETTINGS_JS = REPO_ROOT / "crates/openfang-api/static/js/pages/settings.js"


class SettingsPageLoadingBindingTests(unittest.TestCase):
    def test_settings_template_uses_shared_loading_state(self):
        html = INDEX_BODY.read_text()
        match = re.search(
            r'<div x-data="settingsPage\(\)" @page-leave\.window="destroy\(\)">(.*?)<!-- Network tab -->',
            html,
            re.S,
        )
        self.assertIsNotNone(match, "could not isolate settingsPage template block")
        block = match.group(1)

        self.assertIn('x-init="loadSettings()"', block)
        self.assertIn('x-show="loading"', block)
        self.assertIn('x-show="!loading && loadError"', block)
        self.assertIn('x-show="!loading && !loadError"', block)
        self.assertNotIn('settingsLoading', block)

    def test_settings_page_state_and_loader_keep_loading_contract(self):
        source = SETTINGS_JS.read_text()

        self.assertRegex(
            source,
            re.compile(r"function settingsPage\(\) \{\s*return \{.*?loading: true,", re.S),
        )
        self.assertRegex(
            source,
            re.compile(
                r"async loadSettings\(\) \{.*?this\.loading = true;.*?this\.loading = false;",
                re.S,
            ),
        )
        self.assertNotIn('settingsLoading', source)


if __name__ == "__main__":
    unittest.main()
