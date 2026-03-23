import subprocess
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"


class NodeRegressionSuiteTests(unittest.TestCase):
    def test_all_node_regression_scripts_pass(self) -> None:
        test_files = sorted(
            path
            for path in SCRIPTS_DIR.glob("test_*.js")
            if path.is_file()
        )
        self.assertGreater(
            len(test_files),
            0,
            "expected at least one Node regression script under scripts/test_*.js",
        )

        failures: list[str] = []
        for path in test_files:
            result = subprocess.run(
                ["node", str(path)],
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
            )
            if result.returncode != 0:
                output = "\n".join(
                    part for part in (result.stdout.strip(), result.stderr.strip()) if part
                )
                failures.append(
                    f"{path.relative_to(REPO_ROOT)} exited with {result.returncode}"
                    + (f"\n{output}" if output else "")
                )

        if failures:
            self.fail("\n\n".join(failures))


if __name__ == "__main__":
    unittest.main()
