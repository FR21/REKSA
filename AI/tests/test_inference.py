from __future__ import annotations

import json
import unittest
from pathlib import Path

from reksa_ai.contracts import ForecastRequest, PriorityEvent
from reksa_ai.inference import NearMissRiskForecaster, PriorityEngine

ROOT = Path(__file__).resolve().parents[1]


class BaselineInferenceTests(unittest.TestCase):
    def test_forecast_is_explicitly_uncalibrated_baseline(self) -> None:
        payload = json.loads((ROOT / "examples/forecast_request.json").read_text())
        result = NearMissRiskForecaster().predict(ForecastRequest.model_validate(payload))

        self.assertEqual(result.inference_source, "RULE_BASED_BASELINE")
        self.assertFalse(result.probability_is_calibrated)
        self.assertEqual(result.score_semantics, "RULE_SCORE")
        self.assertTrue(result.advisory_only)
        self.assertGreater(result.escalation_probability, 0.4)
        self.assertIn("rapid_rssi_increase", result.dominant_factors)

    def test_priority_never_claims_supervisor_verification(self) -> None:
        payload = json.loads((ROOT / "examples/priority_request.json").read_text())
        result = PriorityEngine().predict(PriorityEvent.model_validate(payload))

        self.assertEqual(result.priority.value, "HIGH")
        self.assertGreaterEqual(result.priority_score, 70)
        self.assertTrue(result.advisory_only)
        self.assertTrue(result.requires_supervisor_verification)
        self.assertIn("candidate_impact", result.reason_codes)


if __name__ == "__main__":
    unittest.main()
