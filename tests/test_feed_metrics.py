import csv
import io
import unittest

from export_data import csv_bytes
from feed_metrics import FEED_METRIC_COLUMNS, feed_metrics_rows, valid_view_details


def event(kind, post=None, **details):
    return {"event_id": f"{kind}-{post}-{details}", "event_type": kind, "phase": "feed",
            "participant_id": "person", "session_id": "session", "post_id": post, "details": details}


def assignment():
    return event("session_started", post_order=["p1", "p2"], stimuli=[
        {"id": "p1", "stimulus_id": "s1", "filename": "a.png", "source_type": "gan", "gender": "F"},
        {"id": "p2", "stimulus_id": "s2", "filename": "b.png", "source_type": "real", "gender": "M"},
        {"id": "lure", "stimulus_id": "new", "source_type": "transformer", "gender": "F"}])


def view(exposure, index, duration, closed):
    return event("feed_view", "p1", tracking_version=1, exposure_id=exposure,
                 exposure_index=index, duration_ms=duration, closed=closed)


class FeedMetricsTests(unittest.TestCase):
    def complete(self, *records):
        return [assignment(), event("feed_tracking_started", tracking_version=1), *records,
                event("feed_tracking_finalized", tracking_version=1)]

    def test_cumulative_checkpoints_deduplicate_and_include_unseen_faces(self):
        close = view("first", 1, 900, True)
        records = self.complete(view("first", 1, 0, False), view("first", 1, 500, False), close, close,
                                view("second", 2, 300, True), view("first", 1, 700, False))
        rows = feed_metrics_rows(records)
        self.assertEqual(len(rows), 2)
        first, unseen = rows
        self.assertEqual([first[k] for k in ("total_view_duration_ms", "first_view_duration_ms", "view_count", "mean_view_duration_ms", "max_view_duration_ms")], [1200, 900, 2, 600, 900])
        self.assertEqual(first["stimulus_type"], "GAN")
        self.assertEqual(first["feed_position"], 1)
        self.assertEqual(first["stimulus_id"], "s1")
        self.assertEqual(unseen["view_count"], 0)
        self.assertEqual(unseen["total_view_duration_ms"], 0)
        self.assertEqual(unseen["metrics_missing"], 0)
        self.assertEqual(unseen["feed_position"], 2)
        self.assertNotIn("new", {r["stimulus_id"] for r in rows})

    def test_social_states_and_counts_do_not_double_count_automatic_removal(self):
        records = self.complete(event("like", "p1", action_id="one"), event("unlike", "p1", action_id="two"),
            event("like", "p1", action_id="three"), event("unlike", "p1", action_id="four"),
            event("dislike", "p1", action_id="four"), event("save", "p1"), event("unsave", "p1"),
            event("save", "p1", action_id="five"), event("open_comments", "p1"),
            event("expand_comments", "p1"), event("comment_submit", "p1", text="hello"),
            event("comment_submit", "p1", text="   "), event("share_confirmed", "p1"))
        row = feed_metrics_rows(records)[0]
        self.assertEqual((row["liked"], row["like_count"], row["unlike_count"]), (0, 2, 2))
        self.assertEqual((row["disliked"], row["dislike_count"]), (1, 1))
        self.assertEqual(row["saved"], 1)
        self.assertEqual(row["comment_open_count"], 2)
        self.assertEqual(row["comment_count"], 1)
        self.assertEqual(row["shared_count"], 1)
        self.assertEqual(row["interaction_count"], 11)

    def test_active_or_interrupted_feeds_are_not_exported_as_final(self):
        records = [assignment(), event("feed_tracking_started", tracking_version=1), view("open", 1, 500, False)]
        self.assertEqual(feed_metrics_rows(records), [])
        row = feed_metrics_rows(records, finalized_only=False)[0]
        self.assertEqual(row["metrics_missing"], 1)
        self.assertIsNone(row["view_count"])
        self.assertEqual(row["metrics_status"], "incomplete")

    def test_missing_instrumentation_and_unclosed_exposures_are_not_zero(self):
        for records in ([assignment(), event("begin_recognition")], self.complete(view("open", 1, 500, False))):
            row = feed_metrics_rows(records)[0]
            self.assertEqual(row["metrics_missing"], 1)
            self.assertIsNone(row["view_count"])
            self.assertIsNone(row["total_view_duration_ms"])

    def test_sessions_and_recognition_events_remain_separate(self):
        records = self.complete(view("first", 1, 400, True))
        second = [{**r, "session_id": "other"} for r in self.complete()]
        memory = {**event("like", "p2"), "phase": "recognition"}
        rows = feed_metrics_rows(records + second + [memory])
        self.assertEqual(len(rows), 4)
        self.assertEqual(rows[2]["view_count"], 0)
        self.assertEqual(rows[1]["liked"], 0)
        decoded = list(csv.DictReader(io.StringIO(csv_bytes(rows, FEED_METRIC_COLUMNS).decode("utf-8-sig"))))
        self.assertEqual(decoded[0]["total_view_duration_ms"], "400")
        self.assertEqual(decoded[2]["view_count"], "0")

    def test_invalid_durations_and_identifiers_are_rejected(self):
        base = view("ok", 1, 100, True)["details"]
        self.assertTrue(valid_view_details(base))
        for field, value in (("duration_ms", float("nan")), ("duration_ms", -1), ("duration_ms", True),
                             ("closed", "true"), ("exposure_id", []), ("exposure_index", 0)):
            self.assertFalse(valid_view_details({**base, field: value}))
