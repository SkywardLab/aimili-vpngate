# Optional WARP Egress Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a selectable Cloudflare WARP egress mode that forwards the built-in local proxy through a user-configured local WARP HTTP/SOCKS endpoint.

**Architecture:** Keep VPNGate/OpenVPN as the default egress mode and add WARP as a configuration-driven upstream proxy path. `vpngate_manager.py` owns persisted settings, UI state, API validation, and lifecycle transitions; `vpn_utils.py` owns WARP URL parsing; `proxy_server.py` owns upstream dialing for SOCKS5/HTTP WARP endpoints.

**Tech Stack:** Python 3 standard library, `unittest`, existing single-file HTML/JS in `vpngate_manager.py`, existing local HTTP/SOCKS5 proxy in `proxy_server.py`.

---

## File Structure

- Modify `vpn_utils.py`: add WARP proxy URL parser and validation helper.
- Modify `proxy_server.py`: add egress upstream provider, SOCKS5 upstream connect, HTTP CONNECT upstream connect, and route `create_connection()` through the provider when WARP is active.
- Modify `vpngate_manager.py`: add defaults, config migration, state fields, lifecycle transition helper, provider wiring, API fields, and UI fields.
- Modify `tests/proxy_readiness_checks.py`: add proxy upstream provider tests.
- Modify `tests/node_sorting_checks.py`: add manager config and lifecycle tests.
- Modify `tests/ui_contract_checks.py`: add Web UI contract markers for WARP controls.
- Create `tests/warp_config_checks.py`: focused parser tests for WARP endpoint validation.

---

### Task 1: WARP Endpoint Parser

**Files:**
- Modify: `vpn_utils.py`
- Create: `tests/warp_config_checks.py`

- [ ] **Step 1: Write the failing parser tests**

Create `tests/warp_config_checks.py` with:

```python
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
```

- [ ] **Step 2: Run parser tests to verify RED**

Run:

```bash
python3 -m unittest tests.warp_config_checks -v
```

Expected: FAIL with `AttributeError: module 'vpn_utils' has no attribute 'parse_warp_proxy_url'`.

- [ ] **Step 3: Implement minimal parser**

Append this helper near the existing proxy parsing helpers in `vpn_utils.py`, after `parse_proxy_endpoint()`:

```python
def parse_warp_proxy_url(value: str) -> tuple[str, str, int, str | None, str | None]:
    raw = str(value or "").strip()
    parsed = urllib.parse.urlsplit(raw)
    scheme = parsed.scheme.lower()
    if scheme not in ("socks5", "socks", "http", "https"):
        raise ValueError("WARP 代理地址必须使用 socks5://、socks://、http:// 或 https://")
    if not parsed.hostname:
        raise ValueError("WARP 代理地址必须包含主机")
    try:
        port = parsed.port
    except ValueError as exc:
        raise ValueError("WARP 代理端口范围必须是 1 至 65535") from exc
    if port is None or port < 1 or port > 65535:
        raise ValueError("WARP 代理端口范围必须是 1 至 65535")
    proxy_type = "socks" if scheme in ("socks5", "socks") else "http"
    username = urllib.parse.unquote(parsed.username) if parsed.username is not None else None
    password = urllib.parse.unquote(parsed.password) if parsed.password is not None else None
    return proxy_type, parsed.hostname, port, username, password
```

`vpn_utils.py` already imports `urllib.parse`; use that import.

- [ ] **Step 4: Run parser tests to verify GREEN**

Run:

```bash
python3 -m unittest tests.warp_config_checks -v
```

Expected: PASS all 6 tests.

- [ ] **Step 5: Commit parser**

```bash
git add vpn_utils.py tests/warp_config_checks.py
git commit -m "Add WARP proxy URL parser"
```

---

### Task 2: Manager Defaults and Runtime State

**Files:**
- Modify: `vpngate_manager.py`
- Modify: `tests/node_sorting_checks.py`

- [ ] **Step 1: Write failing tests for config defaults and provider config**

Append these tests to `NodeSortingTest` in `tests/node_sorting_checks.py`:

```python
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
```

Ensure the top of `tests/node_sorting_checks.py` imports `mock`:

