import unittest
from pathlib import Path


CONFIG_RS = Path("crates/openfang-types/src/config.rs")


class ConfigValidateChannelEnvClusterParityTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = CONFIG_RS.read_text()

    def assert_warning_guard(self, channel_var: str, env_field: str, message: str):
        self.assertIn(f"std::env::var(&{channel_var}.{env_field})", self.source)
        self.assertIn(message, self.source)

    def test_validate_checks_line_channel_secret_env(self):
        self.assert_warning_guard("ln", "channel_secret_env", '"LINE configured but {} is not set"')

    def test_validate_checks_dingtalk_secret_env(self):
        self.assert_warning_guard("dt", "secret_env", '"DingTalk configured but {} is not set"')

    def test_validate_checks_dingtalk_stream_robot_code_env(self):
        self.assert_warning_guard(
            "ds",
            "robot_code_env",
            '"DingTalk Stream configured but {} is not set"',
        )

    def test_validate_checks_gotify_client_token_env(self):
        self.assert_warning_guard("gf", "client_token_env", '"Gotify configured but {} is not set"')

    def test_rust_regression_test_covers_added_warning_paths(self):
        self.assertIn("fn test_validate_missing_additional_channel_envs()", self.source)
        for expected in [
            "OPENFANG_TEST_NONEXISTENT_VAR_LINE_SECRET",
            "OPENFANG_TEST_NONEXISTENT_VAR_DINGTALK_SECRET",
            "OPENFANG_TEST_NONEXISTENT_VAR_DINGTALK_STREAM_ROBOT_CODE",
            "OPENFANG_TEST_NONEXISTENT_VAR_GOTIFY_CLIENT",
        ]:
            self.assertIn(expected, self.source)


if __name__ == "__main__":
    unittest.main()
