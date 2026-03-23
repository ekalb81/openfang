#!/usr/bin/env python3
from pathlib import Path
import re
import unittest

REPO_ROOT = Path(__file__).resolve().parents[1]
CREDENTIALS_RS = REPO_ROOT / 'crates/openfang-extensions/src/credentials.rs'
KERNEL_RS = REPO_ROOT / 'crates/openfang-kernel/src/kernel.rs'


class CredentialRemovalCacheInvalidationTests(unittest.TestCase):
    def test_resolver_exposes_dotenv_cache_clear_helper(self):
        source = CREDENTIALS_RS.read_text(encoding='utf-8')
        self.assertIn('pub fn clear_dotenv_cache(&mut self, key: &str)', source)
        self.assertIn('self.dotenv.remove(key);', source)

    def test_kernel_remove_credential_clears_boot_snapshot_cache(self):
        source = KERNEL_RS.read_text(encoding='utf-8')
        match = re.search(
            r'pub fn remove_credential\(&self, key: &str\) \{(?P<body>.*?)\n    \}',
            source,
            re.S,
        )
        self.assertIsNotNone(match, 'remove_credential function should exist')
        body = match.group('body')
        self.assertIn('resolver.remove_from_vault(key)', body)
        self.assertIn('resolver.clear_dotenv_cache(key);', body)
        self.assertLess(
            body.index('resolver.remove_from_vault(key)'),
            body.index('resolver.clear_dotenv_cache(key);'),
            'remove_credential should clear the dotenv cache after attempting vault removal',
        )

    def test_resolver_has_rust_regression_for_stale_dotenv_snapshot(self):
        source = CREDENTIALS_RS.read_text(encoding='utf-8')
        self.assertIn('fn clear_dotenv_cache_removes_stale_boot_snapshot_value()', source)
        self.assertIn('resolver.clear_dotenv_cache("TEST_CLEAR_DOTENV_CACHE");', source)
        self.assertIn('assert!(resolver.resolve("TEST_CLEAR_DOTENV_CACHE").is_none());', source)
        self.assertIn('assert!(!resolver.has_credential("TEST_CLEAR_DOTENV_CACHE"));', source)


if __name__ == '__main__':
    unittest.main()