```python
from unittest import mock
```

- [ ] **Step 2: Run manager config tests to verify RED**

Run:

```bash
python3 -m unittest tests.node_sorting_checks.NodeSortingTest.test_load_ui_config_defaults_to_vpngate_egress tests.node_sorting_checks.NodeSortingTest.test_warp_egress_provider_returns_parsed_proxy_config tests.node_sorting_checks.NodeSortingTest.test_vpngate_egress_provider_returns_none -v
```

Expected: FAIL because `egress_mode`, `warp_proxy_url`, and `get_egress_upstream_config()` are missing.

- [ ] **Step 3: Add constants and defaults**

In `vpngate_manager.py`, after `PROXY_HEALTH_STARTUP_GRACE_SECONDS`, add:

```python
DEFAULT_EGRESS_MODE = "vpngate"
DEFAULT_WARP_PROXY_URL = "socks5://127.0.0.1:40000"
VALID_EGRESS_MODES = {"vpngate", "warp"}
```

In `load_ui_config()`, add keys to the `config` dict after `fav_fail_fallback`:

```python
            "fav_fail_fallback": False,
            "egress_mode": DEFAULT_EGRESS_MODE,
            "warp_proxy_url": DEFAULT_WARP_PROXY_URL,
```

Update the missing-key migration list to include the new keys:

```python
                for key in ["host", "port", "proxy_port", "routing_mode", "force_country", "routing_ip_type", "connection_enabled", "fixed_node_id", "favorite_node_ids", "fav_fail_fallback", "egress_mode", "warp_proxy_url"]:
                    if key not in data:
                        updated = True
```

After proxy port normalization in `load_ui_config()`, add:

```python
        if config.get("egress_mode") not in VALID_EGRESS_MODES:
            config["egress_mode"] = DEFAULT_EGRESS_MODE
            updated = True

        try:
            vpn_utils.parse_warp_proxy_url(str(config.get("warp_proxy_url") or DEFAULT_WARP_PROXY_URL))
        except ValueError:
            config["warp_proxy_url"] = DEFAULT_WARP_PROXY_URL
            updated = True
```

- [ ] **Step 4: Add provider helper and state fields**

In `vpngate_manager.py`, after `get_state()`, add:

```python
def get_egress_upstream_config() -> tuple[str, str, int, str | None, str | None] | None:
    ui_cfg = load_ui_config()
    if ui_cfg.get("egress_mode", DEFAULT_EGRESS_MODE) != "warp":
        return None
    return vpn_utils.parse_warp_proxy_url(str(ui_cfg.get("warp_proxy_url") or DEFAULT_WARP_PROXY_URL))
```

Inside `get_state()`, after `state["fav_fail_fallback"] = False`, add:

```python
    state["egress_mode"] = ui_cfg.get("egress_mode", DEFAULT_EGRESS_MODE)
    state["warp_proxy_url"] = ui_cfg.get("warp_proxy_url", DEFAULT_WARP_PROXY_URL)
    state["egress_label"] = "WARP" if state["egress_mode"] == "warp" else "VPNGate"
```

- [ ] **Step 5: Run manager config tests to verify GREEN**

Run:

```bash
python3 -m unittest tests.node_sorting_checks.NodeSortingTest.test_load_ui_config_defaults_to_vpngate_egress tests.node_sorting_checks.NodeSortingTest.test_warp_egress_provider_returns_parsed_proxy_config tests.node_sorting_checks.NodeSortingTest.test_vpngate_egress_provider_returns_none -v
```

Expected: PASS all 3 tests.

- [ ] **Step 6: Commit manager defaults**

```bash
git add vpngate_manager.py tests/node_sorting_checks.py
git commit -m "Add WARP egress configuration defaults"
```

---

### Task 3: Proxy Upstream Provider

**Files:**
- Modify: `proxy_server.py`
- Modify: `tests/proxy_readiness_checks.py`

- [ ] **Step 1: Write failing proxy provider tests**

Append these tests to `ProxyTunReadinessTest` in `tests/proxy_readiness_checks.py`:

```python
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
```

