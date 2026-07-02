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

    def test_web_ui_github_links_point_to_current_repository(self):
        expected_links = [
            "https://github.com/SkywardLab/aimili-vpngate",
            "https://github.com/SkywardLab/aimili-vpngate/tree/bate",
        ]
        for link in expected_links:
            with self.subTest(link=link):
                self.assertTrue(link in TEXT, link)
        self.assertTrue("github.com/baoweise-bot/aimili-vpngate" not in TEXT)


    def test_node_table_displays_latency_column(self):
        expected_markers = [
            '<th style="width: 100px;">延迟</th>',
            '<td><span class="latency-cell">${latencyText}</span></td>',
            'colspan="7"',
        ]
        for marker in expected_markers:
            with self.subTest(marker=marker):
                self.assertTrue(marker in TEXT, marker)

    def test_unavailable_node_latency_displays_dash(self):
        expected_markers = [
            "function formatNodeLatency(n) {",
            'if (!n || n.probe_status === "unavailable") return "-";',
            'const latencyText = formatNodeLatency(n);',
        ]
        for marker in expected_markers:
            with self.subTest(marker=marker):
                self.assertTrue(marker in TEXT, marker)

    def test_api_nodes_response_uses_sorted_nodes(self):
        self.assertTrue("nodes = sort_all_nodes(nodes)" in TEXT)

    def test_frontend_node_sort_uses_status_and_latency(self):
        expected_markers = [
            "function nodeDisplayRank(n) {",
            'if (n.active || n.probe_status === "available") return 0;',
            "function nodeLatencyValue(n) {",
            "const latencyDelta = nodeLatencyValue(a) - nodeLatencyValue(b);",
        ]
        for marker in expected_markers:
            with self.subTest(marker=marker):
                self.assertTrue(marker in TEXT, marker)
        self.assertTrue("const aScore = a.score || 0;" not in TEXT)

    def test_batch_node_latency_test_button_and_script_exist(self):
        expected_markers = [
            'id="btn_test_all_nodes"',
            "测试全部节点",
            "async function testAllFilteredNodes()",
            'fetch("./api/test_nodes"',
            "const batchSize = MANUAL_TEST_NODE_LIMIT;",
            "for (let i = 0; i < ids.length; i += batchSize)",
            "检测中 ${done}/${ids.length}",
        ]
        for marker in expected_markers:
            with self.subTest(marker=marker):
                self.assertTrue(marker in TEXT, marker)

    def test_web_ui_runtime_defaults_to_localhost(self):
        expected_markers = [
            'UI_HOST = os.environ.get("UI_HOST", "127.0.0.1")',
            '"host": UI_HOST,',
        ]
        for marker in expected_markers:
            with self.subTest(marker=marker):
                self.assertTrue(marker in TEXT, marker)



if __name__ == "__main__":
    unittest.main()
