# Optional WARP Egress Design

Date: 2026-07-03

## Goal

Add an optional Cloudflare WARP egress mode to AimiliVPN while preserving the current VPNGate/OpenVPN path as the default. Users can choose WARP from the Web UI and provide a local WARP HTTP or SOCKS5 proxy endpoint.

## Current Project Context

AimiliVPN is a pure Python standard-library VPNGate proxy gateway. The manager stores Web UI and routing settings in `vpngate_data/ui_auth.json`, exposes settings through `/api/update_settings`, serves a single-file Web UI from `vpngate_manager.py`, and runs a local dual HTTP/SOCKS5 proxy from `proxy_server.py`. The current active egress path is VPNGate through OpenVPN, `tun0`, and policy routing table `100`.

## User-Facing Behavior

Network settings gain an egress core selector:

- `VPNGate`: existing behavior with OpenVPN node selection, routing modes, and automatic switching.
- `WARP`: local proxy traffic is forwarded through the configured WARP upstream endpoint.

The WARP endpoint defaults to:

```text
socks5://127.0.0.1:40000
```

Accepted endpoint schemes:

- `socks5://host:port`
- `socks://host:port`
- `http://host:port`

When WARP mode is saved, the manager stops the active OpenVPN connection, clears VPNGate active node state, and reports WARP as the active egress core. Proxy health checks use the WARP endpoint so the displayed exit IP reflects WARP.

## Configuration

`ui_auth.json` adds two keys:

```json
{
  "egress_mode": "vpngate",
  "warp_proxy_url": "socks5://127.0.0.1:40000"
}
```

Defaults:

- `egress_mode`: `vpngate`
- `warp_proxy_url`: `socks5://127.0.0.1:40000`

Validation:

- `egress_mode` accepts `vpngate` and `warp`.
- `warp_proxy_url` must include a supported scheme, host, and port in range `1..65535`.
- Existing unknown keys remain preserved during config load/save.

## Backend Design

### Configuration helpers

Add a small parser/validator in `vpn_utils.py` or `vpngate_manager.py` that converts `warp_proxy_url` into the existing upstream proxy tuple shape:

```python
(proxy_type, host, port, username, password)
```

`proxy_type` maps `socks5` and `socks` to `socks`, and `http`/`https` to `http`.

### Manager state

`set_state_from_runtime()` adds:

- `egress_mode`
- `warp_proxy_url`
- `egress_label`

In WARP mode, node-related state remains visible for history, while current active VPNGate node fields are cleared after saving WARP mode.

### OpenVPN lifecycle

When settings change from VPNGate to WARP:

1. Stop active OpenVPN.
2. Cleanup policy routing.
3. Mark all nodes inactive.
4. Set proxy state to pending until health check completes.

When settings change from WARP to VPNGate:

1. Persist VPNGate mode.
2. Keep existing connection settings.
3. Allow the existing manual connect and auto-switch flows to start a VPNGate node.

### Proxy forwarding

`proxy_server.py` gains an optional egress upstream provider. In WARP mode, outbound target connections are opened through the configured WARP upstream. Existing direct/tun-based behavior remains used in VPNGate mode.

A minimal integration point:

```python
set_egress_upstream_provider(callable)
```

The provider returns either `None` for VPNGate mode or an upstream proxy config for WARP mode. `create_connection()` uses this provider before dialing the target directly.

Supported forwarding:

- SOCKS5 upstream connect with optional username/password.
- HTTP upstream `CONNECT` for TLS and tunnel-style requests.
- Direct HTTP requests can still be sent through HTTP upstream by using absolute-form request forwarding, matching the existing upstream proxy implementation style in `vpngate_manager.py`.

### API behavior

`/api/update_settings` accepts:

- `egress_mode`
- `warp_proxy_url`

It validates both values, persists them, and applies lifecycle changes based on mode transition.

`/api/update_routing` keeps route-mode behavior for VPNGate. If WARP mode is active, route-mode changes are persisted for later VPNGate use and do not start OpenVPN.

`/api/connect` in WARP mode switches `egress_mode` back to `vpngate` before connecting the selected VPNGate node. This keeps the node-list action intuitive: clicking a VPNGate node means use VPNGate.

`/api/test_proxy` uses the active egress mode automatically and reports the exit IP for the local proxy path.

## Web UI Design

The network settings modal adds a compact egress section above routing mode:

- Two option cards: `VPNGate 节点` and `Cloudflare WARP`
- WARP endpoint input shown when WARP is selected
- Hint text: “请先在本机启动 WARP 本地代理，例如 wireproxy 或 warp-cli 对应的代理端口。”

When WARP is selected:

- VPNGate routing cards remain visible as saved preferences for later VPNGate use.
- A warning explains that node auto-switch is paused while WARP mode is active.
- Gateway status shows “出站核心: WARP”.

## Error Handling

Invalid WARP endpoints return HTTP 400 with a clear message.

If the WARP endpoint is unreachable, saving still succeeds and the health check reports the connectivity failure. This supports configuring WARP before its local service starts.

If proxy forwarding through WARP fails during a request, the proxy connection returns the same style of connection failure currently used for upstream failures, and logs the WARP upstream error.

## Testing Plan

Add tests before implementation:

1. Default config includes `egress_mode = vpngate` and the default `warp_proxy_url`.
2. WARP endpoint validation accepts SOCKS5 and HTTP URLs.
3. WARP endpoint validation rejects missing scheme, missing host, and invalid port.
4. Saving WARP mode persists both new keys.
5. Switching to WARP stops the active OpenVPN process and clears active node state.
6. In WARP mode, the proxy connection helper uses the upstream proxy path.
7. In VPNGate mode, proxy connection behavior remains direct/tun-based.

## Scope Boundary

This change integrates WARP through a local upstream proxy endpoint. Installing Cloudflare WARP, creating WARP accounts, registering devices, and managing kernel WireGuard interfaces are outside this feature. The installer can document the expected local proxy endpoint later.
