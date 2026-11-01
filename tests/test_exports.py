import csv
import io
import json
import unittest

from export_data import csv_bytes, filter_events, final_reactions


def record(session, participant, kind, post="P001", **fields):
    return {"session_id": session, "participant_id": participant, "event_type": kind,
            "event_id": session + kind, "post_id": post,
            "server_received_ts": "2026-10-31T10:00:00+00:00", **fields}


class ExportTests(unittest.TestCase):
    def setUp(self):
        self.events = [record("s1", "A", "like"), record("s1", "A", "unlike"),
                       record("s1", "A", "dislike"),
                       record("s1", "A", "recognition_response", details={"response": "OLD", "target": "NEW", "correct": False, "response_time_ms": 425}),
                       record("s1", "A", "recognition_completed"),
                       record("s2", "A", "like"), record("s2", "A", "unlike"),
                       record("s3", "B", "dislike")]

    def test_filters_combine_participant_session_phase_and_completion(self):
        rows = filter_events(self.events, participant_id="A", phase="recognition", completed_only=True)
        self.assertEqual([r["event_type"] for r in rows], ["recognition_response", "recognition_completed"])
        self.assertEqual(len(filter_events(self.events, session_ids=["s3"])), 1)
        self.assertEqual(filter_events(self.events, participant_id="B", completed_only=True), [])
        self.assertEqual(len(filter_events(self.events)), len(self.events))

    def test_final_reactions_are_per_session_and_include_removals(self):
        rows = final_reactions(self.events)
        self.assertEqual({r["session_id"]: r["reaction"] for r in rows}, {"s1": "DISLIKE", "s2": "NONE", "s3": "DISLIKE"})

    def test_csv_exports_scores_false_values_and_safe_user_text(self):
        events = self.events + [record("s4", "=1+1", "comment_submit", details={"text": "è un volto"})]
        data = csv_bytes(events)
        rows = list(csv.DictReader(io.StringIO(data.decode("utf-8-sig"))))
        response = rows[3]
        self.assertEqual(response["correct"], "False")
        self.assertEqual(response["response_time_ms"], "425")
        self.assertEqual(rows[-1]["participant_id"], "'=1+1")
        self.assertEqual(json.loads(rows[-1]["details"])["text"], "è un volto")
        self.assertEqual(events[-1]["participant_id"], "=1+1")

    def test_confidence_exports_values_and_preserves_missing_legacy_ratings(self):
        current = record("current", "A", "recognition_response", details={
            "response": "OLD", "target": "OLD", "correct": True, "response_time_ms": 425,
            "confidence": 4, "confidence_response_time_ms": 850, "confidence_scale_version": 1})
        legacy = record("legacy", "B", "recognition_response", details={"response": "NEW"})
        rows = list(csv.DictReader(io.StringIO(csv_bytes([current, legacy]).decode("utf-8-sig"))))
        self.assertEqual(rows[0]["confidence"], "4")
        self.assertEqual(rows[0]["confidence_response_time_ms"], "850")
        self.assertEqual(rows[0]["response_time_ms"], "425")
        self.assertEqual(rows[0]["confidence_scale_version"], "1")
        self.assertEqual(rows[1]["confidence"], "")
        self.assertEqual(rows[1]["confidence_response_time_ms"], "")