- [ ] **Step 2: Run proxy provider tests to verify RED**

Run:

```bash
python3 -m unittest tests.proxy_readiness_checks.ProxyTunReadinessTest.test_create_connection_uses_egress_upstream_before_tun tests.proxy_readiness_checks.ProxyTunReadinessTest.test_create_connection_uses_tun_when_egress_upstream_is_empty -v
```

Expected: FAIL because `set_egress_upstream_provider()` and `open_connection_via_upstream()` are missing.

- [ ] **Step 3: Add provider plumbing**

In `proxy_server.py`, update the typing import:

```python
from typing import Any, Callable
```

After `proxy_connection_sem = threading.BoundedSemaphore(MAX_PROXY_CONNECTIONS)`, add:

```python
EgressUpstream = tuple[str, str, int, str | None, str | None]
egress_upstream_provider: Callable[[], EgressUpstream | None] | None = None


def set_egress_upstream_provider(provider: Callable[[], EgressUpstream | None] | None) -> None:
    global egress_upstream_provider
    egress_upstream_provider = provider


def current_egress_upstream() -> EgressUpstream | None:
    if egress_upstream_provider is None:
        return None
    return egress_upstream_provider()
```

- [ ] **Step 4: Add upstream dialing helpers**

In `proxy_server.py`, after `parse_host_port()`, add:

```python
def connect_tcp(host: str, port: int, timeout: float) -> socket.socket:
    err = None
    for res in socket.getaddrinfo(host, port, 0, socket.SOCK_STREAM):
        af, socktype, proto, canonname, sa = res
        sock = None
        try:
            sock = socket.socket(af, socktype, proto)
            sock.settimeout(timeout)
            sock.connect(sa)
            return sock
        except OSError as exc:
            err = exc
            if sock is not None:
                sock.close()
    if err is not None:
        raise err
    raise OSError("getaddrinfo returns empty list")


def socks5_address_bytes(host: str) -> bytes:
    try:
        return b"\x01" + socket.inet_aton(host)
    except OSError:
        pass
    try:
        return b"\x04" + socket.inet_pton(socket.AF_INET6, host)
    except OSError:
        pass
    encoded = host.encode("idna")
    if len(encoded) > 255:
        raise OSError("SOCKS5 target host is too long")
    return b"\x03" + bytes([len(encoded)]) + encoded


def open_socks5_upstream(
    upstream: EgressUpstream,
    address: tuple[str, int],
    timeout: float,
) -> socket.socket:
    _, proxy_host, proxy_port, username, password = upstream
    target_host, target_port = address
    sock = connect_tcp(proxy_host, proxy_port, timeout)
    try:
        if username is None:
            sock.sendall(b"\x05\x01\x00")
        else:
            sock.sendall(b"\x05\x01\x02")
        greeting = recv_exact(sock, 2)
        if greeting[0] != 5 or greeting[1] == 0xFF:
            raise OSError("WARP SOCKS5 proxy rejected authentication methods")
        if greeting[1] == 2:
            user_bytes = (username or "").encode("utf-8")
            pass_bytes = (password or "").encode("utf-8")
            if len(user_bytes) > 255 or len(pass_bytes) > 255:
                raise OSError("WARP SOCKS5 credentials are too long")
            sock.sendall(b"\x01" + bytes([len(user_bytes)]) + user_bytes + bytes([len(pass_bytes)]) + pass_bytes)
            auth_reply = recv_exact(sock, 2)
            if auth_reply != b"\x01\x00":
                raise OSError("WARP SOCKS5 authentication failed")
        request = b"\x05\x01\x00" + socks5_address_bytes(target_host) + int(target_port).to_bytes(2, "big")
        sock.sendall(request)
        reply = recv_exact(sock, 4)
        if reply[0] != 5 or reply[1] != 0:
            raise OSError(f"WARP SOCKS5 connect failed with code {reply[1] if len(reply) > 1 else 'unknown'}")
        address_type = reply[3]
        if address_type == 1:
            recv_exact(sock, 4)
        elif address_type == 3:
            recv_exact(sock, recv_exact(sock, 1)[0])
        elif address_type == 4:
            recv_exact(sock, 16)
        else:
            raise OSError("WARP SOCKS5 returned invalid address type")
        recv_exact(sock, 2)
        return sock
    except Exception:
        sock.close()
        raise


def open_http_upstream(
    upstream: EgressUpstream,
    address: tuple[str, int],
    timeout: float,
) -> socket.socket:
    _, proxy_host, proxy_port, username, password = upstream
    target_host, target_port = address
    sock = connect_tcp(proxy_host, proxy_port, timeout)
    try:
        authority = f"[{target_host}]:{target_port}" if ":" in target_host else f"{target_host}:{target_port}"
        auth_header = ""
        if username is not None:
            token = base64.b64encode(f"{username}:{password or ''}".encode("utf-8")).decode("ascii")
            auth_header = f"Proxy-Authorization: Basic {token}\r\n"
        request = (
            f"CONNECT {authority} HTTP/1.1\r\n"
            f"Host: {authority}\r\n"
            f"{auth_header}"
            "Proxy-Connection: Keep-Alive\r\n\r\n"
        )
        sock.sendall(request.encode("iso-8859-1"))
        response = b""
        while b"\r\n\r\n" not in response and len(response) < 65536:
            chunk = sock.recv(4096)
            if not chunk:
                break
            response += chunk
        status_line = response.split(b"\r\n", 1)[0].decode("iso-8859-1", errors="replace")
        parts = status_line.split(" ", 2)
        if len(parts) < 2 or parts[1] != "200":
            raise OSError(f"WARP HTTP proxy CONNECT failed: {status_line}")
        return sock
    except Exception:
        sock.close()
        raise


def open_connection_via_upstream(
    upstream: EgressUpstream,
    address: tuple[str, int],
    timeout: float,
) -> socket.socket:
    proxy_type = upstream[0]
    if proxy_type == "socks":
        return open_socks5_upstream(upstream, address, timeout)
    if proxy_type == "http":
        return open_http_upstream(upstream, address, timeout)
    raise OSError(f"Unsupported WARP proxy type: {proxy_type}")
```

