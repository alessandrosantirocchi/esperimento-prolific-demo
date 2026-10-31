import csv
import io
import unittest

from export_data import csv_bytes, final_reactions, REACTION_COLUMNS
from feed_metrics import feed_metrics_rows, FEED_METRIC_COLUMNS
from participant_data import validate_demographics, participant_rows, PARTICIPANT_COLUMNS
from stimulus_catalog import public_history


class ParticipantDataTests(unittest.TestCase):
    def test_incomplete_or_invalid_answers_are_rejected_without_age_eligibility_rule(self):
        for values in ((None,24,"bachelor"),("woman",None,"bachelor"),("woman",24,None),
                       ("invalid",24,"bachelor"),("woman",-1,"bachelor"),("woman",24.5,"bachelor"),
                       ([],24,"bachelor"),("woman",True,"bachelor")):
            with self.subTest(values=values), self.assertRaises(ValueError):
                validate_demographics(*values)
        self.assertEqual(validate_demographics("prefer_not_to_say",0,"other")["participant_age"],0)

    def test_profile_export_is_one_row_per_session_and_keeps_refusals(self):
        values = validate_demographics("prefer_not_to_say",24,"prefer_not_to_say")
        event = {"event_id":"demographics_submitted","event_type":"demographics_submitted",
                 "participant_id":"P_1","session_id":"s1","server_received_ts":"2026-10-31T20:00:00Z",**values}
        rows = participant_rows([event,event,{**event,"session_id":"s2"}])
        self.assertEqual(len(rows),2)
        decoded = list(csv.DictReader(io.StringIO(csv_bytes(rows,PARTICIPANT_COLUMNS).decode("utf-8-sig"))))
        self.assertEqual(decoded[0]["participant_gender"],"prefer_not_to_say")
        self.assertEqual(decoded[0]["participant_age"],"24")

    def test_demographics_follow_exports_without_overwriting_stimulus_gender(self):
        values = validate_demographics("woman",32,"master")
        base = {"session_id":"s","participant_id":"P",**values}
        start = {**base,"event_id":"start","event_type":"session_started","details":{
            "post_order":["p"],"stimuli":[{"id":"p","stimulus_id":"face","source_type":"gan","gender":"M"}]}}
        like = {**base,"event_id":"like","event_type":"like","post_id":"p","gender":"M","details":{}}
        events = [start,like,{**base,"event_id":"tracking","event_type":"feed_tracking_started","details":{"tracking_version":1}},
                  {**base,"event_id":"end","event_type":"feed_tracking_finalized","details":{"tracking_version":1}}]
        for rows, columns in ((events,None),(final_reactions(events),REACTION_COLUMNS),(feed_metrics_rows(events),FEED_METRIC_COLUMNS)):
            data = csv_bytes(rows) if columns is None else csv_bytes(rows,columns)
            decoded = list(csv.DictReader(io.StringIO(data.decode("utf-8-sig"))))
            self.assertTrue(all(r["participant_gender"]=="woman" and r["participant_age"]=="32" and r["participant_education"]=="master" for r in decoded))
        self.assertEqual(feed_metrics_rows(events)[0]["gender"],"M")
        self.assertNotIn("participant_gender",public_history([like])[0])

    def test_legacy_data_remains_blank_instead_of_invented_demographics(self):
        data = csv_bytes([{"event_id":"old","event_type":"like"}]).decode("utf-8-sig")
        row = next(csv.DictReader(io.StringIO(data)))
        self.assertEqual(row["participant_age"],"")
        self.assertEqual(row["participant_gender"],"")
        self.assertEqual(row["participant_education"],"")
