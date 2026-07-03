import unittest
from pathlib import Path
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

    def test_validate_egress_settings_accepts_warp(self):
        self.assertEqual(
            vpngate_manager.validate_egress_settings("warp", "http://127.0.0.1:8080"),
            ("warp", "http://127.0.0.1:8080"),
        )

    def test_validate_egress_settings_rejects_unknown_mode(self):
        with self.assertRaisesRegex(ValueError, "无效的出站核心"):
            vpngate_manager.validate_egress_settings("other", "socks5://127.0.0.1:40000")

    def test_validate_egress_settings_rejects_bad_warp_url(self):
        with self.assertRaisesRegex(ValueError, "WARP 代理地址必须使用"):
            vpngate_manager.validate_egress_settings("warp", "127.0.0.1:40000")

    def test_update_settings_wires_egress_transition_and_provider_startup(self):
        source = Path(vpngate_manager.__file__).read_text(encoding="utf-8")
        self.assertIn('egress_mode_raw = str(payload.get("egress_mode") or DEFAULT_EGRESS_MODE).strip()', source)
        self.assertIn('warp_proxy_url_raw = str(payload.get("warp_proxy_url") or DEFAULT_WARP_PROXY_URL).strip()', source)
        self.assertIn('previous_ui_cfg = dict(ui_cfg)', source)
        self.assertIn('egress_message = apply_egress_mode_transition(previous_ui_cfg, ui_cfg)', source)
        self.assertIn('proxy_server.set_egress_upstream_provider(get_egress_upstream_config)', source)

    def test_prepare_vpngate_connect_switches_warp_mode_to_vpngate(self):
        cfg = {"egress_mode": "warp", "warp_proxy_url": "socks5://127.0.0.1:40000"}
        updated = vpngate_manager.prepare_vpngate_connect_config(cfg)
        self.assertEqual(updated["egress_mode"], "vpngate")
        self.assertEqual(updated["warp_proxy_url"], "socks5://127.0.0.1:40000")

    def test_warp_mode_suppresses_vpngate_background_paths(self):
        source = Path(vpngate_manager.__file__).read_text(encoding="utf-8")
        self.assertIn('if ui_cfg.get("egress_mode", DEFAULT_EGRESS_MODE) == "warp":', source)
        self.assertIn('暂停 VPNGate 自动切换', source)
        self.assertIn('if egress_mode == "vpngate" and sys.platform.startswith("linux") and not tun_path.exists():', source)

    def test_failed_vpngate_connect_from_warp_restores_warp_config(self):
        import tempfile

        previous_cfg = {
            "egress_mode": "warp",
            "warp_proxy_url": "socks5://127.0.0.1:40000",
            "routing_mode": "auto",
        }
        ui_auth_writes = []

        def capture_write(path, data):
            if Path(path).name == "ui_auth.json":
                ui_auth_writes.append(dict(data))

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            node = {
                "id": "node-a",
                "config_file": str(tmp_path / "node-a.ovpn"),
                "config_text": "client",
            }
            with mock.patch.object(vpngate_manager, "DATA_DIR", tmp_path), \
                mock.patch.object(vpngate_manager, "CONFIG_DIR", tmp_path / "configs"), \
                mock.patch.object(vpngate_manager, "load_ui_config", return_value=previous_cfg), \
                mock.patch.object(vpngate_manager, "read_nodes", return_value=[node]), \
                mock.patch.object(vpngate_manager, "validate_node_allowed_by_routing"), \
                mock.patch.object(vpngate_manager, "write_json", side_effect=capture_write), \
                mock.patch.object(vpngate_manager, "apply_egress_mode_transition"), \
                mock.patch.object(vpngate_manager, "set_state"), \
                mock.patch.object(vpngate_manager, "log_to_json"), \
                mock.patch.object(vpngate_manager, "stop_active_openvpn"), \
                mock.patch.object(vpngate_manager, "run_openvpn_until_ready", return_value=(False, "openvpn failed", None)), \
                mock.patch.object(vpngate_manager, "clear_active_connection_state"):
                with self.assertRaisesRegex(RuntimeError, "openvpn failed"):
                    vpngate_manager.connect_node("node-a")

        self.assertGreaterEqual(len(ui_auth_writes), 2)
        self.assertEqual(ui_auth_writes[0]["egress_mode"], "vpngate")
        self.assertEqual(ui_auth_writes[-1]["egress_mode"], "warp")
        self.assertEqual(ui_auth_writes[-1]["warp_proxy_url"], "socks5://127.0.0.1:40000")

    def test_automatic_maintenance_skips_vpngate_testing_in_warp_mode(self):
        with mock.patch.object(vpngate_manager, "ensure_dirs"), \
            mock.patch.object(vpngate_manager, "load_ui_config", return_value={"egress_mode": "warp"}), \
            mock.patch.object(vpngate_manager, "set_state"), \
            mock.patch.object(vpngate_manager, "fetch_candidates") as fetch_candidates, \
            mock.patch.object(vpngate_manager, "test_multiple_nodes") as test_multiple_nodes:
            result = vpngate_manager.maintain_valid_nodes(force=False)

        self.assertIn("WARP", result)
        fetch_candidates.assert_not_called()
        test_multiple_nodes.assert_not_called()



if __name__ == "__main__":
    unittest.main()