- [ ] **Step 5: Route `create_connection()` through provider**

At the top of `create_connection()` in `proxy_server.py`, after `host, port = address`, add:

```python
    upstream = current_egress_upstream()
    if upstream is not None:
        return open_connection_via_upstream(upstream, (host, port), timeout)
```

- [ ] **Step 6: Run proxy provider tests to verify GREEN**

Run:

```bash
python3 -m unittest tests.proxy_readiness_checks -v
```

Expected: PASS all proxy readiness tests.

- [ ] **Step 7: Commit proxy provider**

```bash
git add proxy_server.py tests/proxy_readiness_checks.py
git commit -m "Route proxy connections through optional WARP upstream"
```

---

### Task 4: WARP Lifecycle Transition

**Files:**
- Modify: `vpngate_manager.py`
- Modify: `tests/node_sorting_checks.py`

- [ ] **Step 1: Write failing lifecycle test**

Append this test to `NodeSortingTest` in `tests/node_sorting_checks.py`:

```python
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
```

- [ ] **Step 2: Run lifecycle test to verify RED**

Run:

```bash
python3 -m unittest tests.node_sorting_checks.NodeSortingTest.test_switching_to_warp_stops_openvpn_and_clears_active_nodes -v
```

Expected: FAIL because `apply_egress_mode_transition()` is missing.

- [ ] **Step 3: Implement lifecycle helper**

In `vpngate_manager.py`, after `enforce_active_node_allowed_by_routing()`, add:

```python
def apply_egress_mode_transition(previous_cfg: dict[str, Any], current_cfg: dict[str, Any]) -> str | None:
    previous_mode = previous_cfg.get("egress_mode", DEFAULT_EGRESS_MODE)
    current_mode = current_cfg.get("egress_mode", DEFAULT_EGRESS_MODE)
    if previous_mode == current_mode:
        return None
    if current_mode == "warp":
        stop_active_openvpn()
        with lock:
            nodes = read_nodes()
            for item in nodes:
                item["active"] = False
            write_json(NODES_FILE, nodes)
        message = "已切换至 WARP 出站核心，VPNGate 活动连接已停止"
        set_state(
            active_openvpn_node_id="",
            active_node_latency="WARP",
            proxy_ok=False,
            proxy_ip="-",
            proxy_latency_ms=0,
            proxy_error="正在检测 WARP 出口连通性",
            last_check_message=message,
        )
        log_to_json("INFO", "Routing", message)
        return message
    if current_mode == "vpngate":
        message = "已切换至 VPNGate 出站核心，可手动连接节点或等待自动维护"
        set_state(last_check_message=message)
        log_to_json("INFO", "Routing", message)
        return message
    return None
```

