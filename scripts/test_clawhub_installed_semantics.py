import pathlib
import unittest


ROUTES = pathlib.Path(__file__).resolve().parents[1] / "crates" / "openfang-api" / "src" / "routes.rs"


class ClawHubInstalledSemanticsTest(unittest.TestCase):
    def test_search_and_browse_use_client_installed_helper(self):
        source = ROUTES.read_text()
        self.assertIn(
            'let installed = client.is_installed(&e.slug, &skills_dir);',
            source,
            'clawhub_search should derive installed state from the shared helper',
        )
        self.assertIn(
            'let installed = client.is_installed(&entry.slug, &skills_dir);',
            source,
            'clawhub_browse should derive installed state from the shared helper',
        )

    def test_search_and_browse_no_longer_treat_any_existing_slug_path_as_installed(self):
        source = ROUTES.read_text()
        self.assertNotIn(
            'skills_dir.join(&e.slug).exists()',
            source,
            'search results should not treat arbitrary existing paths as installed skills',
        )
        self.assertNotIn(
            'skills_dir.join(&entry.slug).exists()',
            source,
            'browse results should not treat arbitrary existing paths as installed skills',
        )


if __name__ == '__main__':
    unittest.main()
