import pathlib
import unittest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
CLI_MAIN = REPO_ROOT / "crates/openfang-cli/src/main.rs"


class CliConfigFileSemanticsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = CLI_MAIN.read_text(encoding="utf-8")

    def test_cli_has_shared_regular_file_reader(self):
        self.assertIn(
            "fn read_optional_regular_text_file(",
            self.source,
            "CLI should centralize regular-file config reads",
        )
        self.assertIn(
            '"{} exists but is not a regular file: {}"',
            self.source,
            "CLI should report non-file config paths explicitly",
        )

    def test_doctor_uses_regular_file_reader_for_config_checks(self):
        self.assertGreaterEqual(
            self.source.count('read_optional_regular_text_file(&config_path, "Config file")'),
            4,
            "doctor/channel flows should share the regular-file config helper",
        )
        self.assertIn(
            'ui::hint("Remove or replace the non-file path before retrying.");',
            self.source,
            "doctor should explain how to recover from non-file config paths",
        )

    def test_channel_commands_do_not_fall_back_to_empty_config_on_read_failure(self):
        self.assertIn(
            'eprintln!("Error: {error}");',
            self.source,
            "channel list should surface config read failures instead of pretending nothing is configured",
        )
        self.assertIn(
            'ui::hint("Remove or replace the non-file path before editing channel config.");',
            self.source,
            "channel setup should stop before writing through a non-file config placeholder",
        )
        self.assertNotIn(
            'let config_str = std::fs::read_to_string(&config_path).unwrap_or_default();',
            self.source,
            "channel list should no longer treat failed config reads as an empty config",
        )
        self.assertNotIn(
            'let existing = std::fs::read_to_string(&config_path).unwrap_or_default();',
            self.source,
            "channel setup should no longer treat failed config reads as an empty config",
        )


if __name__ == "__main__":
    unittest.main()
