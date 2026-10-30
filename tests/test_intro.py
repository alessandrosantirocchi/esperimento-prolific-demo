"""Run with: python -m unittest discover -s tests."""

import unittest
from datetime import datetime
from pathlib import Path

from streamlit.testing.v1 import AppTest


APP = Path(__file__).resolve().parents[1] / "app.py"


class IntroductionTests(unittest.TestCase):
    def test_consent_is_required_and_can_be_unchecked(self):
        app = AppTest.from_file(str(APP)).run()
        self.assertFalse(app.exception)
        self.assertEqual(app.title[0].value, "Faces in the Digital Age")
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
        self.assertCountEqual(order, ["P001", "P002", "P003", "P004"])
        app.run()
        self.assertFalse(app.exception)
        self.assertEqual(len(app.checkbox), 0)
        self.assertEqual(app.session_state["intro_consent_accepted_at"], timestamp)
        self.assertEqual(app.session_state["feed_post_order"], order)


if __name__ == "__main__":
    unittest.main()
