"""Aggregate immutable feed events; never reconstruct exposure from impressions."""

from collections import defaultdict
import math

TRACKING_VERSION = 1
DURATION_FIELDS = ("total_view_duration_ms", "first_view_duration_ms", "view_count",
                   "mean_view_duration_ms", "max_view_duration_ms")
SOCIAL_TYPES = {"like", "unlike", "dislike", "remove_dislike", "save", "unsave",
                "open_comments", "expand_comments", "comment_submit", "share_confirmed"}
FEED_METRIC_COLUMNS = (
    "participant_id", "session_id", "stimulus_id", "post_id", "filename",
    "stimulus_type", "source_type", "gender", "feed_position",
    *DURATION_FIELDS, "liked", "like_count", "unlike_count", "disliked", "dislike_count",
    "remove_dislike_count", "saved", "comment_open_count", "comment_count",
    "shared_count", "interaction_count", "metrics_status", "metrics_missing",
    "feed_finalized", "tracking_version",
)


def valid_view_details(details):
    if not isinstance(details, dict):
        return False
    duration = details.get("duration_ms")
    return (details.get("tracking_version") == TRACKING_VERSION
            and isinstance(details.get("exposure_id"), str) and 0 < len(details["exposure_id"]) <= 128
            and type(details.get("exposure_index")) is int and details["exposure_index"] > 0
            and type(duration) in {int, float} and math.isfinite(duration) and duration >= 0
            and type(details.get("closed")) is bool)


def feed_metrics_rows(events, finalized_only=True):
    """One assigned feed post/session; final exports exclude still-running feeds.

    Closed legacy sessions are included with blank timing, not invented zeroes.
    Diagnostic callers may request provisional rows, explicitly marked incomplete.
    """
    sessions, seen = defaultdict(list), set()
    for event in events:
        session = event.get("session_id")
        key = (session, event.get("event_id"))
        if not session or (event.get("event_id") and key in seen):
            continue
        seen.add(key)
        sessions[session].append(event)
    result = []
    for session, rows in sessions.items():
        start = next((e for e in rows if e.get("event_type") == "session_started"), None)
        if not start:
            continue  # No assignment record: do not invent unobserved feed posts.
        details = start.get("details", {})
        order = details.get("post_order", [])
        metadata = {p["id"]: p for p in details.get("stimuli", []) if isinstance(p, dict) and "id" in p}
        tracked = any(e.get("event_type") == "feed_tracking_started" and
                      e.get("details", {}).get("tracking_version") == TRACKING_VERSION for e in rows)
        finalized = any(e.get("event_type") == "feed_tracking_finalized" and
                        e.get("details", {}).get("tracking_version") == TRACKING_VERSION for e in rows)
        phase_ended = finalized or any(e.get("event_type") in {"begin_recognition", "recognition_started", "recognition_response", "recognition_completed"} for e in rows)
        if finalized_only and not phase_ended:
            continue
        status = "complete" if tracked and finalized else "incomplete" if tracked else "unavailable"
        post_events = defaultdict(list)
        for event in rows:
            if event.get("phase", "feed") == "feed" and event.get("post_id") in order:
                post_events[event["post_id"]].append(event)
        for position, post_id in enumerate(order, 1):
            post = metadata.get(post_id) or next(iter(post_events[post_id]), {})
            category = post.get("source_type", "")
            row = {"participant_id": start.get("participant_id", ""), "session_id": session,
                   "post_id": post_id, "stimulus_id": post.get("stimulus_id", ""),
                   "filename": post.get("filename", ""), "source_type": category,
                   "stimulus_type": {"real": "Real", "gan": "GAN", "transformer": "Transformer"}.get(category, ""),
                   "gender": post.get("gender", ""), "feed_position": position,
                   "metrics_status": status, "metrics_missing": int(status != "complete"),
                   "feed_finalized": int(finalized), "tracking_version": TRACKING_VERSION if tracked else "",
                   **{name: None for name in DURATION_FIELDS},
                   **{name: 0 for name in ("liked", "like_count", "unlike_count", "disliked", "dislike_count",
                      "remove_dislike_count", "saved", "comment_open_count", "comment_count", "shared_count", "interaction_count")}}
            exposures, actions = {}, set()
            for event in post_events[post_id]:
                kind = event.get("event_type")
                info = event.get("details") if isinstance(event.get("details"), dict) else {}
                if kind == "feed_view" and valid_view_details(info):
                    exposure = exposures.setdefault(info["exposure_id"], {"duration": 0, "closed": False,
                        "index": info["exposure_index"], "start": info.get("started_client_ts", "")})
                    exposure["duration"] = max(exposure["duration"], info["duration_ms"])
                    exposure["closed"] |= info["closed"]
                if kind not in SOCIAL_TYPES:
                    continue
                if kind == "comment_submit" and not str(info.get("text", "")).strip():
                    continue
                action_id = info.get("action_id")
                actions.add(action_id if isinstance(action_id, str) and action_id else event.get("event_id"))
                if kind == "like":
                    row["liked"], row["disliked"] = 1, 0
                    row["like_count"] += 1
                elif kind == "unlike":
                    row["liked"] = 0;row["unlike_count"] += 1
                elif kind == "dislike":
                    row["disliked"], row["liked"] = 1, 0
                    row["dislike_count"] += 1
                elif kind == "remove_dislike":
                    row["disliked"] = 0;row["remove_dislike_count"] += 1
                elif kind in {"save", "unsave"}:
                    row["saved"] = int(kind == "save")
                elif kind in {"open_comments", "expand_comments"}:
                    row["comment_open_count"] += 1
                elif kind == "comment_submit":
                    row["comment_count"] += 1
                elif kind == "share_confirmed":
                    row["shared_count"] += 1
            row["interaction_count"] = len(actions)
            # A finalization marker with an unclosed exposure means missing data.
            if status == "complete" and not all(e["closed"] for e in exposures.values()):
                row.update(metrics_status="incomplete", metrics_missing=1)
            elif status == "complete":
                durations = [e["duration"] for e in sorted(exposures.values(), key=lambda e: (e["index"], e["start"]))]
                row.update(total_view_duration_ms=sum(durations), first_view_duration_ms=durations[0] if durations else 0,
                           view_count=len(durations), mean_view_duration_ms=round(sum(durations)/len(durations), 3) if durations else 0,
                           max_view_duration_ms=max(durations, default=0))
            result.append(row)
    return result