- [ ] **Step 4: Run lifecycle test to verify GREEN**

Run:

```bash
python3 -m unittest tests.node_sorting_checks.NodeSortingTest.test_switching_to_warp_stops_openvpn_and_clears_active_nodes -v
```

Expected: PASS.

- [ ] **Step 5: Commit lifecycle helper**

```bash
git add vpngate_manager.py tests/node_sorting_checks.py
git commit -m "Apply WARP egress lifecycle transition"
```

---

### Task 5: Settings API and Provider Wiring

**Files:**
- Modify: `vpngate_manager.py`
- Modify: `tests/node_sorting_checks.py`

- [ ] **Step 1: Write failing validation tests**

Append these tests to `NodeSortingTest` in `tests/node_sorting_checks.py`:

```python
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
```

- [ ] **Step 2: Run validation tests to verify RED**

Run:

```bash
python3 -m unittest tests.node_sorting_checks.NodeSortingTest.test_validate_egress_settings_accepts_warp tests.node_sorting_checks.NodeSortingTest.test_validate_egress_settings_rejects_unknown_mode tests.node_sorting_checks.NodeSortingTest.test_validate_egress_settings_rejects_bad_warp_url -v
```

Expected: FAIL because `validate_egress_settings()` is missing.

- [ ] **Step 3: Implement settings validator**

In `vpngate_manager.py`, after `get_egress_upstream_config()`, add:

```python
def validate_egress_settings(egress_mode: str, warp_proxy_url: str) -> tuple[str, str]:
    mode = str(egress_mode or DEFAULT_EGRESS_MODE).strip().lower()
    if mode not in VALID_EGRESS_MODES:
        raise ValueError("无效的出站核心")
    warp_url = str(warp_proxy_url or DEFAULT_WARP_PROXY_URL).strip()
    vpn_utils.parse_warp_proxy_url(warp_url)
    return mode, warp_url
```

- [ ] **Step 4: Run validation tests to verify GREEN**

Run:

```bash
python3 -m unittest tests.node_sorting_checks.NodeSortingTest.test_validate_egress_settings_accepts_warp tests.node_sorting_checks.NodeSortingTest.test_validate_egress_settings_rejects_unknown_mode tests.node_sorting_checks.NodeSortingTest.test_validate_egress_settings_rejects_bad_warp_url -v
```

Expected: PASS.

- [ ] **Step 5: Wire API update_settings**

In `/api/update_settings`, after reading `routing_ip_type`, add:

```python
                egress_mode_raw = str(payload.get("egress_mode") or DEFAULT_EGRESS_MODE).strip()
                warp_proxy_url_raw = str(payload.get("warp_proxy_url") or DEFAULT_WARP_PROXY_URL).strip()
                try:
                    egress_mode, warp_proxy_url = validate_egress_settings(egress_mode_raw, warp_proxy_url_raw)
                except ValueError as exc:
                    self.send_json({"ok": False, "error": str(exc)}, HTTPStatus.BAD_REQUEST)
                    return
```

After `ui_cfg = load_ui_config()`, save the previous config:

```python
                previous_ui_cfg = dict(ui_cfg)
```

Before writing `ui_cfg` to disk, assign:

```python
                ui_cfg["egress_mode"] = egress_mode
                ui_cfg["warp_proxy_url"] = warp_proxy_url
```

After `write_json(auth_file, ui_cfg)`, replace the single policy message assignment with:

