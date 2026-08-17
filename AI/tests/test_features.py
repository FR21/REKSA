from __future__ import annotations

import unittest
from datetime import UTC, datetime, timedelta

from reksa_ai.contracts import ForecastRequest, Orientation, SensorSample, Vector3, Zone
from reksa_ai.features import extract_temporal_features


def sample(second: int, rssi: float, zone: Zone, accel_x: float = 0.0) -> SensorSample:
    return SensorSample(
        timestamp=datetime(2026, 8, 7, tzinfo=UTC) + timedelta(seconds=second),
        rssi=rssi,
        acceleration=Vector3(x=accel_x, y=0, z=1),
        gyroscope=Vector3(x=0, y=0, z=0),
        orientation=Orientation(pitch=second, roll=0, yaw=0),
        proximity_level=zone,
        hazard_active=True,
    )


class TemporalFeatureTests(unittest.TestCase):
    def test_extracts_temporal_pattern(self) -> None:
        request = ForecastRequest(
            window_id="WIN-1",
            worker_id="W01",
            helmet_id="HELMET-W01",
            hazard_id="F01",
            hazard_type="FORKLIFT",
            repeated_exposure_count=2,
            samples=[
                sample(0, -80, Zone.MODERATE),
                sample(1, -72, Zone.HIGH),
                sample(2, -64, Zone.CRITICAL, accel_x=3),
                sample(3, -56, Zone.CRITICAL),
            ],
        )

        features = extract_temporal_features(request)

        self.assertAlmostEqual(features.rssi_mean, -68.0)
        self.assertAlmostEqual(features.rssi_slope, 8.0)
        self.assertEqual(features.warning_duration_seconds, 2.0)
        self.assertEqual(features.danger_duration_seconds, 1.0)
        self.assertEqual(features.state_transition_count, 2)
        self.assertTrue(features.sudden_motion)
        self.assertEqual(features.repeated_exposure_count, 2)

    def test_rejects_window_without_two_received_packets(self) -> None:
        samples = [sample(0, -80, Zone.SAFE), sample(1, -80, Zone.SAFE)]
        samples[1] = samples[1].model_copy(update={"packet_received": False, "rssi": None})
        request = ForecastRequest(
            window_id="WIN-2",
            worker_id="W01",
            helmet_id="HELMET-W01",
            hazard_id="F01",
            samples=samples,
        )
        with self.assertRaisesRegex(ValueError, "two received BLE packets"):
            extract_temporal_features(request)


if __name__ == "__main__":
    unittest.main()

