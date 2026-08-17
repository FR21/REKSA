from __future__ import annotations

import unittest

import numpy as np

from scripts.generate_synthetic_datasets import (
    build_forecasting_dataset,
    build_priority_dataset,
    validate_forecasting,
    validate_priority,
)


class SyntheticGeneratorTests(unittest.TestCase):
    def test_forecasting_data_contains_both_targets_and_valid_physics(self) -> None:
        frame = build_forecasting_dataset(
            row_count=1200,
            participant_count=12,
            sessions_per_participant=6,
            rng=np.random.default_rng(101),
        )

        self.assertEqual(set(frame["escalated_within_horizon"]), {0, 1})
        self.assertTrue(all(validate_forecasting(frame).values()))
        self.assertEqual(set(frame["data_origin"]), {"SYNTHETIC"})

    def test_priority_data_contains_three_classes_without_verified_claim(self) -> None:
        frame = build_priority_dataset(
            row_count=1200,
            participant_count=12,
            sessions_per_participant=6,
            rng=np.random.default_rng(202),
        )

        self.assertEqual(set(frame["supervisor_priority"]), {"LOW", "MEDIUM", "HIGH"})
        self.assertTrue(all(validate_priority(frame).values()))
        self.assertFalse(frame["verification_label"].str.contains("VERIFIED").any())
