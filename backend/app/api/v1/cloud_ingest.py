from __future__ import annotations

import base64
import json
from typing import Any

from fastapi import APIRouter, HTTPException, Response, status
from pydantic import BaseModel, Field

from app.services.cloud_archive import archive_ingest_event
from app.services.mqtt_handler import handle_mqtt_message

router = APIRouter(prefix="/ingest", tags=["Cloud ingest"])


class PubSubMessage(BaseModel):
    data: str
    message_id: str = Field(alias="messageId")
    attributes: dict[str, str] = Field(default_factory=dict)


class PubSubPush(BaseModel):
    message: PubSubMessage
    subscription: str | None = None


@router.post("/pubsub", status_code=status.HTTP_204_NO_CONTENT)
async def ingest_pubsub(push: PubSubPush) -> Response:
    try:
        decoded = base64.b64decode(push.message.data, validate=True)
        envelope: dict[str, Any] = json.loads(decoded.decode("utf-8"))
        topic = str(envelope["topic"])
        payload = envelope["payload"]
        if not isinstance(payload, dict):
            raise TypeError("payload must be an object")
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError, KeyError, TypeError) as exc:
        raise HTTPException(status_code=400, detail=f"Invalid Pub/Sub envelope: {exc}") from exc

    await handle_mqtt_message(topic, payload)
    await archive_ingest_event(envelope, push.message.message_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
