import unittest
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[1] / "install.sh"
TEXT = SOURCE.read_text(encoding="utf-8")


class InstallScriptContractTest(unittest.TestCase):
    def test_derivative_distributions_use_id_like(self):
        expected_markers = [
            "OS_ID_LIKE",
            "for os_family in $OS_TYPE $OS_ID_LIKE; do",
            'ubuntu|debian)',
            'PKG_MGR="apt-get"',
        ]
        for marker in expected_markers:
            with self.subTest(marker=marker):
                self.assertTrue(marker in TEXT, marker)

    def test_unsupported_message_mentions_compatible_derivatives(self):
        self.assertTrue("兼容衍生发行版" in TEXT)

    def test_default_repository_points_to_skywardlab(self):
        expected_markers = [
            "Default to the official repository (SkywardLab/aimili-vpngate)",
            'DEFAULT_USER="SkywardLab"',
            'DEFAULT_REPO="aimili-vpngate"',
        ]
        for marker in expected_markers:
            with self.subTest(marker=marker):
                self.assertTrue(marker in TEXT, marker)

    def test_web_ui_defaults_to_localhost(self):
        expected_markers = [
            '{"host": "127.0.0.1", "port": 8787',
            '"host": "127.0.0.1",',
            'echo -e "  * 网页控制面板:  ${BLUE}http://127.0.0.1:${UI_PORT}/${SECRET_PATH}/${PLAIN}"',
            "SSH 隧道",
        ]
        for marker in expected_markers:
            with self.subTest(marker=marker):
                self.assertTrue(marker in TEXT, marker)


if __name__ == "__main__":
    unittest.main()
