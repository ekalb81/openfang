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
CLI_REFERENCE_DOC = REPO_ROOT / "docs/cli-reference.md"
CLI_MAIN_RS = REPO_ROOT / "crates/openfang-cli/src/main.rs"
MODEL_CATALOG_RS = REPO_ROOT / "crates/openfang-runtime/src/model_catalog.rs"


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


def live_provider_count() -> int:
    text = MODEL_CATALOG_RS.read_text(encoding="utf-8")
    start = text.index("fn builtin_providers()")
    end = text.index("fn builtin_aliases()")
    return text[start:end].count("ProviderInfo {")


def live_model_count() -> int:
    text = MODEL_CATALOG_RS.read_text(encoding="utf-8")
    start = text.index("fn builtin_models()")
    return text[start:].count("ModelCatalogEntry {")


def live_alias_count() -> int:
    text = MODEL_CATALOG_RS.read_text(encoding="utf-8")
    start = text.index("fn builtin_aliases()")
    end = text.index("fn builtin_models()")
    return len(re.findall(r'^\s*\("', text[start:end], re.MULTILINE))


def first_count(pattern: str, path: Path, description: str) -> int:
    text = path.read_text(encoding="utf-8")
    match = re.search(pattern, text, re.IGNORECASE)
    if not match:
        raise AssertionError(f"Missing {description} in {path.relative_to(REPO_ROOT)}")
    return int(match.group(1))


def cli_channel_count() -> int:
    return first_count(r"(\d+)\s+channels\s+\\u\{00b7\}\s+60\s+skills", CLI_MAIN_RS, "CLI long_about channel count")


def cli_model_count() -> int:
    return first_count(r"60\s+skills\s+\\u\{00b7\}\s+(\d+)\s+models", CLI_MAIN_RS, "CLI long_about model count")


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
        self.assertEqual(expected, cli_channel_count())

    def test_provider_counts_match_live_model_catalog_across_docs(self):
        expected = live_provider_count()
        self.assertEqual(expected, readme_metric("LLM providers"))
        self.assertEqual(
            expected,
            first_count(r"(\d+)\s+LLM providers", README_DOC, "README intro provider count"),
        )
        self.assertEqual(provider_catalog_count(), expected)
        self.assertEqual(
            expected,
            first_count(r"catalog of \d+ models across (\d+) providers", API_REFERENCE_DOC, "API reference provider count"),
        )
        self.assertEqual(
            expected,
            first_count(r"Switch LLM providers\*\*: (\d+) providers supported", GETTING_STARTED_DOC, "getting started provider count"),
        )
        self.assertEqual(
            expected,
            first_count(r"Key features: \d+ channels, \d+ skills, (\d+) providers, \d+ models", PRODUCTION_CHECKLIST_DOC, "production checklist provider count"),
        )
        self.assertEqual(
            expected,
            first_count(r"Build ModelCatalog with \d+ builtin models, \d+ aliases, (\d+) providers", ARCHITECTURE_DOC, "architecture init provider count"),
        )
        self.assertEqual(
            expected,
            first_count(r"cover all (\d+) providers with \d+ builtin models", ARCHITECTURE_DOC, "architecture provider architecture count"),
        )
        self.assertEqual(
            expected,
            first_count(r"\*\*(\d+) providers\*\* with authentication status detection", ARCHITECTURE_DOC, "architecture registry provider count"),
        )
        self.assertEqual(
            expected,
            first_count(r"Returns all (\d+) providers with auth status and model counts", PROVIDERS_DOC, "providers guide response provider count"),
        )
        self.assertEqual(
            expected,
            first_count(r"Lists all (\d+) providers with their authentication status", PROVIDERS_DOC, "providers guide list provider count"),
        )

    def test_model_counts_match_live_model_catalog_across_docs(self):
        expected = live_model_count()
        self.assertEqual(expected, readme_metric("Models in catalog"))
        self.assertEqual(
            expected,
            first_count(r"\|\s*\[LLM Providers\]\(providers\.md\)\s*\|\s*\d+\s+providers,\s*(\d+)\s+models", README_DOC, "README providers summary model count"),
        )
        self.assertEqual(
            expected,
            first_count(r"\[ok\]\s+(\d+)\s+models available", CLI_REFERENCE_DOC, "CLI reference model count"),
        )
        self.assertEqual(expected, cli_model_count())
        self.assertEqual(
            expected,
            first_count(r"catalog of (\d+) models across \d+ providers", API_REFERENCE_DOC, "API reference model count"),
        )
        self.assertEqual(
            expected,
            first_count(r"Key features: \d+ channels, \d+ skills, \d+ providers, (\d+) models", PRODUCTION_CHECKLIST_DOC, "production checklist model count"),
        )
        self.assertEqual(
            expected,
            first_count(r"Build ModelCatalog with (\d+) builtin models, \d+ aliases, \d+ providers", ARCHITECTURE_DOC, "architecture init model count"),
        )
        self.assertEqual(
            expected,
            first_count(r"cover all \d+ providers with (\d+) builtin models", ARCHITECTURE_DOC, "architecture provider architecture model count"),
        )
        self.assertEqual(
            expected,
            first_count(r"\*\*(\d+) builtin models\*\* across", ARCHITECTURE_DOC, "architecture registry model count"),
        )
        self.assertEqual(
            expected,
            first_count(r"all (\d+) builtin models, sorted by provider", PROVIDERS_DOC, "providers guide catalog model count"),
        )
        self.assertEqual(
            expected,
            first_count(r"The (\d+) entries above are the builtin catalog", PROVIDERS_DOC, "providers guide builtin entries count"),
        )

    def test_alias_counts_match_live_model_catalog_across_docs(self):
        expected = live_alias_count()
        self.assertEqual(
            expected,
            first_count(r"\*\*(\d+) aliases\*\*", PROVIDERS_DOC, "providers guide intro alias count"),
        )
        self.assertEqual(
            expected,
            first_count(r"All (\d+) aliases resolve to canonical model IDs", PROVIDERS_DOC, "providers guide alias section count"),
        )
        self.assertEqual(
            expected,
            first_count(r"Build ModelCatalog with \d+ builtin models, (\d+) aliases, \d+ providers", ARCHITECTURE_DOC, "architecture init alias count"),
        )
        self.assertEqual(
            expected,
            first_count(r"\*\*(\d+) aliases\*\* for convenience", ARCHITECTURE_DOC, "architecture registry alias count"),
        )


if __name__ == "__main__":
    unittest.main()
