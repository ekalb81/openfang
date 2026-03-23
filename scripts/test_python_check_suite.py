import subprocess
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"


def discover_python_check_scripts(root: Path) -> list[Path]:
    return sorted(
        path
        for path in root.rglob("check_*.py")
        if path.is_file()
    )


class PythonCheckSuiteTests(unittest.TestCase):
    def test_discover_python_check_scripts_recurses_and_sorts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            nested_dir = root / "nested"
            deeper_dir = nested_dir / "deeper"
            deeper_dir.mkdir(parents=True)

            top_level = root / "check_top.py"
            nested = nested_dir / "check_nested.py"
            deeper = deeper_dir / "check_deeper.py"
            ignored = nested_dir / "test_helper.py"

            for path in (top_level, nested, deeper, ignored):
                path.write_text("print('fixture')\n", encoding="utf-8")

            self.assertEqual(
                discover_python_check_scripts(root),
                [top_level, nested, deeper],
            )

    def test_all_python_check_scripts_pass(self) -> None:
        check_files = discover_python_check_scripts(SCRIPTS_DIR)
        self.assertGreater(
            len(check_files),
            0,
            "expected at least one Python checker under scripts/**/check_*.py",
        )

        failures: list[str] = []
        for path in check_files:
            result = subprocess.run(
                ["python3", str(path)],
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
