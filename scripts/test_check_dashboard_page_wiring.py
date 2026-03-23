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


if __name__ == '__main__':
    unittest.main()
