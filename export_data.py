"""Researcher filtering and spreadsheet-safe CSV exports."""

import csv
import io
import json

EVENT_COLUMNS = (
    "session_id", "event_id", "participant_id", "event_type", "post_id",
    "stimulus_id", "filename", "source_type", "gender", "stimulus_type", "feed_position", "client_ts", "server_received_ts", "phase",
    "trial_id", "response", "target", "correct", "response_time_ms",
    "displayed_client_ts", "elapsed_ms", "details",
)
REACTION_TYPES = {"like", "unlike", "dislike", "remove_dislike"}
REACTION_COLUMNS = (
    "session_id", "participant_id", "post_id", "stimulus_id", "filename", "source_type", "gender", "stimulus_type",
    "reaction", "last_server_received_ts",
)


def event_phase(event):
    return event.get("phase") or ("recognition" if event.get("event_type", "").startswith("recognition_") else "feed")


def filter_events(events, participant_id=None, session_ids=(), phase=None, completed_only=False):
    completed = {e["session_id"] for e in events if e.get("event_type") == "recognition_completed"}
    sessions = set(session_ids)
    return [e for e in events
            if (participant_id is None or e.get("participant_id") == participant_id)
            and (not sessions or e.get("session_id") in sessions)
            and (phase is None or event_phase(e) == phase)
            and (not completed_only or e.get("session_id") in completed)]


def final_reactions(events):
    rows = {}
    for event in events:
        kind = event.get("event_type")
        if kind not in REACTION_TYPES or not event.get("post_id"):
            continue
        key = (event["session_id"], event["post_id"])
        row = rows.setdefault(key, {name: event.get(name, "") for name in REACTION_COLUMNS})
        state = row.get("reaction") or "NONE"
        if kind in {"like", "dislike"}:
            state = kind.upper()
        elif (kind == "unlike" and state == "LIKE") or (kind == "remove_dislike" and state == "DISLIKE"):
            state = "NONE"
        row["reaction"] = state
        row["last_server_received_ts"] = event.get("server_received_ts", "")
    return list(rows.values())


def csv_bytes(events, columns=EVENT_COLUMNS):
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=columns)
    writer.writeheader()
    for event in events:
        details = event.get("details") if isinstance(event.get("details"), dict) else {}
        row = {}
        for column in columns:
            value = json.dumps(details, ensure_ascii=False) if column == "details" else event.get(column, details.get(column, ""))
            # Spreadsheet programs can execute formulas in user-supplied text cells.
            if isinstance(value, str) and (value.startswith(("\t", "\r", "\n")) or value.lstrip().startswith(("=", "+", "-", "@"))):
                value = "'" + value
            row[column] = value
        writer.writerow(row)
    return stream.getvalue().encode("utf-8-sig")
