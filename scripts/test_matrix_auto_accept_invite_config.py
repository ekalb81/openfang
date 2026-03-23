#!/usr/bin/env python3
"""Regression guard for Matrix auto-accept invite configuration wiring."""

from pathlib import Path
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
CONFIG_RS = REPO_ROOT / "crates/openfang-types/src/config.rs"
MATRIX_RS = REPO_ROOT / "crates/openfang-channels/src/matrix.rs"
CHANNEL_BRIDGE_RS = REPO_ROOT / "crates/openfang-api/src/channel_bridge.rs"


class MatrixAutoAcceptInviteConfigTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config_source = CONFIG_RS.read_text(encoding="utf-8")
        cls.matrix_source = MATRIX_RS.read_text(encoding="utf-8")
        cls.bridge_source = CHANNEL_BRIDGE_RS.read_text(encoding="utf-8")

    def test_matrix_config_exposes_opt_in_flag_with_false_default(self):
        self.assertIn("pub auto_accept_invites: bool,", self.config_source)
        self.assertIn("/// Whether to auto-accept room invites (default: false).", self.config_source)
        self.assertIn("#[serde(default)]\n    pub auto_accept_invites: bool,", self.config_source)
        self.assertIn("auto_accept_invites: false,", self.config_source)

    def test_adapter_constructor_accepts_configured_flag(self):
        self.assertIn("auto_accept_invites: bool,", self.matrix_source)
        self.assertIn("auto_accept_invites,", self.matrix_source)
        self.assertNotIn("auto_accept_invites: true,", self.matrix_source)

    def test_channel_bridge_threads_matrix_flag_into_adapter(self):
        self.assertIn("mx_config.auto_accept_invites,", self.bridge_source)
        self.assertIn("MatrixAdapter::new(", self.bridge_source)


if __name__ == "__main__":
    unittest.main()
