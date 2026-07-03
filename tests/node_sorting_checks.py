import unittest
from unittest import mock

import vpngate_manager


class NodeSortingTest(unittest.TestCase):
    def test_available_nodes_sort_by_latency_and_unavailable_nodes_are_last(self):
        nodes = [
            {
                "id": "unavailable-low-latency",
                "probe_status": "unavailable",
                "latency_ms": 1,
                "score": 9999,
                "probed_at": 100,
            },
            {
                "id": "residential-slow",
                "probe_status": "available",
                "latency_ms": 220,
                "ip_type": "residential",
                "score": 1000,
            },
            {
                "id": "active-middle",
                "active": True,
                "probe_status": "not_checked",
                "latency_ms": 80,
                "ip_type": "hosting",
                "score": 10,
            },
            {
                "id": "hosting-fast",
                "probe_status": "available",
                "latency_ms": 40,
                "ip_type": "hosting",
                "score": 20,
            },
            {
                "id": "pending-high-score",
                "probe_status": "not_checked",
                "ping": 1,
                "score": 99999,
            },
        ]

        ordered_ids = [node["id"] for node in vpngate_manager.sort_all_nodes(nodes)]

        self.assertEqual(
            ordered_ids,
            [
                "hosting-fast",
                "active-middle",
                "residential-slow",
                "pending-high-score",
                "unavailable-low-latency",
            ],
        )

    def test_tun_not_ready_proxy_failure_defers_auto_switch_during_start_grace(self):
        now = 1_000.0
        connected_at = now - (vpngate_manager.PROXY_HEALTH_STARTUP_GRACE_SECONDS - 1)
        self.assertTrue(
            vpngate_manager.should_defer_proxy_failure(
                "[错误代码 3004] [ERR_ROUTE_DEV_NOT_FOUND] 等待虚拟网卡 tun0 就绪超时",
                active_node_connected_at=connected_at,
                now=now,
            )
        )

    def test_tun_not_ready_proxy_failure_switches_after_start_grace(self):
        now = 1_000.0
        connected_at = now - (vpngate_manager.PROXY_HEALTH_STARTUP_GRACE_SECONDS + 1)
        self.assertFalse(
            vpngate_manager.should_defer_proxy_failure(
                "[错误代码 3004] [ERR_ROUTE_DEV_NOT_FOUND] 等待虚拟网卡 tun0 就绪超时",
                active_node_connected_at=connected_at,
                now=now,
            )
        )

    def test_regular_proxy_failure_switches_without_start_grace(self):
        now = 1_000.0
        connected_at = now - 1
        self.assertFalse(
            vpngate_manager.should_defer_proxy_failure(
                "出口连接测试失败",
                active_node_connected_at=connected_at,
                now=now,
            )
        )


    def test_load_ui_config_defaults_to_vpngate_egress(self):
        import tempfile
        from pathlib import Path
        from unittest import mock

        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(vpngate_manager, "DATA_DIR", Path(tmp)):
                cfg = vpngate_manager.load_ui_config()

        self.assertEqual(cfg["egress_mode"], "vpngate")
        self.assertEqual(cfg["warp_proxy_url"], "socks5://127.0.0.1:40000")

    def test_warp_egress_provider_returns_parsed_proxy_config(self):
        with mock.patch.object(
            vpngate_manager,
            "load_ui_config",
            return_value={
                "egress_mode": "warp",
                "warp_proxy_url": "socks5://127.0.0.1:40000",
            },
        ):
            self.assertEqual(
                vpngate_manager.get_egress_upstream_config(),
                ("socks", "127.0.0.1", 40000, None, None),
            )

    def test_vpngate_egress_provider_returns_none(self):
        with mock.patch.object(
            vpngate_manager,
            "load_ui_config",
            return_value={"egress_mode": "vpngate", "warp_proxy_url": "socks5://127.0.0.1:40000"},
        ):
            self.assertIsNone(vpngate_manager.get_egress_upstream_config())

    def test_switching_to_warp_stops_openvpn_and_clears_active_nodes(self):
        previous = {"egress_mode": "vpngate"}
        current = {"egress_mode": "warp", "warp_proxy_url": "socks5://127.0.0.1:40000"}
        nodes = [{"id": "node-a", "active": True}, {"id": "node-b", "active": False}]

        with mock.patch.object(vpngate_manager, "stop_active_openvpn") as stop_active, \
            mock.patch.object(vpngate_manager, "read_nodes", return_value=nodes), \
            mock.patch.object(vpngate_manager, "write_json") as write_json, \
            mock.patch.object(vpngate_manager, "set_state") as set_state:
            message = vpngate_manager.apply_egress_mode_transition(previous, current)

        stop_active.assert_called_once()
        written_nodes = write_json.call_args.args[1]
        self.assertEqual([node["active"] for node in written_nodes], [False, False])
        set_state.assert_called_once()
        self.assertIn("WARP", message)


if __name__ == "__main__":
    unittest.main()
