import unittest
from pathlib import Path


CONFIG_RS = Path("crates/openfang-types/src/config.rs")


class ConfigValidateMatrixInviteSafetyTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = CONFIG_RS.read_text()

    def test_validate_warns_on_unrestricted_matrix_auto_accept(self):
        self.assertIn("if mx.auto_accept_invites && mx.allowed_rooms.is_empty()", self.source)
        self.assertIn(
            '"Matrix auto_accept_invites is enabled without allowed_rooms; the bot will join any invited room"',
            self.source,
        )

    def test_rust_regression_tests_cover_scoped_and_unscoped_cases(self):
        self.assertIn(
            "fn test_validate_warns_on_unrestricted_matrix_auto_accept_invites()",
            self.source,
        )
        self.assertIn(
            "fn test_validate_allows_scoped_matrix_auto_accept_invites()",
            self.source,
        )
        self.assertIn('allowed_rooms: vec!["!ops:matrix.org".to_string()]', self.source)


if __name__ == "__main__":
    unittest.main()
