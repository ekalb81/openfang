#!/usr/bin/env python3
from pathlib import Path
import re
import unittest

REPO_ROOT = Path(__file__).resolve().parents[1]
PAGE_FILES = [
    REPO_ROOT / 'crates/openfang-api/static/js/pages/chat.js',
    REPO_ROOT / 'crates/openfang-api/static/js/pages/overview.js',
    REPO_ROOT / 'crates/openfang-api/static/js/pages/wizard.js',
]

HELPER_RE = re.compile(
    r"\n\s*localFlag\(key\)\s*\{.*?\n\s*\},\n\s*setLocalFlag\(key, value\)\s*\{.*?\n\s*\},",
    re.S,
)


class RoutePageStorageGuardTests(unittest.TestCase):
    def test_route_pages_use_guarded_storage_helpers_only(self):
        for path in PAGE_FILES:
            with self.subTest(page=path.name):
                source = path.read_text(encoding='utf-8')
                helper_match = HELPER_RE.search(source)
                self.assertIsNotNone(helper_match, f'{path.name} should define localFlag/setLocalFlag helpers')
                helper_block = helper_match.group(0)
                self.assertIn('localStorage.getItem', helper_block, f'{path.name} localFlag helper should read localStorage')
                self.assertIn('localStorage.setItem', helper_block, f'{path.name} setLocalFlag helper should write localStorage')
                remainder = source.replace(helper_block, '\n')
                self.assertNotIn('localStorage.', remainder, f'{path.name} should not access localStorage outside guarded helpers')


if __name__ == '__main__':
    unittest.main()
