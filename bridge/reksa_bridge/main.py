from __future__ import annotations

import json
import logging
import os
import ssl
import threading
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import paho.mqtt.client as mqtt
from google.cloud import pubsub_v1

from reksa_bridge.outbox import SqliteOutbox

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"), format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("reksa.bridge")


def required(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"{name} is required")
    return value


class Bridge:
    def __init__(self) -> None:
        self.project_id = required("GOOGLE_CLOUD_PROJECT")
        self.pubsub_topic = required("PUBSUB_TOPIC")
        self.mqtt_host = required("MQTT_HOST")
        self.mqtt_port = int(os.getenv("MQTT_PORT", "8883"))
        self.mqtt_username = required("MQTT_USERNAME")
        self.mqtt_password = required("MQTT_PASSWORD")
        self.bridge_id = os.getenv("BRIDGE_ID", "reksa-gateway-01")
        self.outbox = SqliteOutbox(Path(os.getenv("OUTBOX_PATH", "/data/outbox.db")))
        self.publisher = pubsub_v1.PublisherClient()
        self.topic_path = self.publisher.topic_path(self.project_id, self.pubsub_topic)
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=self.bridge_id)
        self.client.username_pw_set(self.mqtt_username, self.mqtt_password)
        self.client.tls_set(
            ca_certs=os.getenv("MQTT_CA_CERT") or None,
            cert_reqs=ssl.CERT_REQUIRED,
            tls_version=ssl.PROTOCOL_TLS_CLIENT,
        )
        self.client.reconnect_delay_set(min_delay=1, max_delay=60)
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.running = True

    def on_connect(self, client: mqtt.Client, _userdata: Any, _flags: Any, reason_code: Any, _properties: Any) -> None:
        if reason_code != 0:
            logger.error("MQTT connection rejected: %s", reason_code)
            return
        client.subscribe("REKSA/helmet/+/sensor", qos=1)
        client.subscribe("REKSA/hazard/+/status", qos=1)
        logger.info("Connected to HiveMQ and subscribed; pending=%d", self.outbox.count())

    def on_message(self, _client: mqtt.Client, _userdata: Any, message: mqtt.MQTTMessage) -> None:
        try:
            payload = json.loads(message.payload.decode("utf-8"))
            message_id = str(payload["message_id"])
            if self.outbox.was_delivered(message_id):
                self.publish_ack(payload, message_id, duplicate=True)
                logger.info("Duplicate %s re-acknowledged without Pub/Sub forward", message_id)
                return
            inserted = self.outbox.enqueue(message_id, message.topic, json.dumps(payload, separators=(",", ":")))
            if inserted:
                logger.info("Buffered %s from %s", message_id, message.topic)
        except (UnicodeDecodeError, json.JSONDecodeError, KeyError, TypeError) as exc:
            logger.warning("Rejected invalid payload on %s: %s", message.topic, exc)

    def publish_pending(self) -> None:
        while self.running:
            for pending in self.outbox.pending():
                envelope = {
                    "topic": pending.mqtt_topic,
                    "payload": json.loads(pending.payload),
                    "bridge_id": self.bridge_id,
                    "received_at": datetime.now(UTC).isoformat(),
                    "delivery_attempt": pending.attempts + 1,
                }
                try:
                    future = self.publisher.publish(
                        self.topic_path,
                        json.dumps(envelope, separators=(",", ":")).encode("utf-8"),
                        source="hivemq",
                        bridge_id=self.bridge_id,
                    )
                    pubsub_id = future.result(timeout=20)
                    self.outbox.mark_delivered(pending.message_id)
                    self.publish_ack(
                        envelope["payload"],
                        pending.message_id,
                        duplicate=False,
                        pubsub_message_id=pubsub_id,
                    )
                    logger.info("Forwarded %s to Pub/Sub as %s", pending.message_id, pubsub_id)
                except Exception as exc:  # retry is intentionally broad at the durable boundary
                    self.outbox.mark_attempt(pending.message_id)
                    logger.warning("Pub/Sub unavailable; retained %s: %s", pending.message_id, exc)
                    break
            time.sleep(1)

    def publish_ack(
        self,
        payload: dict[str, Any],
        message_id: str,
        *,
        duplicate: bool,
        pubsub_message_id: str | None = None,
    ) -> None:
        worker_id = str(payload.get("worker_id", "")).strip()
        if not worker_id:
            return
        acknowledgement: dict[str, Any] = {
            "message_id": message_id,
            "accepted": True,
            "duplicate": duplicate,
        }
        if pubsub_message_id:
            acknowledgement["pubsub_message_id"] = pubsub_message_id
        result = self.client.publish(
            f"REKSA/helmet/{worker_id}/telemetry/ack",
            json.dumps(acknowledgement, separators=(",", ":")),
            qos=1,
        )
        if result.rc != mqtt.MQTT_ERR_SUCCESS:
            logger.warning("ACK publish failed for %s: rc=%s", message_id, result.rc)

    def run(self) -> None:
        threading.Thread(target=self.publish_pending, daemon=True, name="pubsub-outbox").start()
        self.client.connect(self.mqtt_host, self.mqtt_port, keepalive=30)
        self.client.loop_forever(retry_first_connection=True)


def run() -> None:
    Bridge().run()
