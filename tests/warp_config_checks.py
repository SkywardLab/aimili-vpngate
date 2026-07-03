import unittest

import vpn_utils


class WarpProxyUrlTest(unittest.TestCase):
    def test_accepts_socks5_endpoint(self):
        self.assertEqual(
            vpn_utils.parse_warp_proxy_url("socks5://127.0.0.1:40000"),
            ("socks", "127.0.0.1", 40000, None, None),
        )

    def test_accepts_http_endpoint_with_credentials(self):
        self.assertEqual(
            vpn_utils.parse_warp_proxy_url("http://user:pass@example.com:8080"),
            ("http", "example.com", 8080, "user", "pass"),
        )

    def test_accepts_socks_alias(self):
        self.assertEqual(
            vpn_utils.parse_warp_proxy_url("socks://localhost:1080"),
            ("socks", "localhost", 1080, None, None),
        )

    def test_rejects_missing_scheme(self):
        with self.assertRaisesRegex(ValueError, "WARP 代理地址必须使用"):
            vpn_utils.parse_warp_proxy_url("127.0.0.1:40000")

    def test_rejects_missing_host(self):
        with self.assertRaisesRegex(ValueError, "WARP 代理地址必须包含主机"):
            vpn_utils.parse_warp_proxy_url("socks5://:40000")

    def test_rejects_invalid_port(self):
        with self.assertRaisesRegex(ValueError, "WARP 代理端口范围必须是 1 至 65535"):
            vpn_utils.parse_warp_proxy_url("socks5://127.0.0.1:70000")


if __name__ == "__main__":
    unittest.main()
