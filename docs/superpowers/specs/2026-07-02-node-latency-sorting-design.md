# Node Latency Sorting Design

## Goal

The node list presents the most useful choices first:

1. Available nodes and the active node sorted by measured latency from low to high.
2. Testing and unchecked nodes after measured nodes.
3. Unavailable nodes at the end with latency rendered as `-`.

## Scope

This change covers the Web UI node table and the `/api/nodes` response ordering used by page load, manual refresh, and automatic polling.

## Backend Design

`sort_all_nodes(nodes)` remains the single ordering function. It groups nodes into:

- measured group: `probe_status == "available"` or `active`
- pending group: `probe_status` in `("not_checked", "testing")`
- unavailable group: `probe_status == "unavailable"`

The measured group sorts by:

1. `latency_ms` ascending, with empty or invalid latency placed after measured latencies.
2. IP type preference for residential/mobile where latency ties.
3. score descending.

The pending group keeps its current heuristic order by score and API ping. The unavailable group stays last and keeps useful secondary ordering by score and probe time.

`/api/nodes` applies `sort_all_nodes()` before stripping `config_text` and returning the JSON payload, so all UI refresh paths share the same order.

## Frontend Design

The node table renders latency with a small helper rule:

- Unavailable nodes render latency as `-`.
- Available or active nodes with `latency_ms > 0` render `N ms`.
- Pending nodes render `-` until a measured latency is present.

This keeps table cells stable and avoids showing stale or misleading latency for failed nodes.

## Testing

Add contract tests that verify:

- the UI explicitly renders unavailable node latency as `-`
- `/api/nodes` uses `sort_all_nodes()` before returning nodes
- measured nodes use latency-first ordering

Existing UI contract tests continue to verify the latency column remains present.
