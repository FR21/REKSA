from __future__ import annotations

import unittest
from pathlib import Path

import pandas as pd

from reksa_ai.datasets import build_event_dataset, build_forecasting_windows

ROOT = Path(__file__).resolve().parents[1]


class DatasetBuilderTests(unittest.TestCase):
    def setUp(self) -> None:
        self.raw = pd.read_csv(ROOT / "data/templates/raw_sensor_samples.csv")

    def test_target_is_read_only_from_future_horizon(self) -> None:
        windows = build_forecasting_windows(
            self.raw,
            window_seconds=2,
            horizon_seconds=1,
            step_seconds=1,
            min_samples=2,
        )

        positive = windows[windows["escalated_within_horizon"] == 1]
        self.assertEqual(len(positive), 1)
        self.assertTrue(positive.iloc[0]["window_ended_at"].startswith("2026-08-07T08:15:03"))
        self.assertEqual(positive.iloc[0]["target_source"], "CONTROLLED_SCENARIO")

    def test_event_builder_produces_one_row_per_event(self) -> None:
        events = build_event_dataset(self.raw)

        self.assertEqual(len(events), 1)
        self.assertEqual(events.iloc[0]["event_id"], "EVT-TEMPLATE-001")
        self.assertEqual(events.iloc[0]["supervisor_priority"], "HIGH")
        self.assertEqual(events.iloc[0]["verification_label"], "SIMULATED_HIGH_RISK")


if __name__ == "__main__":
    unittest.main()
