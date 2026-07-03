import types
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


class FakeSocket:
    def __init__(self, recv_chunks):
        self.recv_chunks = list(recv_chunks)
        self.sent = []
        self.closed = False

    def sendall(self, data):
        self.sent.append(data)

    def recv(self, size):
        if not self.recv_chunks:
            return b""
        chunk = self.recv_chunks.pop(0)
        data, rest = chunk[:size], chunk[size:]
        if rest:
            self.recv_chunks.insert(0, rest)
        return data

    def close(self):
        self.closed = True


class ProxyUpstreamHelperTest(unittest.TestCase):
    def test_egress_upstream_alias_uses_python38_compatible_typing_tuple(self):
        generic_alias = getattr(types, "GenericAlias", ())
        self.assertNotIsInstance(proxy_server.EgressUpstream, generic_alias)

    def test_open_socks5_upstream_negotiates_no_auth_and_connects(self):
        fake_sock = FakeSocket([
            b"\x05\x00",
            b"\x05\x00\x00\x01\x00\x00\x00\x00\x00\x00",
        ])

        with mock.patch.object(proxy_server, "connect_tcp", return_value=fake_sock) as connect_tcp:
            result = proxy_server.open_socks5_upstream(
                ("socks", "127.0.0.1", 40000, None, None),
                ("example.com", 443),
                0.5,
            )

        self.assertIs(result, fake_sock)
        self.assertFalse(fake_sock.closed)
        connect_tcp.assert_called_once_with("127.0.0.1", 40000, 0.5)
        self.assertEqual(fake_sock.sent[0], b"\x05\x01\x00")
        self.assertEqual(
            fake_sock.sent[1],
            b"\x05\x01\x00\x03\x0bexample.com\x01\xbb",
        )

    def test_open_http_upstream_connect_success_returns_socket(self):
        fake_sock = FakeSocket([b"HTTP/1.1 200 Connection Established\r\n\r\n"])

        with mock.patch.object(proxy_server, "connect_tcp", return_value=fake_sock):
            result = proxy_server.open_http_upstream(
                ("http", "127.0.0.1", 40000, None, None),
                ("example.com", 443),
                0.5,
            )

        self.assertIs(result, fake_sock)
        self.assertFalse(fake_sock.closed)
        self.assertEqual(
            fake_sock.sent[0],
            b"CONNECT example.com:443 HTTP/1.1\r\n"
            b"Host: example.com:443\r\n"
            b"Proxy-Connection: Keep-Alive\r\n\r\n",
        )

    def test_open_http_upstream_preserves_trailing_response_bytes(self):
        fake_sock = FakeSocket([b"HTTP/1.1 200 Connection Established\r\n\r\nPAYLOAD"])

        with mock.patch.object(proxy_server, "connect_tcp", return_value=fake_sock):
            result = proxy_server.open_http_upstream(
                ("http", "127.0.0.1", 40000, None, None),
                ("example.com", 443),
                0.5,
            )

        self.assertEqual(result.recv(7), b"PAYLOAD")
        self.assertFalse(fake_sock.closed)

    def test_open_http_upstream_connect_failure_closes_socket(self):
        fake_sock = FakeSocket([b"HTTP/1.1 407 Proxy Authentication Required\r\n\r\n"])

        with mock.patch.object(proxy_server, "connect_tcp", return_value=fake_sock):
            with self.assertRaisesRegex(OSError, "WARP HTTP proxy CONNECT failed"):
                proxy_server.open_http_upstream(
                    ("http", "127.0.0.1", 40000, None, None),
                    ("example.com", 443),
                    0.5,
                )

        self.assertTrue(fake_sock.closed)

    def test_open_socks5_upstream_rejected_auth_closes_socket(self):
        fake_sock = FakeSocket([b"\x05\xff"])

        with mock.patch.object(proxy_server, "connect_tcp", return_value=fake_sock):
            with self.assertRaisesRegex(OSError, "rejected authentication"):
                proxy_server.open_socks5_upstream(
                    ("socks", "127.0.0.1", 40000, None, None),
                    ("example.com", 443),
                    0.5,
                )

        self.assertTrue(fake_sock.closed)


if __name__ == "__main__":
    unittest.main()
