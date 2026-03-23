import tempfile
import unittest
from pathlib import Path


TEMPLATES_RS = Path("crates/openfang-cli/src/templates.rs")


class CliTemplateManifestFileSemanticsTests(unittest.TestCase):
    def test_cli_loader_uses_real_file_semantics_for_template_manifests(self):
        source = TEMPLATES_RS.read_text()
        self.assertIn('if !manifest.is_file() {', source)
        self.assertNotIn('if !manifest.exists() {', source)

    def test_directory_named_agent_toml_is_not_a_valid_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            template_dir = Path(tmp) / 'agents' / 'example'
            fake_manifest_dir = template_dir / 'agent.toml'
            fake_manifest_dir.mkdir(parents=True)

            self.assertTrue(fake_manifest_dir.exists())
            self.assertFalse(fake_manifest_dir.is_file())


if __name__ == '__main__':
    unittest.main()
