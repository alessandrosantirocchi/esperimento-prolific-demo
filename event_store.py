"""Transactional local event storage; deploy on a persistent disk for durability."""

from contextlib import closing
import json
import os
from pathlib import Path
import sqlite3


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


def read_events(path: Path | None = None) -> list[dict]:
    """Server-side researcher export; never exposed to participant sessions."""
    destination = path if path is not None else database_path()
    if not destination.exists():
        return []
    with closing(sqlite3.connect(destination, timeout=30)) as connection:
        return [dict(json.loads(payload), session_id=session_id) for session_id, payload
                in connection.execute("SELECT session_id, payload FROM events ORDER BY rowid")]


if __name__ == "__main__":
    import argparse
    import csv

    parser = argparse.ArgumentParser(description="Export locally saved InstaLab events.")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    rows = read_events()
    columns = ["session_id", "event_id", "participant_id", "event_type", "post_id",
               "stimulus_id", "stimulus_type", "client_ts", "server_received_ts",
               "phase", "trial_id", "response", "target", "correct", "response_time_ms",
               "displayed_client_ts", "elapsed_ms", "details"]
    with args.output.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            details = row.get("details", {})
            writer.writerow({**details, **row, "details": json.dumps(details, ensure_ascii=False)})
    print(f"Exported {len(rows)} events.")