```python
                egress_message = apply_egress_mode_transition(previous_ui_cfg, ui_cfg)
                policy_message = None
                if egress_mode == "vpngate":
                    policy_message = enforce_active_node_allowed_by_routing(ui_cfg, "路由设置已更新")
```

In the non-restart response branch, keep:

```python
                    message = egress_message or policy_message or "配置更新成功，已即时生效！"
                    self.send_json({"ok": True, "restart_needed": False, "message": message})
```

- [ ] **Step 6: Wire proxy provider in main startup**

In `main()`, after `sys.stderr = tee`, add:

```python
    proxy_server.set_egress_upstream_provider(get_egress_upstream_config)
```

In the initial `write_json(STATE_FILE, {...})` payload, add:

```python
            "egress_mode": load_ui_config().get("egress_mode", DEFAULT_EGRESS_MODE),
            "egress_label": "WARP" if load_ui_config().get("egress_mode", DEFAULT_EGRESS_MODE) == "warp" else "VPNGate",
```

- [ ] **Step 7: Run focused manager tests**

Run:

```bash
python3 -m unittest tests.node_sorting_checks -v
```

Expected: PASS all node sorting and manager helper tests.

- [ ] **Step 8: Commit API wiring**

```bash
git add vpngate_manager.py tests/node_sorting_checks.py
git commit -m "Persist WARP egress settings through API"
```

---

### Task 6: Web UI Controls

**Files:**
- Modify: `vpngate_manager.py`
- Modify: `tests/ui_contract_checks.py`

- [ ] **Step 1: Write failing UI contract test**

Append this test to `UiContractTest` in `tests/ui_contract_checks.py`:

```python
    def test_warp_egress_controls_exist(self):
        expected_markers = [
            'id="net_egress_mode"',
            'id="net_warp_proxy_url"',
            'Cloudflare WARP',
            'function setEgressMode(value)',
            'function handleEgressModeChange(mode)',
            'egress_mode: egressMode',
            'warp_proxy_url: warpProxyUrl',
            'state.egress_label',
        ]
        for marker in expected_markers:
            with self.subTest(marker=marker):
                self.assertTrue(marker in TEXT, marker)
```

- [ ] **Step 2: Run UI contract test to verify RED**

Run:

```bash
python3 -m unittest tests.ui_contract_checks.UiContractTest.test_warp_egress_controls_exist -v
```

Expected: FAIL because the WARP UI markers are missing.

- [ ] **Step 3: Add egress controls to the network modal**

In the `<form id="network_form" onsubmit="saveNetwork(event)">` block, immediately before `<input type="hidden" id="net_routing_mode" value="auto">`, insert:

```html
            <input type="hidden" id="net_egress_mode" value="vpngate">
            <div class="form-group">
              <label>出站核心</label>
              <div class="option-group" id="egress_mode_group">
                <div class="option-card active" data-value="vpngate" onclick="setEgressMode('vpngate')">
                  <div class="option-title">VPNGate 节点</div>
                  <div class="option-desc">使用当前 OpenVPN 节点、地区锁定、收藏和自动切换能力。</div>
                </div>
                <div class="option-card" data-value="warp" onclick="setEgressMode('warp')">
                  <div class="option-title">Cloudflare WARP</div>
                  <div class="option-desc">通过本机 WARP HTTP/SOCKS 代理作为出口。</div>
                </div>
              </div>
            </div>
            <div class="form-group" id="net_warp_proxy_group" style="display:none;">
              <label for="net_warp_proxy_url">WARP 代理地址</label>
              <input type="text" id="net_warp_proxy_url" placeholder="socks5://127.0.0.1:40000">
              <div class="hint">请先在本机启动 WARP 本地代理，例如 wireproxy 或 warp-cli 对应的代理端口。</div>
            </div>
```

- [ ] **Step 4: Add JavaScript handlers**

In `selectOptionCard(groupName, value)`, add an `egress_mode` branch before the `routing_mode` branch:

```javascript
  if (groupName === 'egress_mode') {
    const input = $("net_egress_mode");
    if (input) input.value = value;

    const cards = document.querySelectorAll("#egress_mode_group .option-card");
    cards.forEach(card => {
      if (card.getAttribute("data-value") === value) {
        card.classList.add("active");
      } else {
        card.classList.remove("active");
      }
    });

    handleEgressModeChange(value);
  } else if (groupName === 'routing_mode') {
```

