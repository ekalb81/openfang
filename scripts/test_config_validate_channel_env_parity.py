import unittest
from pathlib import Path


CONFIG_RS = Path("crates/openfang-types/src/config.rs")


class ConfigValidateChannelEnvParityTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = CONFIG_RS.read_text()

    def assert_warning_guard(self, channel_var: str, env_field: str, message: str):
        block = (
            f'if let Some(ref {channel_var}) = self.channels.'
        )
        self.assertIn(block, self.source)
        self.assertIn(f'std::env::var(&{channel_var}.{env_field})', self.source)
        self.assertIn(message, self.source)

    def test_validate_checks_whatsapp_verify_token_env(self):
        self.assert_warning_guard("wa", "verify_token_env", '"WhatsApp configured but {} is not set"')

    def test_validate_checks_messenger_verify_token_env(self):
        self.assert_warning_guard("ms", "verify_token_env", '"Messenger configured but {} is not set"')

    def test_validate_checks_reddit_password_env(self):
        self.assert_warning_guard("rd", "password_env", '"Reddit configured but {} is not set"')

    def test_regression_test_covers_added_warning_paths(self):
        self.assertIn("fn test_validate_missing_webhook_and_reddit_channel_envs()", self.source)
        for expected in [
            "OPENFANG_TEST_NONEXISTENT_VAR_WA_VERIFY",
            "OPENFANG_TEST_NONEXISTENT_VAR_MESSENGER_VERIFY",
            "OPENFANG_TEST_NONEXISTENT_VAR_REDDIT_PASSWORD",
        ]:
            self.assertIn(expected, self.source)


if __name__ == "__main__":
    unittest.main()
