"""Run with: python -m unittest discover -s tests."""

import unittest
import json
import sqlite3
from unittest.mock import patch
from datetime import datetime
from pathlib import Path

from streamlit.testing.v1 import AppTest


APP = Path(__file__).resolve().parents[1] / "app.py"


class IntroductionTests(unittest.TestCase):
    def setUp(self):
        storage = patch("event_store.save_events")
        self.storage = storage.start()
        self.addCleanup(storage.stop)

    def test_consent_is_required_and_can_be_unchecked(self):
        app = AppTest.from_file(str(APP)).run()
        self.assertFalse(app.exception)
        self.assertEqual(app.title[0].value, "Faces in the Digital Age")
        self.assertEqual(len(app.warning), 0)
        self.assertEqual(app.expander[0].label, "Informazioni sullo studio — da completare")
        self.assertTrue(any("DA COMPLETARE" in text.value for text in app.markdown))
        self.assertTrue(app.button[0].disabled)
        self.assertNotIn("feed_events", app.session_state)
        app.checkbox[0].check().run()
        self.assertFalse(app.button[0].disabled)
        self.assertFalse(app.session_state.get("intro_consent_accepted", False))
        app.checkbox[0].uncheck().run()
        self.assertTrue(app.button[0].disabled)

    def test_acceptance_preserves_participant_and_survives_rerun(self):
        app = AppTest.from_file(str(APP))
        app.query_params["PROLIFIC_PID"] = "TEST001"
        app.run()
        app.checkbox[0].check().run()
        app.button[0].click().run()
        self.assertFalse(app.exception)
        self.assertTrue(app.session_state["intro_consent_accepted"])
        self.assertEqual(app.session_state["intro_consent_participant_id"], "TEST001")
        self.assertEqual(app.query_params["PROLIFIC_PID"], "TEST001")
        timestamp = app.session_state["intro_consent_accepted_at"]
        self.assertIsNotNone(datetime.fromisoformat(timestamp).tzinfo)
        self.assertIn("feed_events", app.session_state)
        order = list(app.session_state["feed_post_order"])
        self.assertCountEqual(order, [f"P{i:03}" for i in range(1, 21)])
        app.run()
        self.assertFalse(app.exception)
        self.assertEqual(len(app.checkbox), 0)
        self.assertEqual(app.session_state["intro_consent_accepted_at"], timestamp)
        self.assertEqual(app.session_state["feed_post_order"], order)

    def test_provisional_stimuli_are_balanced_and_available(self):
        posts = json.loads((APP.parent / "posts.json").read_text())["posts"]
        self.assertEqual(len(posts), 20)
        self.assertEqual(sum(p["stimulus_type"] == "real" for p in posts), 10)
        self.assertEqual(sum(p["stimulus_type"] == "deepfake" for p in posts), 10)
        self.assertEqual(len({p["stimulus_id"] for p in posts}), 20)
        for post in posts:
            self.assertTrue((APP.parent / post["image"]).is_file())
        regions = [tuple(p["image_region"].values()) for p in posts if "image_region" in p]
        self.assertEqual(len(set(regions)), 10)

    def test_failed_storage_is_reported_and_can_be_retried(self):
        self.storage.side_effect = sqlite3.OperationalError("database is locked")
        app = AppTest.from_file(str(APP)).run()
        app.checkbox[0].check().run()
        app.button[0].click().run()
        self.assertFalse(app.exception)
        self.assertEqual(len(app.error), 1)
        self.assertEqual(app.session_state["feed_events"], [])
        self.assertEqual(app.session_state["seen_event_ids"], set())
        self.storage.side_effect = None
        app.run()
        self.assertFalse(app.exception)
        self.assertEqual(len(app.error), 0)
        self.assertEqual(app.session_state["feed_events"][0]["event_type"], "session_started")


if __name__ == "__main__":
    unittest.main()
