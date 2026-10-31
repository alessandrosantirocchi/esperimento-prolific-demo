"""Transactional local event storage; deploy on a persistent disk for durability."""

from contextlib import closing
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sqlite3


class SessionDeletedError(sqlite3.DatabaseError):
    """A researcher deleted this session; delayed writes must not recreate it."""


def _deletion_table(connection):
    connection.execute("CREATE TABLE IF NOT EXISTS deleted_sessions (session_id TEXT PRIMARY KEY, deleted_at TEXT NOT NULL)")


def database_path() -> Path:
    return Path(os.environ.get(
        "INSTALAB_DB_PATH", Path(__file__).resolve().parent / ".local-data" / "events.sqlite3"
    ))


def save_events(session_id: str, events: list[dict], path: Path | None = None) -> None:
    """Commit a batch atomically; repeated delivery never duplicates an event."""
    destination = path if path is not None else database_path()
    destination.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(destination, timeout=30)) as connection:
        with connection:
            connection.execute("BEGIN IMMEDIATE")
            _deletion_table(connection)
            if connection.execute("SELECT 1 FROM deleted_sessions WHERE session_id=?", (session_id,)).fetchone():
                raise SessionDeletedError("This session was deleted")
            connection.execute("""
                CREATE TABLE IF NOT EXISTS events (
                    session_id TEXT NOT NULL,
                    event_id TEXT NOT NULL,
                    participant_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    server_received_ts TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    PRIMARY KEY (session_id, event_id)
                )
            """)
            connection.executemany(
                "INSERT INTO events VALUES (?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(session_id, event_id) DO NOTHING",
                [(session_id, e["event_id"], e["participant_id"], e["event_type"],
                  e["server_received_ts"], json.dumps(e, ensure_ascii=False)) for e in events],
            )


def delete_sessions(session_ids: list[str], path: Path | None = None) -> dict:
    """Delete only explicitly selected sessions, atomically and with bound IDs."""
    if isinstance(session_ids, str) or not session_ids or any(not isinstance(s, str) or not s.strip() for s in session_ids):
        raise ValueError("Select session IDs explicitly")
    selected = sorted(set(session_ids))
    if len(selected) > 500:
        raise ValueError("Select at most 500 sessions per operation")
    destination = path if path is not None else database_path()
    if not destination.exists():
        return {"sessions": 0, "events": 0}
    placeholders = ",".join("?" for _ in selected)
    with closing(sqlite3.connect(destination.resolve().as_uri() + "?mode=rw", uri=True, timeout=30)) as connection:
        with connection:
            connection.execute("BEGIN IMMEDIATE")
            if connection.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='events'").fetchone() is None:
                return {"sessions": 0, "events": 0}
            count = connection.execute(
                f"SELECT COUNT(DISTINCT session_id), COUNT(*) FROM events WHERE session_id IN ({placeholders})", selected
            ).fetchone()
            _deletion_table(connection)
            deleted_at = datetime.now(timezone.utc).isoformat()
            connection.executemany("INSERT OR IGNORE INTO deleted_sessions VALUES (?, ?)", [(s, deleted_at) for s in selected])
            connection.execute(f"DELETE FROM events WHERE session_id IN ({placeholders})", selected)
            return {"sessions": count[0], "events": count[1]}


def is_session_deleted(session_id: str, path: Path | None = None) -> bool:
    destination = path if path is not None else database_path()
    if not destination.exists():
        return False
    with closing(sqlite3.connect(destination.resolve().as_uri() + "?mode=ro", uri=True, timeout=30)) as connection:
        if connection.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='deleted_sessions'").fetchone() is None:
            return False
        return connection.execute("SELECT 1 FROM deleted_sessions WHERE session_id=?", (session_id,)).fetchone() is not None


def read_events(path: Path | None = None) -> list[dict]:
    """Read-only researcher export; never exposed to unauthenticated sessions."""
    destination = path if path is not None else database_path()
    if not destination.exists():
        return []
    with closing(sqlite3.connect(destination.resolve().as_uri() + "?mode=ro", uri=True, timeout=30)) as connection:
        if connection.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='events'").fetchone() is None:
            return []
        return [dict(json.loads(payload), session_id=session_id) for session_id, payload
                in connection.execute("SELECT session_id, payload FROM events ORDER BY rowid")]


if __name__ == "__main__":
    import argparse
    from export_data import csv_bytes

    parser = argparse.ArgumentParser(description="Export locally saved InstaLab events.")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    rows = read_events()
    args.output.write_bytes(csv_bytes(rows))
    print(f"Exported {len(rows)} events.")
