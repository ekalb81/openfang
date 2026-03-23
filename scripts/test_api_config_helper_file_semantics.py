import pathlib
import unittest


REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
ROUTES_RS = REPO_ROOT / "crates/openfang-api/src/routes.rs"


class ApiConfigHelperFileSemanticsTests(unittest.TestCase):
    def test_shared_helper_requires_regular_files(self):
        source = ROUTES_RS.read_text()
        self.assertIn("fn read_optional_regular_text_file(path: &std::path::Path)", source)
        self.assertIn("Ok(metadata) if metadata.is_file() => std::fs::read_to_string(path).map(Some)", source)
        self.assertIn("Ok(_) => Ok(None)", source)
        self.assertIn(
            "Err(err) if err.kind() == std::io::ErrorKind::NotFound => Ok(None)",
            source,
        )

    def test_config_helpers_use_shared_regular_file_reader(self):
        source = ROUTES_RS.read_text()
        for helper in (
            "upsert_provider_url",
            "upsert_channel_config",
            "remove_channel_config",
        ):
            marker = f"fn {helper}("
            start = source.index(marker)
            end = source.find("\nfn ", start + len(marker))
            if end == -1:
                end = len(source)
            block = source[start:end]
            self.assertIn("read_optional_regular_text_file(config_path)", block)
            self.assertNotIn("config_path.exists()", block)

    def test_api_config_set_route_ignores_directory_placeholders(self):
        source = ROUTES_RS.read_text()
        marker = "pub async fn config_set("
        start = source.index(marker)
        end = source.find("\npub async fn ", start + len(marker))
        if end == -1:
            end = len(source)
        block = source[start:end]
        self.assertIn("read_optional_regular_text_file(&config_path)", block)
        self.assertNotIn("config_path.exists()", block)

    def test_directory_placeholder_demo_matches_expected_semantics(self):
        workspace = REPO_ROOT / ".tmp_api_config_helper_file_semantics"
        if workspace.exists():
            if workspace.is_dir():
                for child in sorted(workspace.rglob('*'), reverse=True):
                    if child.is_file() or child.is_symlink():
                        child.unlink()
                    elif child.is_dir():
                        child.rmdir()
                workspace.rmdir()
            else:
                workspace.unlink()

        config_path = workspace / "config.toml"
        config_path.mkdir(parents=True)
        self.assertTrue(config_path.exists())
        self.assertFalse(config_path.is_file())

        # Cleanup
        config_path.rmdir()
        workspace.rmdir()


if __name__ == "__main__":
    unittest.main()