Add these functions after `setRoutingIpType(value)`:

```javascript
function setEgressMode(value) {
  selectOptionCard('egress_mode', value);
}

function handleEgressModeChange(mode) {
  const warpGroup = $("net_warp_proxy_group");
  const warningDiv = $("net_routing_warning");
  if (warpGroup) {
    warpGroup.style.display = mode === "warp" ? "block" : "none";
  }
  if (mode === "warp" && warningDiv) {
    warningDiv.style.color = "var(--warning)";
    warningDiv.style.background = "rgba(245, 158, 11, 0.1)";
    warningDiv.style.border = "1px solid rgba(245, 158, 11, 0.2)";
    warningDiv.innerHTML = `⚠️ <strong>WARP 出站</strong>：当前本地代理将通过配置的 WARP 本地代理端口出站，VPNGate 节点自动切换会暂停。`;
  }
}
```

In `openNetworkModal()`, after setting `proxy_port`, add:

```javascript
    const egressMode = state.egress_mode || "vpngate";
    $("net_warp_proxy_url").value = state.warp_proxy_url || "socks5://127.0.0.1:40000";
    selectOptionCard('egress_mode', egressMode);
```

In `saveNetwork(e)`, after `const routingIpType = $("net_routing_ip_type").value;`, add:

```javascript
  const egressMode = $("net_egress_mode").value;
  const warpProxyUrl = $("net_warp_proxy_url").value.trim() || "socks5://127.0.0.1:40000";
```

In the `fetch("./api/update_settings"` body, add:

```javascript
        egress_mode: egressMode,
        warp_proxy_url: warpProxyUrl
```

- [ ] **Step 5: Add status display marker**

In the gateway status rendering area, add a display that references `state.egress_label`, for example near the active routing status:

```javascript
  const egressLabel = state.egress_label || (state.egress_mode === "warp" ? "WARP" : "VPNGate");
```

Render the label with text containing:

```html
出站核心: ${esc(egressLabel)}
```

- [ ] **Step 6: Run UI contract test to verify GREEN**

Run:

```bash
python3 -m unittest tests.ui_contract_checks.UiContractTest.test_warp_egress_controls_exist -v
```

Expected: PASS.

- [ ] **Step 7: Commit UI controls**

```bash
git add vpngate_manager.py tests/ui_contract_checks.py
git commit -m "Add WARP egress controls to Web UI"
```

---

### Task 7: Connect Flow and Health Behavior

**Files:**
- Modify: `vpngate_manager.py`
- Modify: `tests/node_sorting_checks.py`

- [ ] **Step 1: Write failing connect-mode helper tests**

Append this test to `NodeSortingTest` in `tests/node_sorting_checks.py`:

```python
    def test_prepare_vpngate_connect_switches_warp_mode_to_vpngate(self):
        cfg = {"egress_mode": "warp", "warp_proxy_url": "socks5://127.0.0.1:40000"}
        updated = vpngate_manager.prepare_vpngate_connect_config(cfg)
        self.assertEqual(updated["egress_mode"], "vpngate")
        self.assertEqual(updated["warp_proxy_url"], "socks5://127.0.0.1:40000")
```

- [ ] **Step 2: Run connect helper test to verify RED**

Run:

```bash
python3 -m unittest tests.node_sorting_checks.NodeSortingTest.test_prepare_vpngate_connect_switches_warp_mode_to_vpngate -v
```

Expected: FAIL because `prepare_vpngate_connect_config()` is missing.

- [ ] **Step 3: Implement connect helper**

In `vpngate_manager.py`, after `validate_egress_settings()`, add:

```python
def prepare_vpngate_connect_config(ui_cfg: dict[str, Any]) -> dict[str, Any]:
    updated = dict(ui_cfg)
    updated["egress_mode"] = "vpngate"
    updated.setdefault("warp_proxy_url", DEFAULT_WARP_PROXY_URL)
    return updated
```

In `connect_node()`, replace:

