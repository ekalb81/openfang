import re
import unittest
from pathlib import Path


CONFIG_RS = Path("crates/openfang-types/src/config.rs")

CHANNEL_STRUCTS = {
    "telegram": "TelegramConfig",
    "discord": "DiscordConfig",
    "slack": "SlackConfig",
    "whatsapp": "WhatsAppConfig",
    "matrix": "MatrixConfig",
    "email": "EmailConfig",
    "teams": "TeamsConfig",
    "mattermost": "MattermostConfig",
    "google_chat": "GoogleChatConfig",
    "twitch": "TwitchConfig",
    "rocketchat": "RocketChatConfig",
    "zulip": "ZulipConfig",
    "xmpp": "XmppConfig",
    "line": "LineConfig",
    "viber": "ViberConfig",
    "messenger": "MessengerConfig",
    "reddit": "RedditConfig",
    "mastodon": "MastodonConfig",
    "bluesky": "BlueskyConfig",
    "feishu": "FeishuConfig",
    "wecom": "WeComConfig",
    "revolt": "RevoltConfig",
    "nextcloud": "NextcloudConfig",
    "guilded": "GuildedConfig",
    "keybase": "KeybaseConfig",
    "threema": "ThreemaConfig",
    "nostr": "NostrConfig",
    "webex": "WebexConfig",
    "pumble": "PumbleConfig",
    "flock": "FlockConfig",
    "twist": "TwistConfig",
    "mumble": "MumbleConfig",
    "dingtalk": "DingTalkConfig",
    "dingtalk_stream": "DingTalkStreamConfig",
    "discourse": "DiscourseConfig",
    "gitter": "GitterConfig",
    "ntfy": "NtfyConfig",
    "gotify": "GotifyConfig",
    "webhook": "WebhookConfig",
    "linkedin": "LinkedInConfig",
}

# Intentional omissions: these env-backed fields are optional/alternate behavior and should not
# emit generic "configured but not set" warnings when absent.
INTENTIONAL_VALIDATE_EXCEPTIONS = {
    ("whatsapp", "gateway_url_env"),
    ("feishu", "encrypt_key_env"),
}


class ConfigValidateChannelEnvCoverageTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = CONFIG_RS.read_text()
        validate_start = cls.source.index("pub fn validate(&self) -> Vec<String> {")
        cls.validate_body = cls.source[validate_start:]

    def extract_struct_env_fields(self, struct_name: str) -> list[str]:
        match = re.search(rf"pub struct {struct_name} \{{(.*?)\n\}}", self.source, re.S)
        self.assertIsNotNone(match, f"Could not find {struct_name}")
        return re.findall(r"pub (\w+_env): (?:Option<)?String", match.group(1))

    def test_validate_covers_all_required_channel_env_fields(self):
        uncovered: list[tuple[str, str]] = []
        for channel_name, struct_name in CHANNEL_STRUCTS.items():
            for env_field in self.extract_struct_env_fields(struct_name):
                if (channel_name, env_field) in INTENTIONAL_VALIDATE_EXCEPTIONS:
                    continue
                expected = f"std::env::var(&"
                self.assertIn(expected, self.validate_body)
                if f".{env_field})" not in self.validate_body:
                    uncovered.append((channel_name, env_field))
        self.assertEqual(
            uncovered,
            [],
            f"KernelConfig::validate() is missing channel env warning coverage for: {uncovered}",
        )

    def test_intentional_exceptions_are_stable(self):
        for channel_name, env_field in INTENTIONAL_VALIDATE_EXCEPTIONS:
            struct_name = CHANNEL_STRUCTS[channel_name]
            self.assertIn(env_field, self.extract_struct_env_fields(struct_name))
            self.assertNotIn(f".{env_field})", self.validate_body)


if __name__ == "__main__":
    unittest.main()
