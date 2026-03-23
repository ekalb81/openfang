#!/usr/bin/env python3
"""Guard channel env hot-reload against directory-shaped .env/secrets.env placeholders."""

from pathlib import Path
import tempfile

REPO_ROOT = Path(__file__).resolve().parents[1]
SOURCE = REPO_ROOT / "crates/openfang-api/src/channel_bridge.rs"


def load_helper_source() -> str:
    text = SOURCE.read_text()
    marker = "fn reload_env_file_for_channel_hot_reload("
    start = text.index(marker)
    end = text.index("fn hot_reload_env_snapshots()", start)
    return text[start:end]


def reload_env_file_for_channel_hot_reload(path: Path):
    if not path.is_file():
        return {}

    entries = {}
    for line in path.read_text().splitlines():
        trimmed = line.strip()
        if not trimmed or trimmed.startswith("#"):
            continue
        if "=" not in trimmed:
            continue
        key, value = trimmed.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key:
            continue
        entries[key] = value
    return entries


def main() -> None:
    helper = load_helper_source()
    assert "if !path.is_file()" in helper, "channel env hot-reload should require real files"
    assert "read_to_string(path)?" in helper, "expected helper to keep reading file contents"

    with tempfile.TemporaryDirectory() as tmp:
        home = Path(tmp)
        (home / "secrets.env").mkdir()
        (home / ".env").mkdir()

        assert reload_env_file_for_channel_hot_reload(home / "secrets.env") == {}
        assert reload_env_file_for_channel_hot_reload(home / ".env") == {}

        env_file = home / ".env.real"
        env_file.write_text("FIRST=1\n#ignored\nSECOND = two\n =bad\n")
        assert reload_env_file_for_channel_hot_reload(env_file) == {
            "FIRST": "1",
            "SECOND": "two",
        }

    print("ok: channel env hot-reload ignores non-file placeholders and still parses real files")


if __name__ == "__main__":
    main()