```python
        ui_cfg = load_ui_config()
        validate_node_allowed_by_routing(node, ui_cfg)
        ui_cfg["connection_enabled"] = True
```

with:

```python
        loaded_ui_cfg = load_ui_config()
        ui_cfg = prepare_vpngate_connect_config(loaded_ui_cfg)
        validate_node_allowed_by_routing(node, ui_cfg)
        ui_cfg["connection_enabled"] = True
```

After writing `ui_cfg`, add:

```python
        apply_egress_mode_transition(loaded_ui_cfg, ui_cfg)
```

- [ ] **Step 4: Update background behavior for WARP mode**

In `auto_switch_node()`, after loading `ui_cfg`, add:

```python
    if ui_cfg.get("egress_mode", DEFAULT_EGRESS_MODE) == "warp":
        print("[自动切换] 当前处于 WARP 出站模式，暂停 VPNGate 自动切换。", flush=True)
        return
```

In `reconnect_fixed_node_if_needed(ui_cfg)`, add at the start:

```python
    if ui_cfg.get("egress_mode", DEFAULT_EGRESS_MODE) == "warp":
        return False
```

In `check_proxy_health()`, guard the tun0 check so WARP mode skips the Linux tun0 requirement:

```python
    ui_cfg = load_ui_config()
    egress_mode = ui_cfg.get("egress_mode", DEFAULT_EGRESS_MODE)
```

Then change:

```python
    if sys.platform.startswith("linux") and not tun_path.exists():
```

into:

```python
    if egress_mode == "vpngate" and sys.platform.startswith("linux") and not tun_path.exists():
```

- [ ] **Step 5: Run connect helper test to verify GREEN**

Run:

```bash
python3 -m unittest tests.node_sorting_checks.NodeSortingTest.test_prepare_vpngate_connect_switches_warp_mode_to_vpngate -v
```

Expected: PASS.

- [ ] **Step 6: Commit connect and health behavior**

```bash
git add vpngate_manager.py tests/node_sorting_checks.py
git commit -m "Coordinate WARP mode with VPNGate connect flow"
```

---

### Task 8: Final Verification and Documentation Touch-Up

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Add README note**

In the Chinese quick-start network settings section, add:

```markdown
* **☁️ 可选 WARP 出站**：如果您已在 VPS 本机启动 Cloudflare WARP 本地代理（例如 `socks5://127.0.0.1:40000`），可在“管理员 -> 代理及网络设置”中将出站核心切换为 **Cloudflare WARP**，本地 `7928` 代理端口会转发到该 WARP 出口。
```

In the English quick-start network settings section, add:

```markdown
* **☁️ Optional WARP egress**: If a Cloudflare WARP local proxy is already running on the VPS, such as `socks5://127.0.0.1:40000`, open **Admin -> Proxy Settings** and switch the egress core to **Cloudflare WARP**. The local `7928` proxy port will forward traffic through that WARP exit.
```

- [ ] **Step 2: Run complete test suite**

Run:

```bash
python3 -m unittest discover tests -v
```

Expected: PASS all tests.

- [ ] **Step 3: Run git status**

Run:

```bash
git status --short
```

Expected: README and any final touched files are listed before commit.

- [ ] **Step 4: Commit docs and final verification**

```bash
git add README.md
git commit -m "Document optional WARP egress"
```

- [ ] **Step 5: Record final verification output**

Run:

```bash
python3 -m unittest discover tests -v
git status --short
```

Expected: test suite PASS, then clean working tree.

---

## Self-Review

Spec coverage:

- Config defaults and validation: Tasks 1, 2, and 5.
- Backend provider and proxy forwarding: Task 3.
- OpenVPN lifecycle on WARP transition: Task 4.
- Settings API persistence: Task 5.
- Web UI controls and status label: Task 6.
- VPNGate click behavior from WARP mode and health check behavior: Task 7.
- User documentation: Task 8.

Placeholder scan: passed with concrete steps and code blocks throughout the plan.

Type consistency: WARP upstream tuple stays `tuple[str, str, int, str | None, str | None]`; mode names stay `vpngate` and `warp`; config keys stay `egress_mode` and `warp_proxy_url`.
