#!/usr/bin/env python3
from pathlib import Path
import unittest

REPO_ROOT = Path(__file__).resolve().parents[1]
COMMS_JS = REPO_ROOT / 'crates/openfang-api/static/js/pages/comms.js'
INDEX_BODY = REPO_ROOT / 'crates/openfang-api/static/index_body.html'


class CommsPageCleanupWiringTests(unittest.TestCase):
    def test_comms_page_exposes_destroy_alias_for_route_cleanup(self):
        js = COMMS_JS.read_text(encoding='utf-8')
        self.assertIn('destroy() {', js)
        self.assertIn('this.stopSSE();', js)

    def test_comms_route_uses_shared_destroy_hook(self):
        html = INDEX_BODY.read_text(encoding='utf-8')
        self.assertIn('x-data="commsPage()" x-init="loadData()" @page-leave.window="destroy()"', html)
        self.assertNotIn('x-data="commsPage()" x-init="loadData()" @page-leave.window="stopSSE()"', html)


if __name__ == '__main__':
    unittest.main()
