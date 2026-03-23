import subprocess
import tempfile
import unittest
from pathlib import Path
import re

REPO_ROOT = Path(__file__).resolve().parents[1]
STATIC_DIR = REPO_ROOT / "crates/openfang-api/static"
STATIC_JS_DIR = STATIC_DIR / "js"
NODE_CHECK_TIMEOUT_SECONDS = 15
INLINE_SCRIPT_RE = re.compile(r"<script\b[^>]*>(.*?)</script>", re.IGNORECASE | re.DOTALL)


def first_party_javascript_files() -> list[Path]:
    files = [
        path
        for path in STATIC_JS_DIR.rglob("*.js")
        if path.is_file()
    ]
    files.extend(
        path
        for path in STATIC_DIR.glob("*.js")
        if path.is_file()
    )
    return sorted(set(files))


def html_files() -> list[Path]:
    return sorted(path for path in STATIC_DIR.rglob("*.html") if path.is_file())


def inline_script_blocks(path: Path) -> list[tuple[int, str]]:
    html = path.read_text(encoding="utf-8")
    blocks: list[tuple[int, str]] = []
    for match in INLINE_SCRIPT_RE.finditer(html):
        script = match.group(1).strip()
        if not script:
            continue
        start_line = html.count("\n", 0, match.start()) + 1
        blocks.append((start_line, script))
    return blocks


def node_check(path: Path) -> str | None:
    try:
        result = subprocess.run(
            ["node", "--check", str(path)],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=NODE_CHECK_TIMEOUT_SECONDS,
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
        return (
            f"node --check timed out after {NODE_CHECK_TIMEOUT_SECONDS}s"
            + (f"\n{output}" if output else "")
        )

    if result.returncode == 0:
        return None
    return (result.stderr or result.stdout).strip()


class DashboardJavaScriptSyntaxTests(unittest.TestCase):
    def test_node_check_reports_timeouts(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "hang.js"
            path.write_text("const answer = 42;\n", encoding="utf-8")

            original_run = subprocess.run
            original_timeout = NODE_CHECK_TIMEOUT_SECONDS

            def fake_run(*args, **kwargs):
                raise subprocess.TimeoutExpired(
                    cmd=args[0],
                    timeout=kwargs.get("timeout", 0.01),
                )

            try:
                subprocess.run = fake_run
                globals()["NODE_CHECK_TIMEOUT_SECONDS"] = 0.01
                output = node_check(path)
            finally:
                subprocess.run = original_run
                globals()["NODE_CHECK_TIMEOUT_SECONDS"] = original_timeout

        self.assertIsNotNone(output)
        self.assertIn("node --check timed out after 0.01s", output)

    def test_first_party_dashboard_javascript_files_parse_with_node(self):
        files = first_party_javascript_files()
        self.assertGreater(len(files), 0, "expected first-party JavaScript assets to exist")

        failures: list[str] = []
        for path in files:
            output = node_check(path)
            if output:
                failures.append(f"{path.relative_to(REPO_ROOT)}\n{output}")

        if failures:
            self.fail("JavaScript syntax check failed:\n\n" + "\n\n".join(failures))

    def test_inline_static_html_scripts_parse_with_node(self):
        files = html_files()
        self.assertGreater(len(files), 0, "expected static HTML files to exist")

        failures: list[str] = []
        for path in files:
            for start_line, script in inline_script_blocks(path):
                with tempfile.NamedTemporaryFile(
                    mode="w",
                    suffix=".js",
                    encoding="utf-8",
                    delete=False,
                ) as handle:
                    temp_path = Path(handle.name)
                    handle.write(script)

                try:
                    output = node_check(temp_path)
                finally:
                    temp_path.unlink(missing_ok=True)

                if output:
                    failures.append(
                        f"{path.relative_to(REPO_ROOT)}:{start_line}\n{output}"
                    )

        if failures:
            self.fail("Inline script syntax check failed:\n\n" + "\n\n".join(failures))


if __name__ == "__main__":
    unittest.main()
