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
