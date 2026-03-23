#!/usr/bin/env python3
from pathlib import Path
import unittest

REPO_ROOT = Path(__file__).resolve().parents[1]
OVERVIEW_JS = REPO_ROOT / 'crates/openfang-api/static/js/pages/overview.js'
INDEX_BODY = REPO_ROOT / 'crates/openfang-api/static/index_body.html'


class OverviewPageCleanupWiringTests(unittest.TestCase):
    def test_overview_page_exposes_destroy_alias_for_route_cleanup(self):
        js = OVERVIEW_JS.read_text(encoding='utf-8')
        self.assertIn('destroy() {', js)
        self.assertIn('this.stopAutoRefresh();', js)

    def test_overview_route_uses_shared_destroy_hook(self):
        html = INDEX_BODY.read_text(encoding='utf-8')
        self.assertIn('x-data="overviewPage()" x-init="loadOverview().then(() => startAutoRefresh())" @page-leave.window="destroy()"', html)
        self.assertNotIn('x-data="overviewPage()" x-init="loadOverview().then(() => startAutoRefresh())" @page-leave.window="stopAutoRefresh()"', html)


if __name__ == '__main__':
    unittest.main()
