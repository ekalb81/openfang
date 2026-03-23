import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
CHANNEL_BRIDGE_RS = REPO_ROOT / 'crates/openfang-api/src/channel_bridge.rs'


class ChannelBridgeManifestFileSemanticsTest(unittest.TestCase):
    def test_source_requires_real_manifest_file(self):
        source = CHANNEL_BRIDGE_RS.read_text(encoding='utf-8')
        self.assertIn('if !manifest_path.is_file()', source)
        self.assertNotIn('if !manifest_path.exists()', source)

    def test_directory_placeholder_is_not_a_valid_manifest(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            manifest_path = Path(tmpdir) / 'agents' / 'demo' / 'agent.toml'
            manifest_path.mkdir(parents=True)

            self.assertTrue(manifest_path.exists())
            self.assertFalse(manifest_path.is_file())

    def test_regular_file_still_counts_as_manifest(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            manifest_path = Path(tmpdir) / 'agents' / 'demo' / 'agent.toml'
            manifest_path.parent.mkdir(parents=True)
            manifest_path.write_text('name = "demo"\n', encoding='utf-8')

            self.assertTrue(manifest_path.exists())
            self.assertTrue(manifest_path.is_file())


if __name__ == '__main__':
    unittest.main()
