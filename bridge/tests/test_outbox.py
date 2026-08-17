from pathlib import Path

from reksa_bridge.outbox import SqliteOutbox


def test_outbox_is_durable_and_deduplicates(tmp_path: Path) -> None:
    path = tmp_path / "outbox.db"
    first = SqliteOutbox(path)
    assert first.enqueue("m-1", "REKSA/helmet/W01/sensor", "{}") is True
    assert first.enqueue("m-1", "REKSA/helmet/W01/sensor", "{}") is False
    first.mark_attempt("m-1")

    reopened = SqliteOutbox(path)
    assert reopened.count() == 1
    assert reopened.pending()[0].attempts == 1
    reopened.mark_delivered("m-1")
    assert reopened.count() == 0
    assert reopened.was_delivered("m-1") is True
    assert reopened.enqueue("m-1", "REKSA/helmet/W01/sensor", "{}") is False

    delivered_reopened = SqliteOutbox(path)
    assert delivered_reopened.was_delivered("m-1") is True
    assert delivered_reopened.enqueue("m-1", "REKSA/helmet/W01/sensor", "{}") is False
