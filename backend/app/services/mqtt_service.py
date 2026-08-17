import asyncio
import json
import logging
import ssl
import threading
from collections import OrderedDict
from collections.abc import Callable
from typing import Any

import paho.mqtt.client as mqtt
from pydantic import ValidationError

from app.schemas.mqtt import EnvironmentPayload, HazardPayload, HelmetSensorPayload

logger = logging.getLogger(__name__)

TOPIC_SCHEMAS: dict[str, type[HelmetSensorPayload | HazardPayload | EnvironmentPayload]] = {
    "helmet": HelmetSensorPayload,
    "hazard": HazardPayload,
    "environment": EnvironmentPayload,
}


class MQTTService:
    subscriptions = (
        "REKSA/helmet/+/sensor", "REKSA/helmet/+/status",
        "REKSA/helmet/+/warning/ack", "REKSA/hazard/+/beacon",
        "REKSA/hazard/+/status", "REKSA/environment/+/data",
        "REKSA/event/nearmiss", "REKSA/risk/+/score",
    )

    def __init__(
        self,
        host: str,
        port: int,
        handler: Callable[[str, dict[str, Any]], None] | None = None,
        *,
        username: str | None = None,
        password: str | None = None,
        use_tls: bool = False,
        ca_cert: str | None = None,
        client_id: str = "reksa-backend",
        ack_enabled: bool = True,
        dedup_max_messages: int = 5000,
    ) -> None:
        self.host = host
        self.port = port
        self.handler = handler
        self.client_id = client_id
        self.ack_enabled = ack_enabled
        self.dedup_max_messages = max(100, dedup_max_messages)
        self._seen_message_ids: OrderedDict[str, None] = OrderedDict()
        self.connected = False
        self.invalid_messages: list[dict[str, str]] = []
        self.loop: asyncio.AbstractEventLoop | None = None
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=client_id)
        if username:
            self.client.username_pw_set(username, password)
        if use_tls:
            self.client.tls_set(
                # An empty MQTT_CA_CERT means "use the operating system trust
                # store". Passing an empty string to paho makes OpenSSL treat it
                # as a filename and crashes application startup.
                ca_certs=ca_cert or None,
                cert_reqs=ssl.CERT_REQUIRED,
                tls_version=ssl.PROTOCOL_TLS_CLIENT,
            )
        self.client.will_set(
            "REKSA/backend/status",
            json.dumps({"status": "OFFLINE", "source": client_id}),
            qos=1,
            retain=True,
        )
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_message = self._on_message

    def _on_connect(self, client: mqtt.Client, _userdata: Any, _flags: Any, reason_code: Any, _properties: Any) -> None:
        self.connected = reason_code == 0
        if self.connected:
            client.publish(
                "REKSA/backend/status",
                json.dumps({"status": "ONLINE", "source": self.client_id}),
                qos=1,
                retain=True,
            )
            for topic in self.subscriptions:
                client.subscribe(topic, qos=1)

    def _on_disconnect(self, _client: mqtt.Client, _userdata: Any, _flags: Any, _reason_code: Any, _properties: Any) -> None:
        self.connected = False

    def _on_message(self, _client: mqtt.Client, _userdata: Any, message: mqtt.MQTTMessage) -> None:
        try:
            payload = json.loads(message.payload.decode("utf-8"))
            category = message.topic.split("/")[1]
            schema = TOPIC_SCHEMAS.get(category)
            validated = schema.model_validate(payload).model_dump(mode="json") if schema else payload
            message_id = str(validated.get("message_id", "")).strip()
            worker_id = str(validated.get("worker_id", "")).strip()
            if message_id and message_id in self._seen_message_ids:
                self._publish_ack(worker_id, message_id, duplicate=True)
                return
            if message_id:
                self._seen_message_ids[message_id] = None
                self._seen_message_ids.move_to_end(message_id)
                while len(self._seen_message_ids) > self.dedup_max_messages:
                    self._seen_message_ids.popitem(last=False)
            if self.handler:
                if asyncio.iscoroutinefunction(self.handler) and self.loop:
                    asyncio.run_coroutine_threadsafe(self.handler(message.topic, validated), self.loop)
                else:
                    self.handler(message.topic, validated)
            self._publish_ack(worker_id, message_id, duplicate=False)
        except (UnicodeDecodeError, json.JSONDecodeError, ValidationError) as error:
            self.invalid_messages.append({"topic": message.topic, "error": str(error)[:500]})
            logger.warning("Rejected malformed MQTT message on %s", message.topic)

    def _publish_ack(self, worker_id: str, message_id: str, *, duplicate: bool) -> None:
        if not self.ack_enabled or not worker_id or not message_id:
            return
        self.client.publish(
            f"REKSA/helmet/{worker_id}/telemetry/ack",
            json.dumps({"message_id": message_id, "accepted": True, "duplicate": duplicate}),
            qos=1,
        )

    def start(self) -> None:
        def connect() -> None:
            try:
                self.client.connect_async(self.host, self.port, keepalive=30)
                self.client.loop_forever(retry_first_connection=True)
            except OSError:
                logger.warning("MQTT unavailable; API continues in simulation mode")

        threading.Thread(target=connect, daemon=True, name="reksa-mqtt").start()

    def stop(self) -> None:
        if self.connected:
            self.client.publish(
                "REKSA/backend/status",
                json.dumps({"status": "OFFLINE", "shutdown": "GRACEFUL"}),
                qos=1,
                retain=True,
            ).wait_for_publish(timeout=2)
        self.client.disconnect()
        self.client.loop_stop()

    def publish(self, topic: str, payload: dict[str, Any]) -> bool:
        if not self.connected:
            return False
        result = self.client.publish(topic, json.dumps(payload), qos=1)
        return result.rc == mqtt.MQTT_ERR_SUCCESS
