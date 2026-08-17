from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any

from app.core.config import settings


async def archive_ingest_event(envelope: dict[str, Any], pubsub_message_id: str) -> None:
    """Persist a raw cloud-ingest envelope when Firestore is explicitly enabled."""
    if not settings.firestore_enabled:
        return

    def write() -> None:
        try:
            from google.cloud import firestore
        except ImportError as exc:  # pragma: no cover - deployment configuration error
            raise RuntimeError("google-cloud-firestore is required when FIRESTORE_ENABLED=true") from exc
        client = firestore.Client(project=settings.google_cloud_project)
        client.collection(settings.firestore_collection).document(pubsub_message_id).set(
            {
                **envelope,
                "pubsub_message_id": pubsub_message_id,
                "archived_at": datetime.now(UTC),
            }
        )

    await asyncio.to_thread(write)
