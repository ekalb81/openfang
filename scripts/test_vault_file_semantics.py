import pathlib
import unittest


REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
VAULT_SOURCE = REPO_ROOT / "crates/openfang-extensions/src/vault.rs"
CLI_SOURCE = REPO_ROOT / "crates/openfang-cli/src/main.rs"
KERNEL_SOURCE = REPO_ROOT / "crates/openfang-kernel/src/kernel.rs"


class VaultFileSemanticsTests(unittest.TestCase):
    def test_vault_loader_requires_real_vault_file(self):
        source = VAULT_SOURCE.read_text()
        self.assertIn("pub fn exists(&self) -> bool {\n        self.path.is_file()", source)
        self.assertIn("if !self.path.is_file() {", source)

    def test_cli_and_kernel_only_treat_real_vault_files_as_present(self):
        cli = CLI_SOURCE.read_text()
        kernel = KERNEL_SOURCE.read_text()
        self.assertIn("if vault_path.is_file() {", cli)
        self.assertIn("if !vault_path.is_file() {", cli)
        self.assertNotIn("if vault_path.exists() {", cli)
        self.assertNotIn("if !vault_path.exists() {", cli)
        self.assertIn("let vault = if vault_path.is_file() {", cli)
        self.assertIn("let vault = if vault_path.is_file() {", kernel)
        self.assertNotIn("let vault = if vault_path.exists() {", kernel)

    def test_directory_placeholder_is_not_treated_as_vault_file(self):
        workspace = REPO_ROOT / ".tmp_vault_file_semantics"
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

        vault_dir = workspace / "vault.enc"
        workspace.mkdir(parents=True)
        vault_dir.mkdir()

        self.assertTrue(vault_dir.exists())
        self.assertFalse(vault_dir.is_file())

        vault_dir.rmdir()
        workspace.rmdir()


if __name__ == "__main__":
    unittest.main()
