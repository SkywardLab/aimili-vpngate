# Node Latency Sorting Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Show unavailable node latency as `-` and return/display nodes ordered by latency with unavailable nodes last.

**Architecture:** Keep sorting in `vpngate_manager.py::sort_all_nodes()` as the backend source of truth. Add a small frontend latency formatter inside the existing inline UI script. Cover behavior with one functional sorting test and updated UI contract checks.

**Tech Stack:** Python standard library, `unittest`, inline JavaScript in `vpngate_manager.py`.

---

## File Structure

- Modify: `vpngate_manager.py`
  - `sort_all_nodes(nodes)` changes measured-node sort priority to latency first.
  - `/api/nodes` applies `sort_all_nodes(nodes)` before returning node JSON.
  - Inline JavaScript gains `formatNodeLatency(n)` and table rendering uses it.
- Modify: `tests/ui_contract_checks.py`
  - Add string-contract checks for the frontend latency helper and API sorting call.
- Create: `tests/node_sorting_checks.py`
  - Add a functional unit test for latency-first sorting and unavailable-last ordering.

---

### Task 1: Backend node sorting

**Files:**
- Create: `tests/node_sorting_checks.py`
- Modify: `vpngate_manager.py:1156-1174`

- [ ] **Step 1: Write the failing functional test**

Create `tests/node_sorting_checks.py`:

```python
import unittest

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


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the test and verify it fails**

Run:

```bash
python3 -m unittest tests.node_sorting_checks.NodeSortingTest.test_available_nodes_sort_by_latency_and_unavailable_nodes_are_last
```

Expected: `FAIL`, with `residential-slow` appearing before `hosting-fast` under the current sort key.

- [ ] **Step 3: Implement latency-first measured sorting**

Replace `sort_all_nodes()` in `vpngate_manager.py` with:

```python
def sort_all_nodes(nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    available_nodes = sorted(
        [n for n in nodes if n.get("probe_status") == "available" or n.get("active")],
        key=lambda n: (
            parse_int(n.get("latency_ms")) or 999999,
            0 if n.get("ip_type") in ("residential", "mobile") else 1,
            -parse_int(n.get("score"))
        )
    )
    untested_nodes = sorted(
        [n for n in nodes if n.get("probe_status") in ("not_checked", "testing") and not n.get("active")],
        key=lambda n: (-parse_int(n.get("score")), parse_int(n.get("ping")))
    )
    unavailable_nodes = sorted(
        [n for n in nodes if n.get("probe_status") == "unavailable" and not n.get("active")],
        key=lambda n: (-parse_int(n.get("score")), -float(n.get("probed_at", 0)))
    )
    return available_nodes + untested_nodes + unavailable_nodes
```

- [ ] **Step 4: Run the functional test and verify it passes**

Run:

```bash
python3 -m unittest tests.node_sorting_checks.NodeSortingTest.test_available_nodes_sort_by_latency_and_unavailable_nodes_are_last
```

Expected: `OK`.

- [ ] **Step 5: Commit Task 1**

Run:

```bash
git add vpngate_manager.py tests/node_sorting_checks.py
git commit -m "Sort nodes by measured latency"
```

---

### Task 2: API and UI latency display contract

**Files:**
- Modify: `tests/ui_contract_checks.py`
- Modify: `vpngate_manager.py:3755-3758`
- Modify: `vpngate_manager.py:5024-5030`

- [ ] **Step 1: Write failing contract tests**

Append these tests to `tests/ui_contract_checks.py` inside `UiContractTest`:

```python
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
```

- [ ] **Step 2: Run the contract tests and verify they fail**

Run:

```bash
python3 -m unittest tests.ui_contract_checks.UiContractTest.test_unavailable_node_latency_displays_dash tests.ui_contract_checks.UiContractTest.test_api_nodes_response_uses_sorted_nodes
```

Expected: `FAIL`, because the helper and API sorting call are absent.

- [ ] **Step 3: Add frontend latency formatter**

In `vpngate_manager.py`, near the existing JavaScript helpers and before table rows are rendered, add:

```javascript
  function formatNodeLatency(n) {
    if (!n || n.probe_status === "unavailable") return "-";
    const latency = Number(n.latency_ms || 0);
    if (latency > 0 && (n.probe_status === "available" || n.active)) {
      const latencyClass = getLatencyClass(latency);
      return `<span class="latency-val ${latencyClass}">${latency} ms</span>`;
    }
    return "-";
  }
```

Replace the current table-rendering latency lines:

```javascript
      const latencyClass = getLatencyClass(n.latency_ms);
      const latencyText = n.latency_ms ? `<span class="latency-val ${latencyClass}">${n.latency_ms} ms</span>` : "-";
```

with:

```javascript
      const latencyText = formatNodeLatency(n);
```

- [ ] **Step 4: Sort nodes in `/api/nodes` response**

In `vpngate_manager.py`, inside `/api/nodes`, change:

```python
            stripped_nodes = []
            for n in nodes:
```

to:

```python
            nodes = sort_all_nodes(nodes)
            stripped_nodes = []
            for n in nodes:
```

- [ ] **Step 5: Run contract tests and verify they pass**

Run:

```bash
python3 -m unittest tests.ui_contract_checks.UiContractTest.test_unavailable_node_latency_displays_dash tests.ui_contract_checks.UiContractTest.test_api_nodes_response_uses_sorted_nodes
```

Expected: `OK`.

- [ ] **Step 6: Run the full focused test set**

Run:

```bash
python3 -m unittest tests.ui_contract_checks tests.node_sorting_checks
```

Expected: `OK`.

- [ ] **Step 7: Commit Task 2**

Run:

```bash
git add vpngate_manager.py tests/ui_contract_checks.py
git commit -m "Show unavailable node latency as dash"
```

---

### Task 3: Final verification

**Files:**
- Read: `vpngate_manager.py`
- Read: `tests/ui_contract_checks.py`
- Read: `tests/node_sorting_checks.py`

- [ ] **Step 1: Run all repository tests**

Run:

```bash
python3 -m unittest discover tests
```

Expected: `OK`.

- [ ] **Step 2: Check git state**

Run:

```bash
git status --short
```

Expected: only pre-existing untracked files remain, such as `DESIGN.md`, with task changes committed.

- [ ] **Step 3: Report verification evidence**

Report:

```text
Verification:
- python3 -m unittest discover tests: OK
- git status --short: reviewed
```

---

## Self-Review

- Spec coverage: backend sorting, API ordering, frontend `-` display, and tests are covered by Tasks 1 and 2.
- Placeholder scan: concrete files, code, commands, and expected outputs are present.
- Type consistency: tests and implementation use existing `latency_ms`, `probe_status`, `active`, `ip_type`, `score`, `ping`, and `probed_at` fields.
