import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
README_DOC = REPO_ROOT / "docs/README.md"
CHANNEL_ADAPTER_DOCS = REPO_ROOT / "docs/channel-adapters.md"
PROVIDERS_DOC = REPO_ROOT / "docs/providers.md"
API_REFERENCE_DOC = REPO_ROOT / "docs/api-reference.md"
CONFIGURATION_DOC = REPO_ROOT / "docs/configuration.md"
ARCHITECTURE_DOC = REPO_ROOT / "docs/architecture.md"
PRODUCTION_CHECKLIST_DOC = REPO_ROOT / "docs/production-checklist.md"
GETTING_STARTED_DOC = REPO_ROOT / "docs/getting-started.md"


def readme_metric(name: str) -> int:
    text = README_DOC.read_text(encoding="utf-8")
    match = re.search(rf"\|\s*{re.escape(name)}\s*\|\s*(\d+)\s*\|", text)
    if not match:
        raise AssertionError(f"Missing README metric row for {name}")
    return int(match.group(1))


def readme_channel_mentions() -> list[int]:
    text = README_DOC.read_text(encoding="utf-8")
    matches = re.findall(r"(\d+)\s+(?:messaging\s+)?channels", text, re.IGNORECASE)
    if not matches:
        raise AssertionError("README channel counts not found")
    return [int(value) for value in matches]


def channel_catalog_count() -> int:
    text = CHANNEL_ADAPTER_DOCS.read_text(encoding="utf-8")
    overview = text.split("## All ", 1)[1].split("## Channel Configuration", 1)[0]
    count = 0
    for line in overview.splitlines():
        if not line.startswith("|"):
            continue
        first_cell = line.strip().split("|", 2)[1].strip()
        if first_cell in {"Channel", "---------"}:
            continue
        count += 1
    return count


def provider_catalog_count() -> int:
    text = PROVIDERS_DOC.read_text(encoding="utf-8")
    match = re.search(r"LLM Providers \((\d+)\):", text)
    if not match:
        raise AssertionError("Missing provider count header in docs/providers.md")
    return int(match.group(1))


def first_count(pattern: str, path: Path, description: str) -> int:
    text = path.read_text(encoding="utf-8")
    match = re.search(pattern, text, re.IGNORECASE)
    if not match:
        raise AssertionError(f"Missing {description} in {path.relative_to(REPO_ROOT)}")
    return int(match.group(1))


class DocsCatalogCountTests(unittest.TestCase):
    def test_readme_channel_counts_match_live_channel_catalog(self):
        expected = channel_catalog_count()
        self.assertEqual(expected, readme_metric("Messaging channels"))
        self.assertEqual([expected, expected], readme_channel_mentions())

    def test_other_docs_channel_counts_match_live_channel_catalog(self):
        expected = channel_catalog_count()
        self.assertEqual(
            expected,
            first_count(r"Supports\s+(\d+)\s+channel adapters", API_REFERENCE_DOC, "API reference channel count"),
        )
        self.assertEqual(
            expected,
            first_count(r"All\s+(\d+)\s+channel adapters", CONFIGURATION_DOC, "configuration channel count"),
        )
        self.assertEqual(
            expected,
            first_count(r"openfang-channels\s+(\d+)\s+channel adapters", ARCHITECTURE_DOC, "architecture channel count"),
        )
        self.assertEqual(
            expected,
            first_count(r"Key features:\s+(\d+)\s+channels", PRODUCTION_CHECKLIST_DOC, "production checklist channel count"),
        )
        self.assertEqual(
            expected,
            first_count(r"Connect any of\s+(\d+)\s+messaging platforms", GETTING_STARTED_DOC, "getting started channel count"),
        )

    def test_readme_provider_count_matches_provider_guide(self):
        self.assertEqual(provider_catalog_count(), readme_metric("LLM providers"))


if __name__ == "__main__":
    unittest.main()
