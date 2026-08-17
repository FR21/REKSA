import asyncio
import json
import logging
import threading
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

    def __init__(self, host: str, port: int, handler: Callable[[str, dict[str, Any]], None] | None = None) -> None:
        self.host = host
        self.port = port
        self.handler = handler
        self.connected = False
        self.invalid_messages: list[dict[str, str]] = []
        self.loop: asyncio.AbstractEventLoop | None = None
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="reksa-backend")
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_message = self._on_message

    def _on_connect(self, client: mqtt.Client, _userdata: Any, _flags: Any, reason_code: Any, _properties: Any) -> None:
        self.connected = reason_code == 0
        if self.connected:
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
            if self.handler:
                if asyncio.iscoroutinefunction(self.handler) and self.loop:
                    asyncio.run_coroutine_threadsafe(self.handler(message.topic, validated), self.loop)
                else:
                    self.handler(message.topic, validated)
        except (UnicodeDecodeError, json.JSONDecodeError, ValidationError) as error:
            self.invalid_messages.append({"topic": message.topic, "error": str(error)[:500]})
            logger.warning("Rejected malformed MQTT message on %s", message.topic)

    def start(self) -> None:
        def connect() -> None:
            try:
                self.client.connect_async(self.host, self.port, keepalive=30)
                self.client.loop_forever(retry_first_connection=True)
            except OSError:
                logger.warning("MQTT unavailable; API continues in simulation mode")

        threading.Thread(target=connect, daemon=True, name="reksa-mqtt").start()

    def stop(self) -> None:
        self.client.disconnect()
        self.client.loop_stop()

    def publish(self, topic: str, payload: dict[str, Any]) -> bool:
        if not self.connected:
            return False
        result = self.client.publish(topic, json.dumps(payload), qos=1)
        return result.rc == mqtt.MQTT_ERR_SUCCESS

