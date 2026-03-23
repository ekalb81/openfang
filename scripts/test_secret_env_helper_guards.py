#!/usr/bin/env python3
from pathlib import Path
import unittest

REPO_ROOT = Path(__file__).resolve().parents[1]
ROUTES_RS = REPO_ROOT / 'crates/openfang-api/src/routes.rs'


class SecretEnvHelperGuardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = ROUTES_RS.read_text(encoding='utf-8')

    def helper_body(self, signature: str, next_signature: str) -> str:
        start = self.source.find(signature)
        self.assertNotEqual(start, -1, f'{signature} should exist')
        end = self.source.find(next_signature, start)
        self.assertNotEqual(end, -1, f'{next_signature} should exist after {signature}')
        return self.source[start:end]

    def test_secret_env_key_matcher_trims_existing_keys(self):
        self.assertIn('fn secret_env_line_matches_key(line: &str, key: &str) -> bool {', self.source)
        self.assertIn("line.split_once('=')", self.source)
        self.assertIn('existing_key.trim() == key', self.source)

    def test_write_secret_env_rejects_multiline_values_before_mutating_file(self):
        body = self.helper_body(
            'fn write_secret_env(path: &std::path::Path, key: &str, value: &str) -> Result<(), std::io::Error> {',
            'fn remove_secret_env(path: &std::path::Path, key: &str) -> Result<(), std::io::Error> {',
        )
        self.assertIn("value.contains(['\\n', '\\r'])", body)
        self.assertIn('std::io::ErrorKind::InvalidInput', body)
        self.assertIn('Refusing to write multiline secret_env value for {key}', body)
        self.assertLess(
            body.index("value.contains(['\\n', '\\r'])"),
            body.index('let mut lines: Vec<String> = if path.exists() {'),
            'write_secret_env should reject multiline values before reading or mutating secrets.env',
        )

    def test_write_secret_env_rewrites_only_exact_key_and_uses_atomic_writer(self):
        body = self.helper_body(
            'fn write_secret_env(path: &std::path::Path, key: &str, value: &str) -> Result<(), std::io::Error> {',
            'fn remove_secret_env(path: &std::path::Path, key: &str) -> Result<(), std::io::Error> {',
        )
        self.assertIn('lines.retain(|l| !secret_env_line_matches_key(l, key));', body)
        self.assertIn('escape_secret_env_value(value)', body)
        self.assertIn('write_text_file_atomically(path, &(lines.join("\\n") + "\\n"))?;', body)

    def test_remove_secret_env_noops_on_missing_file_and_matches_trimmed_exact_key(self):
        body = self.helper_body(
            'fn remove_secret_env(path: &std::path::Path, key: &str) -> Result<(), std::io::Error> {',
            '// ── Config.toml channel management helpers ──────────────────────────',
        )
        self.assertIn('if !path.exists() {', body)
        self.assertIn('return Ok(());', body)
        self.assertIn('.filter(|l| !secret_env_line_matches_key(l, key))', body)
        self.assertIn('write_text_file_atomically(path, &(lines.join("\\n") + "\\n"))?;', body)

    def test_routes_rs_keeps_rust_regressions_for_secret_env_helpers(self):
        expected_tests = [
            'fn test_write_secret_env_quotes_special_values_and_updates_exact_key()',
            'fn test_remove_secret_env_only_removes_exact_key()',
            'fn test_write_secret_env_updates_trimmed_existing_key()',
            'fn test_remove_secret_env_matches_trimmed_existing_key()',
            'fn test_write_secret_env_rejects_multiline_values_without_mutating_file()',
            'fn test_write_text_file_atomically_replaces_contents_without_temp_leaks()',
        ]
        for test_name in expected_tests:
            with self.subTest(test_name=test_name):
                self.assertIn(test_name, self.source)


if __name__ == '__main__':
    unittest.main()
