"""Run with: python -m unittest discover -s tests."""

import unittest
import sqlite3
import tempfile
from unittest.mock import patch
from datetime import datetime
from pathlib import Path

from streamlit.testing.v1 import AppTest
from catalog_fixture import create_catalog
from stimulus_catalog import load_catalog, select_sets


APP = Path(__file__).resolve().parents[1] / "app.py"


class IntroductionTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.catalog = load_catalog(create_catalog(folder.name))
        catalog = patch("stimulus_catalog.load_catalog", return_value=self.catalog)
        catalog.start()
        self.addCleanup(catalog.stop)
        storage = patch("event_store.save_events")
        self.storage = storage.start()
        self.addCleanup(storage.stop)
        deleted = patch("event_store.is_session_deleted", return_value=False)
        deleted.start()
        self.addCleanup(deleted.stop)

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
        self.assertCountEqual(order, app.session_state["stimulus_selection"]["feed"])
        self.assertEqual(len(order), 30)
        self.assertEqual(len(app.session_state["recognition_plan"]), 60)
        app.run()
        self.assertFalse(app.exception)
        self.assertEqual(len(app.checkbox), 0)
        self.assertEqual(app.session_state["intro_consent_accepted_at"], timestamp)
        self.assertEqual(app.session_state["feed_post_order"], order)
        assignments = [e for e in app.session_state["feed_events"] if e["event_type"] == "recognition_plan_assigned"]
        self.assertEqual(len(assignments), 1)
        self.assertEqual(assignments[0]["details"]["recognition_plan"], app.session_state["recognition_plan"])

    def test_catalog_reserves_distinct_new_faces(self):
        selection = select_sets(self.catalog)
        self.assertEqual(len(selection["feed"]), 30)
        self.assertEqual(len(selection["new"]), 30)
        self.assertFalse(set(selection["feed"]) & set(selection["new"]))

    def test_previous_protocol_session_stops_before_adding_new_events(self):
        app = AppTest.from_file(str(APP)).run()
        app.checkbox[0].check().run()
        app.button[0].click().run()
        calls = self.storage.call_count
        app.session_state["stimulus_selection"] = {**app.session_state["stimulus_selection"],
                                                  "protocol_version": "previous-protocol"}
        app.run()
        self.assertFalse(app.exception)
        self.assertIn("configurazione dello studio è cambiata", app.error[0].value)
        self.assertEqual(self.storage.call_count, calls)

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

    def test_memory_instructions_appear_only_after_first_phase(self):
        app = AppTest.from_file(str(APP)).run()
        app.checkbox[0].check().run()
        app.button[0].click().run()
        self.assertFalse(app.exception)
        self.assertFalse(any("Hai già visto" in title.value for title in app.title))
        plan = list(app.session_state["recognition_plan"])
        app.session_state["experiment_phase"] = "recognition_intro"
        app.run()
        self.assertEqual(app.title[0].value, "Hai già visto questo volto?")
        self.assertTrue(any("OLD — Già visto" in text.value for text in app.markdown))
        app.button[0].click().run()
        self.assertFalse(app.exception)
        self.assertEqual(app.session_state["experiment_phase"], "recognition")
        self.assertEqual(app.session_state["recognition_plan"], plan)
        self.assertTrue(any(e["event_type"] == "recognition_started" for e in app.session_state["feed_events"]))


if __name__ == "__main__":
    unittest.main()
