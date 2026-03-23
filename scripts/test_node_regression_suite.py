import subprocess
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
SCRIPT_TIMEOUT_SECONDS = 15


def discover_node_regression_scripts(root: Path) -> list[Path]:
    return sorted(
        path
        for path in root.rglob("test_*.js")
        if path.is_file()
    )


def run_node_regression_script(
    path: Path,
    timeout_seconds: float = SCRIPT_TIMEOUT_SECONDS,
) -> tuple[int, str]:
    try:
        result = subprocess.run(
            ["node", str(path)],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired as exc:
        output = "\n".join(
            part.strip()
            for part in (
                (exc.stdout or "") if isinstance(exc.stdout, str) else "",
                (exc.stderr or "") if isinstance(exc.stderr, str) else "",
            )
            if part and part.strip()
        )
        message = f"timed out after {timeout_seconds}s" + (f"\n{output}" if output else "")
        return (124, message)

    output = "\n".join(
        part for part in (result.stdout.strip(), result.stderr.strip()) if part
    )
    return (result.returncode, output)


class NodeRegressionSuiteTests(unittest.TestCase):
    def test_discover_node_regression_scripts_recurses_and_sorts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            nested_dir = root / "nested"
            deeper_dir = nested_dir / "deeper"
            deeper_dir.mkdir(parents=True)

            top_level = root / "test_top.js"
            nested = nested_dir / "test_nested.js"
            deeper = deeper_dir / "test_deeper.js"
            ignored = nested_dir / "helper.js"

            for path in (top_level, nested, deeper, ignored):
                path.write_text("// fixture\n", encoding="utf-8")

            self.assertEqual(
                discover_node_regression_scripts(root),
                [deeper, nested, top_level],
            )

    def test_run_node_regression_script_reports_timeouts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "test_hang.js"
            path.write_text("setTimeout(() => {}, 60_000);\n", encoding="utf-8")

            returncode, output = run_node_regression_script(path, timeout_seconds=0.01)

        self.assertEqual(returncode, 124)
        self.assertIn("timed out after 0.01s", output)

    def test_all_node_regression_scripts_pass(self) -> None:
        test_files = discover_node_regression_scripts(SCRIPTS_DIR)
        self.assertGreater(
            len(test_files),
            0,
            "expected at least one Node regression script under scripts/**/test_*.js",
        )

        failures: list[str] = []
        for path in test_files:
            returncode, output = run_node_regression_script(path)
            if returncode != 0:
                failures.append(
                    f"{path.relative_to(REPO_ROOT)} exited with {returncode}"
                    + (f"\n{output}" if output else "")
                )

        if failures:
            self.fail("\n\n".join(failures))


if __name__ == "__main__":
    unittest.main()
