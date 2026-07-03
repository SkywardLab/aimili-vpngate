import unittest
from unittest import mock

import proxy_server


class ProxyTunReadinessTest(unittest.TestCase):
    def test_waits_until_tun_interface_appears(self):
        attempts = []
        sleeps = []

        def exists(interface):
            attempts.append(interface)
            return len(attempts) == 3

        result = proxy_server.wait_for_tun_interface(
            "tun0",
            timeout=1.0,
            interval=0.1,
            exists=exists,
            sleep=sleeps.append,
            monotonic=lambda: len(attempts) * 0.1,
        )

        self.assertTrue(result)
        self.assertEqual(attempts, ["tun0", "tun0", "tun0"])
        self.assertEqual(sleeps, [0.1, 0.1])

    def test_stops_waiting_after_timeout(self):
        clock = [0.0]
        attempts = []

        def exists(interface):
            attempts.append(interface)
            return False

        def sleep(duration):
            clock[0] += duration

        result = proxy_server.wait_for_tun_interface(
            "tun0",
            timeout=0.25,
            interval=0.1,
            exists=exists,
            sleep=sleep,
            monotonic=lambda: clock[0],
        )

        self.assertFalse(result)
        self.assertGreaterEqual(clock[0], 0.25)
        self.assertEqual(attempts, ["tun0", "tun0", "tun0", "tun0"])

    def test_create_connection_waits_for_tun_before_dns(self):
        with mock.patch.object(proxy_server, "wait_for_tun_interface", return_value=False), \
            mock.patch.object(proxy_server, "resolve_dns_over_tun0") as resolve_dns:
            with self.assertRaisesRegex(OSError, "等待虚拟网卡 tun0 就绪超时"):
                proxy_server.create_connection(("example.com", 443), timeout=0.1)

        resolve_dns.assert_not_called()

    def tearDown(self):
        proxy_server.set_egress_upstream_provider(None)

    def test_create_connection_uses_egress_upstream_before_tun(self):
        sentinel = object()
        proxy_server.set_egress_upstream_provider(lambda: ("socks", "127.0.0.1", 40000, None, None))

        with mock.patch.object(proxy_server, "open_connection_via_upstream", return_value=sentinel) as open_upstream, \
            mock.patch.object(proxy_server, "wait_for_tun_interface") as wait_for_tun:
            result = proxy_server.create_connection(("example.com", 443), timeout=0.1)

        self.assertIs(result, sentinel)
        open_upstream.assert_called_once_with(
            ("socks", "127.0.0.1", 40000, None, None),
            ("example.com", 443),
            0.1,
        )
        wait_for_tun.assert_not_called()

    def test_create_connection_uses_tun_when_egress_upstream_is_empty(self):
        proxy_server.set_egress_upstream_provider(lambda: None)

        with mock.patch.object(proxy_server, "wait_for_tun_interface", return_value=False), \
            mock.patch.object(proxy_server, "open_connection_via_upstream") as open_upstream:
            with self.assertRaisesRegex(OSError, "等待虚拟网卡 tun0 就绪超时"):
                proxy_server.create_connection(("example.com", 443), timeout=0.1)

        open_upstream.assert_not_called()


if __name__ == "__main__":
    unittest.main()
