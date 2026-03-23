from pathlib import Path
import re
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
LOGS_JS = REPO_ROOT / 'crates' / 'openfang-api' / 'static' / 'js' / 'pages' / 'logs.js'
INDEX_BODY = REPO_ROOT / 'crates' / 'openfang-api' / 'static' / 'index_body.html'


class LogsPageInitWiringTests(unittest.TestCase):
    def test_logs_page_exposes_init_method(self):
        js = LOGS_JS.read_text()
        self.assertIn('async init() {', js)
        self.assertIn('await this.loadData();', js)
        self.assertIn('this.startStreaming();', js)

    def test_logs_page_template_calls_init_and_destroy_once(self):
        html = INDEX_BODY.read_text()
        self.assertIn('x-data="logsPage()" x-init="init()" @page-leave.window="destroy()"', html)
        self.assertNotIn('x-data="logsPage()" @page-leave.window="destroy()"', html)

        route_match = re.search(
            r'<template x-if="page === \'logs\'">(?P<body>.*?)</template>',
            html,
            re.DOTALL,
        )
        self.assertIsNotNone(route_match)
        assert route_match is not None
        self.assertEqual(route_match.group('body').count('x-init="init()"'), 1)


if __name__ == '__main__':
    unittest.main()
