import pathlib
import tempfile
import unittest


REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
VAULT_RS = REPO_ROOT / 'crates' / 'openfang-extensions' / 'src' / 'vault.rs'


class ExtensionVaultFileSemanticsTests(unittest.TestCase):
    def test_init_paths_require_real_files(self):
        source = VAULT_RS.read_text(encoding='utf-8')
        init_block = source.split('pub fn init(&mut self) -> ExtensionResult<()> {', 1)[1].split('        // Check if a master key is already available', 1)[0]
        init_with_key_block = source.split('pub fn init_with_key(&mut self, master_key: Zeroizing<[u8; 32]>) -> ExtensionResult<()> {', 1)[1].split('        self.entries.clear();', 1)[0]

        self.assertIn('self.path.is_file()', init_block)
        self.assertNotIn('self.path.exists()', init_block)
        self.assertIn('self.path.is_file()', init_with_key_block)
        self.assertNotIn('self.path.exists()', init_with_key_block)

    def test_directory_placeholders_do_not_count_as_initialized_vaults(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            vault_path = pathlib.Path(tmpdir) / 'vault.enc'
            vault_path.mkdir()

            self.assertFalse(vault_path.is_file())
            self.assertTrue(vault_path.exists())
            self.assertFalse(vault_path.is_file(), 'directory placeholder must not count as a real vault file')

            vault_path.rmdir()
            vault_path.write_text('vault-data', encoding='utf-8')

            self.assertTrue(vault_path.exists())
            self.assertTrue(vault_path.is_file(), 'real vault file should still count as initialized')


if __name__ == '__main__':
    unittest.main()
