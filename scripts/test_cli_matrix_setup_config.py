import pathlib
import unittest


REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
CLI_MAIN_RS = REPO_ROOT / "crates/openfang-cli/src/main.rs"
CONFIG_RS = REPO_ROOT / "crates/openfang-types/src/config.rs"


class CliMatrixSetupConfigTests(unittest.TestCase):
    def test_matrix_setup_writes_supported_homeserver_key(self):
        source = CLI_MAIN_RS.read_text()
        self.assertIn('homeserver_url = {}', source)
        self.assertNotIn('homeserver_env = "MATRIX_HOMESERVER"', source)
        self.assertIn('auto_accept_invites = false', source)
        self.assertIn('toml::Value::String(homeserver.clone())', source)

    def test_matrix_config_still_expects_homeserver_url_field(self):
        source = CONFIG_RS.read_text()
        self.assertIn('pub homeserver_url: String,', source)
        self.assertNotIn('pub homeserver_env:', source)

    def test_matrix_setup_no_longer_persists_unused_homeserver_env_var(self):
        source = CLI_MAIN_RS.read_text()
        self.assertNotIn('dotenv::save_env_key("MATRIX_HOMESERVER", &homeserver)', source)
        self.assertNotIn('export MATRIX_HOMESERVER=', source)


if __name__ == "__main__":
    unittest.main()
