from __future__ import annotations

import sqlite3
import threading
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class PendingMessage:
    message_id: str
    mqtt_topic: str
    payload: str
    attempts: int


class SqliteOutbox:
    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self.connection = sqlite3.connect(path, check_same_thread=False)
        with self.lock:
            self.connection.execute(
                """CREATE TABLE IF NOT EXISTS outbox (
                    message_id TEXT PRIMARY KEY,
                    mqtt_topic TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    attempts INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )"""
            )
            self.connection.execute(
                """CREATE TABLE IF NOT EXISTS delivered (
                    message_id TEXT PRIMARY KEY,
                    delivered_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )"""
            )
            self.connection.commit()

    def enqueue(self, message_id: str, mqtt_topic: str, payload: str) -> bool:
        with self.lock:
            if self.was_delivered(message_id):
                return False
            cursor = self.connection.execute(
                "INSERT OR IGNORE INTO outbox(message_id, mqtt_topic, payload) VALUES (?, ?, ?)",
                (message_id, mqtt_topic, payload),
            )
            self.connection.commit()
            return cursor.rowcount == 1

    def was_delivered(self, message_id: str) -> bool:
        with self.lock:
            row = self.connection.execute(
                "SELECT 1 FROM delivered WHERE message_id = ?", (message_id,)
            ).fetchone()
            return row is not None

    def pending(self, limit: int = 100) -> list[PendingMessage]:
        with self.lock:
            rows = self.connection.execute(
                "SELECT message_id, mqtt_topic, payload, attempts FROM outbox ORDER BY created_at LIMIT ?",
                (limit,),
            ).fetchall()
            return [PendingMessage(*row) for row in rows]

    def mark_attempt(self, message_id: str) -> None:
        with self.lock:
            self.connection.execute(
                "UPDATE outbox SET attempts = attempts + 1 WHERE message_id = ?", (message_id,)
            )
            self.connection.commit()

    def mark_delivered(self, message_id: str, history_limit: int = 5000) -> None:
        with self.lock:
            self.connection.execute("DELETE FROM outbox WHERE message_id = ?", (message_id,))
            self.connection.execute(
                "INSERT OR IGNORE INTO delivered(message_id) VALUES (?)", (message_id,)
            )
            self.connection.execute(
                """DELETE FROM delivered
                   WHERE rowid NOT IN (
                       SELECT rowid FROM delivered ORDER BY rowid DESC LIMIT ?
                   )""",
                (history_limit,),
            )
            self.connection.commit()

    def count(self) -> int:
        with self.lock:
            return int(self.connection.execute("SELECT COUNT(*) FROM outbox").fetchone()[0])
