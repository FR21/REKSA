from __future__ import annotations

import csv
import json
import logging
import ssl
from pathlib import Path
from typing import Any

LOGGER_COLUMNS = [
    "participant_id", "session_id", "scenario_id", "trajectory_id", "event_id",
    "timestamp", "worker_id", "helmet_id", "hazard_id", "hazard_type", "rssi",
    "packet_received", "accel_x", "accel_y", "accel_z", "gyro_x", "gyro_y",
    "gyro_z", "pitch", "roll", "yaw", "proximity_level", "hazard_active",
    "temperature_c", "humidity_percent", "mq135_raw", "mq135_baseline",
    "mq135_deviation", "candidate_impact",
    "candidate_fall", "post_event_stillness_seconds", "repeated_exposure_count",
    "similar_event_count", "local_warning_success", "connectivity_status",
    "forecast_target", "target_source", "supervisor_priority", "verification_label",
]

logger = logging.getLogger(__name__)


def flatten_helmet_payload(payload: dict[str, Any], context: dict[str, str]) -> dict[str, Any]:
    acceleration = payload.get("acceleration") or {}
    gyroscope = payload.get("gyroscope") or {}
    orientation = payload.get("orientation") or {}
    hazard = payload.get("closest_hazard") or {}
    air = payload.get("air_quality") or {}
    packet_received = bool(hazard and hazard.get("rssi") is not None)
    status = str(hazard.get("operating_status", "INACTIVE")).upper()
    mq135_raw = air.get("mq135_raw")
    mq135_baseline = air.get("mq135_baseline", context.get("mq135_baseline"))
    mq135_deviation = air.get("mq135_deviation")
    if mq135_deviation is None and mq135_raw is not None and mq135_baseline not in {None, ""}:
        mq135_deviation = float(mq135_raw) - float(mq135_baseline)
    return {
        **context,
        "event_id": "",
        "timestamp": payload.get("timestamp", ""),
        "worker_id": payload.get("worker_id", ""),
        "helmet_id": payload.get("device_id", ""),
        "hazard_id": hazard.get("hazard_id", "NONE"),
        "hazard_type": hazard.get("hazard_type", "UNKNOWN"),
        "rssi": hazard.get("rssi", ""),
        "packet_received": packet_received,
        "accel_x": acceleration.get("x", 0),
        "accel_y": acceleration.get("y", 0),
        "accel_z": acceleration.get("z", 1),
        "gyro_x": gyroscope.get("x", 0),
        "gyro_y": gyroscope.get("y", 0),
        "gyro_z": gyroscope.get("z", 0),
        "pitch": orientation.get("pitch", 0),
        "roll": orientation.get("roll", 0),
        "yaw": orientation.get("yaw", 0),
        "proximity_level": hazard.get("proximity_level", "SAFE"),
        "hazard_active": status in {"ACTIVE", "MOVING"},
        "temperature_c": payload.get("temperature", ""),
        "humidity_percent": payload.get("humidity", ""),
        "mq135_raw": mq135_raw if mq135_raw is not None else "",
        "mq135_baseline": mq135_baseline if mq135_baseline is not None else "",
        "mq135_deviation": mq135_deviation if mq135_deviation is not None else "",
        "candidate_impact": payload.get("impact_detected", False),
        "candidate_fall": payload.get("fall_detected", False),
        "post_event_stillness_seconds": "",
        "repeated_exposure_count": 0,
        "similar_event_count": 0,
        "local_warning_success": "",
        "connectivity_status": "ONLINE",
        "forecast_target": "",
        "target_source": "UNLABELED",
        "supervisor_priority": "",
        "verification_label": "",
    }


class CsvMqttLogger:
    def __init__(self, output_path: Path, context: dict[str, str]) -> None:
        self.output_path = output_path
        self.context = context
        self.output_path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, payload: dict[str, Any]) -> None:
        row = flatten_helmet_payload(payload, self.context)
        exists = self.output_path.exists() and self.output_path.stat().st_size > 0
        with self.output_path.open("a", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=LOGGER_COLUMNS, extrasaction="ignore")
            if not exists:
                writer.writeheader()
            writer.writerow(row)

    def run(
        self,
        host: str,
        port: int,
        topic: str,
        *,
        username: str | None = None,
        password: str | None = None,
        use_tls: bool = False,
        ca_cert: str | None = None,
    ) -> None:
        try:
            import paho.mqtt.client as mqtt
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError("paho-mqtt is required for MQTT logging") from exc

        def on_connect(client: Any, userdata: Any, flags: Any, reason_code: Any, properties: Any = None) -> None:
            if int(reason_code) != 0:
                raise ConnectionError(f"MQTT connection failed: {reason_code}")
            client.subscribe(topic, qos=1)
            logger.info("Subscribed to %s", topic)

        def on_message(client: Any, userdata: Any, message: Any) -> None:
            try:
                payload = json.loads(message.payload.decode("utf-8"))
                self.append(payload)
            except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
                logger.warning("Rejected MQTT payload on %s: %s", message.topic, exc)

        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        if username:
            client.username_pw_set(username, password)
        if use_tls:
            client.tls_set(
                ca_certs=ca_cert,
                cert_reqs=ssl.CERT_REQUIRED,
                tls_version=ssl.PROTOCOL_TLS_CLIENT,
            )
        client.on_connect = on_connect
        client.on_message = on_message
        client.connect(host, port, keepalive=60)
        client.loop_forever()
