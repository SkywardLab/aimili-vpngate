import unittest
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[1] / "vpngate_manager.py"
TEXT = SOURCE.read_text(encoding="utf-8")


class UiContractTest(unittest.TestCase):
    def test_vps_purchase_recommendation_ui_is_removed(self):
        removed_markers = [
            "vps_recommend_modal",
            "vps-recommend-tab",
            "VPS 购买推荐",
            "VPS购买推荐",
            "openVpsModal",
            "closeVpsModal",
            "my.racknerd.com/aff.php",
            "bandwagonhost.com/aff.php",
        ]
        for marker in removed_markers:
            with self.subTest(marker=marker):
                self.assertTrue(marker not in TEXT, marker)

    def test_apple_design_tokens_are_applied_to_main_ui(self):
        expected_tokens = [
            "--primary: #0066cc;",
            "--primary-focus: #0071e3;",
            "--bg-dark: #f5f5f7;",
            "--bg-surface: #ffffff;",
            "--text-primary: #1d1d1f;",
            "--text-secondary: #7a7a7a;",
            "border-radius: 9999px;",
            "font-size: 17px;",
            "transform: scale(0.95);",
        ]
        for token in expected_tokens:
            with self.subTest(token=token):
                self.assertTrue(token in TEXT, token)

    def test_legacy_gradient_glass_theme_is_removed_from_primary_chrome(self):
        legacy_markers = [
            "#6366f1",
            "--primary-gradient",
            "radial-gradient(at 0% 0%",
            "translateY(-1px)",
            "box-shadow: 0 4px 12px rgba(99, 102, 241, 0.2);",
        ]
        for marker in legacy_markers:
            with self.subTest(marker=marker):
                self.assertTrue(marker not in TEXT, marker)


if __name__ == "__main__":
    unittest.main()
