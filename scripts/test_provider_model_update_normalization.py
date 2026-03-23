import pathlib
import re
import unittest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]


class ProviderModelUpdateNormalizationTests(unittest.TestCase):
    def test_model_catalog_accepts_display_name_lookups(self):
        source = (REPO_ROOT / "crates/openfang-runtime/src/model_catalog.rs").read_text()

        self.assertIn(
            "/// Find a model by its canonical ID, display name, or alias.",
            source,
        )
        self.assertRegex(
            source,
            re.compile(
                r"find_model\(&self, id_or_alias: &str\) -> Option<&ModelCatalogEntry> \{"
                r".*?m\.id\.to_lowercase\(\) == lower"
                r".*?m\.display_name\.to_lowercase\(\) == lower"
                r".*?self\.aliases\.get\(&lower\)",
                re.S,
            ),
        )
        self.assertIn("fn test_find_model_by_display_name()", source)

    def test_set_agent_model_normalizes_catalog_entries_and_refreshes_auth_hint(self):
        source = (REPO_ROOT / "crates/openfang-kernel/src/kernel.rs").read_text()

        self.assertRegex(
            source,
            re.compile(
                r"pub fn set_agent_model\("
                r".*?let catalog_entry = self"
                r".*?catalog\.find_model\(model\)\.cloned\(\)"
                r".*?strip_provider_prefix\(&entry\.id, prov\)"
                r".*?let api_key_env = Some\(self\.config\.resolve_api_key_env\(&provider\)\);"
                r".*?update_model_provider_config\("
                r".*?api_key_env,"
                r".*?None,"
                r".*?info!\(agent_id = %agent_id, model = %normalized_model, provider = %provider, \"Agent model\+provider updated\"\);",
                re.S,
            ),
        )

    def test_patch_agent_config_routes_explicit_provider_updates_through_kernel_normalization(self):
        source = (REPO_ROOT / "crates/openfang-api/src/routes.rs").read_text()
        match = re.search(
            r"if let Some\(ref new_model\) = req\.model \{.*?\n    \}\n\n    // Update fallback model chain",
            source,
            re.S,
        )
        self.assertIsNotNone(match, "could not isolate patch_agent_config model update block")
        block = match.group(0)

        self.assertIn(
            "set_agent_model(agent_id, new_model, Some(new_provider))",
            block,
        )
        self.assertNotIn("update_model_and_provider(", block)
        self.assertIn(
            "so provider-specific auth/env hints stay in sync.",
            block,
        )

    def test_registry_helper_updates_provider_auth_hint_and_base_url_together(self):
        source = (REPO_ROOT / "crates/openfang-kernel/src/registry.rs").read_text()

        self.assertRegex(
            source,
            re.compile(
                r"pub fn update_model_provider_config\("
                r".*?api_key_env: Option<String>,"
                r".*?base_url: Option<String>,"
                r".*?entry\.manifest\.model\.model = new_model;"
                r".*?entry\.manifest\.model\.provider = new_provider;"
                r".*?entry\.manifest\.model\.api_key_env = api_key_env;"
                r".*?entry\.manifest\.model\.base_url = base_url;",
                re.S,
            ),
        )


if __name__ == "__main__":
    unittest.main()
