import copy
import json
import unittest
from importlib.resources import files

from orderflowsage.core import OrderFlowError
from orderflowsage.engine import order_flow_imbalance, run_pipeline
from orderflowsage.report import prompt, verify

CONFIG = json.loads(files("orderflowsage.data").joinpath("demo_config.json").read_text())
EVENTS = [json.loads(line) for line in files("orderflowsage.data").joinpath("demo.jsonl").read_text().splitlines()]


class EngineTests(unittest.TestCase):
    def test_pipeline_features_and_windows(self):
        report = run_pipeline(CONFIG, EVENTS)
        self.assertEqual(len(report["features"]), 12)
        self.assertEqual(len(report["windows"]), 3)
        first = report["features"][0]
        self.assertIsNone(first["order_flow_imbalance"])
        self.assertGreater(first["best_ask"], first["best_bid"])
        self.assertAlmostEqual(first["microprice"],
                               (first["best_ask"] * EVENTS[0]["bids"][0][1] + first["best_bid"] * EVENTS[0]["asks"][0][1]) /
                               (EVENTS[0]["bids"][0][1] + EVENTS[0]["asks"][0][1]))

    def test_ofi_known_queue_change(self):
        previous = {"bids": [[100, 10]], "asks": [[101, 12]]}
        current = {"bids": [[100, 14]], "asks": [[101, 9]]}
        self.assertEqual(order_flow_imbalance(previous, current), 7)

    def test_sequence_gap_and_crossed_book_fail_closed(self):
        changed = copy.deepcopy(EVENTS)
        changed[4]["sequence"] += 1
        with self.assertRaisesRegex(OrderFlowError, "sequence gap"):
            run_pipeline(CONFIG, changed)
        changed = copy.deepcopy(EVENTS)
        changed[2]["asks"][0][0] = changed[2]["bids"][0][0]
        with self.assertRaisesRegex(OrderFlowError, "crossed"):
            run_pipeline(CONFIG, changed)

    def test_wrong_sort_and_zero_size_fail(self):
        changed = copy.deepcopy(EVENTS)
        changed[0]["bids"][0], changed[0]["bids"][1] = changed[0]["bids"][1], changed[0]["bids"][0]
        with self.assertRaisesRegex(OrderFlowError, "descending"):
            run_pipeline(CONFIG, changed)
        changed = copy.deepcopy(EVENTS)
        changed[0]["asks"][0][1] = 0
        with self.assertRaisesRegex(OrderFlowError, "positive"):
            run_pipeline(CONFIG, changed)

    def test_future_event_cannot_change_past_features(self):
        baseline = run_pipeline(CONFIG, EVENTS)
        changed = copy.deepcopy(EVENTS)
        changed[-1]["bids"][0][1] += 100
        rerun = run_pipeline(CONFIG, changed)
        self.assertEqual(baseline["features"][:-1], rerun["features"][:-1])

    def test_verify_detects_tampering(self):
        report = run_pipeline(CONFIG, EVENTS)
        self.assertIs(verify(CONFIG, EVENTS, report), report)
        changed = copy.deepcopy(report)
        changed["integrity"]["sequence_complete"] = False
        with self.assertRaisesRegex(OrderFlowError, "recomputation"):
            verify(CONFIG, EVENTS, changed)

    def test_prompt_omits_prices_timestamps_and_books(self):
        material = json.dumps(prompt(run_pipeline(CONFIG, EVENTS)))
        self.assertNotIn(EVENTS[0]["timestamp"], material)
        self.assertNotIn("best_bid", material)
        self.assertNotIn("book_sha256", material)
        self.assertIn("Do not predict", material)


if __name__ == "__main__":
    unittest.main()
