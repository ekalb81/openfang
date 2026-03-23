import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
API_ROUTES = REPO_ROOT / "crates/openfang-api/src/routes.rs"
CLI_CHANNELS = REPO_ROOT / "crates/openfang-cli/src/tui/screens/channels.rs"
CHANNEL_ADAPTER_DOCS = REPO_ROOT / "docs/channel-adapters.md"

DOC_CHANNEL_NAME_TO_ID = {
    "Telegram": "telegram",
    "Discord": "discord",
    "Slack": "slack",
    "WhatsApp": "whatsapp",
    "Signal": "signal",
    "Matrix": "matrix",
    "Email": "email",
    "Microsoft Teams": "teams",
    "Mattermost": "mattermost",
    "Google Chat": "google_chat",
    "Webex": "webex",
    "Feishu / Lark": "feishu",
    "WeCom": "wecom",
    "Rocket.Chat": "rocketchat",
    "Zulip": "zulip",
    "XMPP": "xmpp",
    "LINE": "line",
    "Viber": "viber",
    "Facebook Messenger": "messenger",
    "Mastodon": "mastodon",
    "Bluesky": "bluesky",
    "Reddit": "reddit",
    "LinkedIn": "linkedin",
    "Twitch": "twitch",
    "IRC": "irc",
    "Guilded": "guilded",
    "Revolt": "revolt",
    "Keybase": "keybase",
    "Discourse": "discourse",
    "Gitter": "gitter",
    "Nextcloud Talk": "nextcloud",
    "Threema": "threema",
    "Nostr": "nostr",
    "Mumble": "mumble",
    "Pumble": "pumble",
    "Flock": "flock",
    "Twist": "twist",
    "DingTalk": "dingtalk",
    "DingTalk Stream": "dingtalk_stream",
    "ntfy": "ntfy",
    "Gotify": "gotify",
    "Webhook": "webhook",
}


def channel_meta_blocks(text: str):
    parts = text.split("\n    ChannelMeta {")
    for part in parts[1:]:
        block = "    ChannelMeta {" + part
        next_idx = block.find("\n    ChannelMeta {")
        yield block if next_idx == -1 else block[:next_idx]


def parse_api_channel_metadata():
    text = API_ROUTES.read_text(encoding="utf-8")
    channels = {}
    for block in channel_meta_blocks(text):
        name_match = re.search(r'^\s*name:\s*"([^"]+)"', block, re.MULTILINE)
        if not name_match:
            continue
        name = name_match.group(1)
        required_env_vars = set()
        for field_body in re.findall(r'ChannelField\s*\{(.*?)\n\s*\},', block, re.DOTALL):
            env_match = re.search(r'env_var:\s*Some\("([^"]+)"\)', field_body)
            required_match = re.search(r'required:\s*(true|false)', field_body)
            if env_match and required_match and required_match.group(1) == "true":
                required_env_vars.add(env_match.group(1))

        template_match = re.search(r'config_template:\s*"((?:[^"\\]|\\.)*)"', block, re.DOTALL)
        if not template_match:
            raise AssertionError(f"Missing config_template for channel {name}")
        template = bytes(template_match.group(1), "utf-8").decode("unicode_escape")
        template_env_vars = set(re.findall(r'=\s*"([A-Z][A-Z0-9_]+)"', template))
        channels[name] = {
            "required_env_vars": required_env_vars,
            "template_env_vars": template_env_vars,
        }
    return channels


def parse_cli_channel_env_vars():
    text = CLI_CHANNELS.read_text(encoding="utf-8")
    pattern = re.compile(
        r'ChannelDef \{\s*name:\s*"([^"]+)",.*?env_vars:\s*&\[(.*?)\],', re.DOTALL
    )
    channels = {}
    for name, env_list_src in pattern.findall(text):
        env_vars = set(re.findall(r'"([A-Z][A-Z0-9_]+)"', env_list_src))
        channels[name] = env_vars
    return channels


def parse_doc_channel_overview_ids():
    text = CHANNEL_ADAPTER_DOCS.read_text(encoding="utf-8")
    section = text.split("## All 42 Channels", 1)[1].split("## Channel Configuration", 1)[0]
    channel_ids = []
    for line in section.splitlines():
        if not line.startswith("|"):
            continue
        name = line.strip().split("|", 2)[1].strip()
        if name in {"Channel", "---------"}:
            continue
        channel_ids.append(DOC_CHANNEL_NAME_TO_ID[name])
    return channel_ids


class ChannelMetadataConsistencyTests(unittest.TestCase):
    def test_api_and_cli_define_the_same_channel_set(self):
        api_channels = parse_api_channel_metadata()
        cli_channels = parse_cli_channel_env_vars()
        self.assertEqual(
            sorted(api_channels),
            sorted(cli_channels),
            "API channel metadata and CLI channel definitions drifted",
        )

    def test_required_api_secret_env_vars_appear_in_channel_setup_templates(self):
        api_channels = parse_api_channel_metadata()
        missing = {
            name: sorted(meta["required_env_vars"] - meta["template_env_vars"])
            for name, meta in api_channels.items()
            if meta["required_env_vars"] - meta["template_env_vars"]
        }
        self.assertEqual({}, missing)

    def test_cli_channel_env_hints_match_api_channel_setup_templates(self):
        api_channels = parse_api_channel_metadata()
        cli_channels = parse_cli_channel_env_vars()
        mismatches = {}
        for name, meta in api_channels.items():
            cli_envs = cli_channels[name]
            if cli_envs != meta["template_env_vars"]:
                mismatches[name] = {
                    "api_template": sorted(meta["template_env_vars"]),
                    "cli": sorted(cli_envs),
                }
        self.assertEqual({}, mismatches)

    def test_channel_adapter_docs_overview_matches_cli_channel_catalog(self):
        cli_channels = parse_cli_channel_env_vars()
        doc_channels = parse_doc_channel_overview_ids()
        self.assertEqual(
            sorted(cli_channels),
            sorted(doc_channels),
            "docs/channel-adapters.md overview drifted from the live channel catalog",
        )


if __name__ == "__main__":
    unittest.main()
