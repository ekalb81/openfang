import subprocess
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
STATIC_JS_DIR = REPO_ROOT / "crates/openfang-api/static/js"


def static_js_files() -> list[Path]:
    return sorted(path for path in STATIC_JS_DIR.rglob("*.js") if path.is_file())


class DashboardJavaScriptSyntaxTests(unittest.TestCase):
    def test_static_dashboard_javascript_files_parse_with_node(self):
        files = static_js_files()
        self.assertGreater(len(files), 0, "expected dashboard JavaScript assets to exist")

        failures: list[str] = []
        for path in files:
            result = subprocess.run(
                ["node", "--check", str(path)],
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
            )
            if result.returncode != 0:
                output = (result.stderr or result.stdout).strip()
                failures.append(f"{path.relative_to(REPO_ROOT)}\n{output}")

        if failures:
            self.fail("JavaScript syntax check failed:\n\n" + "\n\n".join(failures))


if __name__ == "__main__":
    unittest.main()
