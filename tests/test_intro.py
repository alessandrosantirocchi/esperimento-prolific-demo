"""Run with: python -m unittest discover -s tests."""

import unittest
import sqlite3
import tempfile
from unittest.mock import patch
from datetime import datetime
from pathlib import Path
from types import ModuleType
import uuid

from streamlit.testing.v1 import AppTest
from catalog_fixture import create_catalog
from stimulus_catalog import load_catalog, select_sets
from image_assets import prepare_image


APP = Path(__file__).resolve().parents[1] / "app.py"


class IntroductionTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.catalog = load_catalog(create_catalog(folder.name))
        catalog = patch("stimulus_catalog.load_catalog", return_value=self.catalog)
        self.catalog_loader = catalog.start()
        self.addCleanup(catalog.stop)
        storage = patch("event_store.save_events")
        self.storage = storage.start()
        self.addCleanup(storage.stop)
        deleted = patch("event_store.is_session_deleted", return_value=False)
        deleted.start()
        self.addCleanup(deleted.stop)
        prefetch = patch("image_assets.prefetch_images")
        self.prefetch_loader = prefetch.start()
        self.addCleanup(prefetch.stop)

    def complete_details(self, app, gender="woman", age=24, education="bachelor", start_feed=True):
        next(s for s in app.selectbox if s.key == "demographic_gender").set_value(gender)
        app.number_input[0].set_value(age)
        next(s for s in app.selectbox if s.key == "demographic_education").set_value(education)
        next(b for b in app.button if b.label == "Continua").click().run()
        if start_feed:
            button = next((b for b in app.button if b.key == "start_feed_button"), None)
            if button:
                button.click().run()

    def test_consent_is_required_and_can_be_unchecked(self):
        app = AppTest.from_file(str(APP)).run()
        self.assertFalse(app.exception)
        self.assertEqual(app.title[0].value, "Faces in the Digital Age")
        self.assertEqual(len(app.warning), 0)
        self.assertEqual(app.expander[0].label, "Consenso informato")
        self.assertTrue(any("DA COMPLETARE" in text.value for text in app.markdown))
        self.assertTrue(app.button[0].disabled)
        self.assertNotIn("feed_events", app.session_state)
        app.checkbox[0].check().run()
        self.assertFalse(app.button[0].disabled)
        self.assertFalse(app.session_state.get("intro_consent_accepted", False))
        app.checkbox[0].uncheck().run()
        self.assertTrue(app.button[0].disabled)

    def test_acceptance_preserves_participant_and_survives_rerun(self):
        app = AppTest.from_file(str(APP)).run()
        participant = app.session_state["participant_id"]
        self.assertTrue(participant.startswith("P_"))
        self.assertEqual(uuid.UUID(hex=participant[2:]).version, 4)
        app.checkbox[0].check().run()
        app.button[0].click().run()
        self.complete_details(app)
        self.assertFalse(app.exception)
        self.assertTrue(app.session_state["intro_consent_accepted"])
        self.assertEqual(app.session_state["intro_consent_participant_id"], participant)
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
        self.assertEqual(app.session_state["participant_id"], participant)
        self.assertEqual({e["participant_id"] for e in app.session_state["feed_events"]}, {participant})
        assignments = [e for e in app.session_state["feed_events"] if e["event_type"] == "recognition_plan_assigned"]
        self.assertEqual(len(assignments), 1)
        self.assertEqual(assignments[0]["details"]["recognition_plan"], app.session_state["recognition_plan"])

    def test_plain_link_sessions_get_distinct_participant_codes_before_consent(self):
        first = AppTest.from_file(str(APP)).run()
        second = AppTest.from_file(str(APP)).run()
        self.assertNotEqual(first.session_state["participant_id"], second.session_state["participant_id"])
        self.storage.assert_not_called()

    def test_query_parameters_do_not_supply_or_change_the_participant_code(self):
        app = AppTest.from_file(str(APP))
        app.query_params["PROLIFIC_PID"] = "OLD_EXTERNAL_ID"
        app.query_params["participant_id"] = "ANOTHER_EXTERNAL_ID"
        app.run()
        participant = app.session_state["participant_id"]
        self.assertNotIn(participant, {"OLD_EXTERNAL_ID", "ANOTHER_EXTERNAL_ID"})
        app.query_params["PROLIFIC_PID"] = "CHANGED_EXTERNAL_ID"
        app.run()
        self.assertEqual(app.session_state["participant_id"], participant)

    def test_active_legacy_session_retains_its_original_participant_code(self):
        app = AppTest.from_file(str(APP)).run()
        app.checkbox[0].check().run()
        app.button[0].click().run()
        self.complete_details(app)
        session = app.session_state["recording_session_id"]
        del app.session_state["participant_id"]
        del app.session_state["participant_demographics"]
        del app.session_state["demographics_completed"]
        del app.session_state["feed_instructions_completed"]
        app.session_state["intro_consent_participant_id"] = "LEGACY_PARTICIPANT"
        app.session_state["feed_events"] = [{**e, "participant_id":"LEGACY_PARTICIPANT"} for e in app.session_state["feed_events"]]
        calls = self.storage.call_count
        app.run()
        self.assertFalse(app.exception)
        self.assertEqual(app.session_state["participant_id"], "LEGACY_PARTICIPANT")
        self.assertEqual(app.session_state["recording_session_id"], session)
        self.assertEqual(self.storage.call_count, calls)
        self.assertFalse(any(b.key == "start_feed_button" for b in app.button))

    def test_feed_instructions_follow_demographics_before_faces_and_timers(self):
        app = AppTest.from_file(str(APP)).run()
        app.checkbox[0].check().run()
        app.button[0].click().run()
        participant = app.session_state["participant_id"]
        session = app.session_state["recording_session_id"]
        self.complete_details(app, start_feed=False)
        self.assertFalse(app.exception)
        self.assertEqual(app.title[0].value, "Prima di aprire il feed")
        self.catalog_loader.assert_not_called()
        self.assertNotIn("stimulus_selection", app.session_state)
        self.assertNotIn("recognition_plan", app.session_state)
        self.assertEqual([e["event_type"] for e in app.session_state["feed_events"]], ["demographics_submitted"])
        text = " ".join(item.value for item in app.markdown)
        for label in ("Scorri al tuo ritmo", "Like", "Dislike", "commento", "seconda fase"):
            self.assertIn(label, text)
        for spoiler in ("OLD", "NEW", "riconoscimento", "memoria", "GAN", "Transformer"):
            self.assertNotIn(spoiler, text)
        calls = self.storage.call_count
        app.run()
        self.assertEqual(app.title[0].value, "Prima di aprire il feed")
        self.assertEqual(self.storage.call_count, calls)
        self.catalog_loader.assert_not_called()
        next(b for b in app.button if b.key == "start_feed_button").click().run()
        self.assertFalse(app.exception)
        self.assertTrue(app.session_state["feed_instructions_completed"])
        self.assertEqual(app.session_state["participant_id"], participant)
        self.assertEqual(app.session_state["recording_session_id"], session)
        self.assertEqual(len(app.session_state["feed_post_order"]), 30)
        self.assertEqual(len(app.session_state["recognition_plan"]), 60)
        order = list(app.session_state["feed_post_order"])
        app.run()
        self.assertFalse(any(b.key == "start_feed_button" for b in app.button))
        self.assertEqual(app.session_state["feed_post_order"], order)
        self.assertEqual(len([e for e in app.session_state["feed_events"] if e["event_type"] == "demographics_submitted"]), 1)

    def test_demographics_are_required_between_consent_and_feed(self):
        app = AppTest.from_file(str(APP)).run()
        app.checkbox[0].check().run()
        app.button[0].click().run()
        self.assertEqual(app.title[0].value, "Prima di iniziare")
        self.assertTrue(all(s.value is None for s in app.selectbox))
        self.assertIsNone(app.number_input[0].value)
        self.catalog_loader.assert_not_called()
        self.storage.assert_not_called()
        app.button[0].click().run()
        self.assertEqual(len(app.error), 1)
        self.assertNotIn("stimulus_selection", app.session_state)
        self.complete_details(app, gender="prefer_not_to_say", age=0, education="other")
        self.assertFalse(app.exception)
        self.assertTrue(app.session_state["demographics_completed"])
        self.assertEqual(app.session_state["participant_demographics"],
                         {"participant_gender":"prefer_not_to_say", "participant_age":0, "participant_education":"other"})
        self.assertEqual(len(app.selectbox), 0)
        profile = [e for e in app.session_state["feed_events"] if e["event_type"] == "demographics_submitted"]
        self.assertEqual(len(profile), 1)
        self.assertIn("consent_accepted_at", profile[0]["details"])
        app.run()
        self.assertEqual(len([e for e in app.session_state["feed_events"] if e["event_type"] == "demographics_submitted"]), 1)

    def test_catalog_reserves_distinct_new_faces(self):
        selection = select_sets(self.catalog)
        self.assertEqual(len(selection["feed"]), 30)
        self.assertEqual(len(selection["new"]), 30)
        self.assertFalse(set(selection["feed"]) & set(selection["new"]))

    def test_new_memory_images_are_prepared_only_after_the_feed(self):
        with patch("image_assets.prepare_image", wraps=prepare_image) as image_loader:
            app = AppTest.from_file(str(APP)).run()
            app.checkbox[0].check().run()
            app.button[0].click().run()
            self.complete_details(app, start_feed=False)
            image_loader.assert_not_called()
            next(b for b in app.button if b.key == "start_feed_button").click().run()
            self.assertFalse(app.exception)
            selection = app.session_state["stimulus_selection"]
            by_id = {record["id"]: record for record in self.catalog.records}
            paths = lambda ids: {self.catalog.base / by_id[i]["image"] for i in ids}
            self.assertEqual({call.args[0] for call in image_loader.call_args_list}, paths(selection["feed"]))
            self.prefetch_loader.assert_called_with([self.catalog.base / by_id[i]["image"] for i in selection["new"]])
            plan = list(app.session_state["recognition_plan"])
            order = list(app.session_state["feed_post_order"])
            image_loader.reset_mock()
            app.session_state["experiment_phase"] = "recognition_intro"
            app.run()
            self.assertFalse(app.exception)
            self.assertEqual(app.title[0].value, "Hai già visto questo volto?")
            self.assertEqual({call.args[0] for call in image_loader.call_args_list}, paths(selection["feed"] + selection["new"]))
            self.assertEqual(app.session_state["recognition_plan"], plan)
            self.assertEqual(app.session_state["feed_post_order"], order)

    def test_memory_preparation_failure_keeps_instructions_and_can_be_retried(self):
        app = AppTest.from_file(str(APP)).run()
        app.checkbox[0].check().run()
        app.button[0].click().run()
        self.complete_details(app)
        plan = list(app.session_state["recognition_plan"])
        from image_assets import prepare_images

        def fail_memory(paths):
            if len(paths) == 60:
                raise OSError("Temporary image preparation failure")
            return prepare_images(paths)

        app.session_state["experiment_phase"] = "recognition_intro"
        with patch("image_assets.prepare_images", side_effect=fail_memory):
            app.run()
        self.assertFalse(app.exception)
        self.assertEqual(app.title[0].value, "Hai già visto questo volto?")
        self.assertEqual(len(app.error), 1)
        self.assertFalse(any(b.label == "Inizia il riconoscimento" for b in app.button))
        next(b for b in app.button if b.label == "Riprova aggiornamento").click().run()
        self.assertFalse(app.exception)
        self.assertEqual(len(app.error), 0)
        self.assertTrue(any(b.label == "Inizia il riconoscimento" for b in app.button))
        self.assertEqual(app.session_state["recognition_plan"], plan)

    def test_cached_image_module_without_batch_helper_can_run_both_phases(self):
        legacy = ModuleType("image_assets")
        legacy.__file__ = str(APP.with_name("image_assets.py"))
        legacy.prepare_image = prepare_image
        # A running Streamlit process may retain the previously imported module
        # while rerunning the updated app.py. It has only the original API.
        with patch.dict("sys.modules", {"image_assets": legacy}):
            app = AppTest.from_file(str(APP)).run()
            self.assertFalse(app.exception)
            app.checkbox[0].check().run()
            app.button[0].click().run()
            self.complete_details(app)
            self.assertFalse(app.exception)
            self.assertEqual(len(app.session_state["feed_post_order"]), 30)
            plan = list(app.session_state["recognition_plan"])
            self.assertEqual(len(plan), 60)
            app.run()
            self.assertFalse(app.exception)
            app.session_state["experiment_phase"] = "recognition_intro"
            app.run()
            self.assertFalse(app.exception)
            self.assertEqual(app.title[0].value, "Hai già visto questo volto?")
            app.button[0].click().run()
            self.assertFalse(app.exception)
            self.assertEqual(app.session_state["experiment_phase"], "recognition")
            self.assertEqual(app.session_state["recognition_plan"], plan)

    def test_previous_protocol_session_stops_before_adding_new_events(self):
        app = AppTest.from_file(str(APP)).run()
        app.checkbox[0].check().run()
        app.button[0].click().run()
        self.complete_details(app)
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
        self.complete_details(app)
        self.assertFalse(app.exception)
        self.assertEqual(len(app.error), 1)
        self.assertEqual(app.session_state["feed_events"], [])
        self.assertEqual(app.session_state["seen_event_ids"], set())
        self.assertFalse(app.session_state.get("demographics_completed", False))
        self.storage.side_effect = None
        app.button[0].click().run()
        self.assertFalse(app.exception)
        self.assertEqual(len(app.error), 0)
        self.assertEqual(app.session_state["feed_events"][0]["event_type"], "demographics_submitted")
        self.assertEqual(app.title[0].value, "Prima di aprire il feed")
        self.assertFalse(any(e["event_type"] == "session_started" for e in app.session_state["feed_events"]))
        next(b for b in app.button if b.key == "start_feed_button").click().run()
        self.assertEqual(len([e for e in app.session_state["feed_events"] if e["event_type"] == "session_started"]), 1)

    def test_failed_feed_start_does_not_resubmit_saved_demographics(self):
        def fail_start(session, events):
            if any(e["event_type"] == "session_started" for e in events):
                raise sqlite3.OperationalError("database is locked")
        self.storage.side_effect = fail_start
        app = AppTest.from_file(str(APP)).run()
        app.checkbox[0].check().run()
        app.button[0].click().run()
        self.complete_details(app)
        self.assertEqual(len(app.error), 1)
        self.assertTrue(app.session_state["demographics_completed"])
        self.assertEqual([e["event_type"] for e in app.session_state["feed_events"]], ["demographics_submitted"])
        self.storage.side_effect = None
        app.run()
        self.assertFalse(app.exception)
        self.assertEqual(len([e for e in app.session_state["feed_events"] if e["event_type"] == "demographics_submitted"]), 1)

    def test_memory_instructions_appear_only_after_first_phase(self):
        app = AppTest.from_file(str(APP)).run()
        app.checkbox[0].check().run()
        app.button[0].click().run()
        self.complete_details(app)
        self.assertFalse(app.exception)
        self.assertFalse(any("Hai già visto" in title.value for title in app.title))
        plan = list(app.session_state["recognition_plan"])
        participant = app.session_state["participant_id"]
        session = app.session_state["recording_session_id"]
        app.session_state["experiment_phase"] = "recognition_intro"
        app.run()
        self.assertEqual(app.title[0].value, "Hai già visto questo volto?")
        self.assertTrue(any("OLD — Già visto" in text.value for text in app.markdown))
        app.button[0].click().run()
        self.assertFalse(app.exception)
        self.assertEqual(app.session_state["experiment_phase"], "recognition")
        self.assertEqual(app.session_state["recognition_plan"], plan)
        self.assertEqual(app.session_state["participant_id"], participant)
        self.assertEqual(app.session_state["recording_session_id"], session)
        self.assertEqual({e["participant_id"] for e in app.session_state["feed_events"]}, {participant})
        self.assertTrue(all(e["participant_age"] == 24 and e["participant_gender"] == "woman" for e in app.session_state["feed_events"]))
        self.assertTrue(any(e["event_type"] == "recognition_started" for e in app.session_state["feed_events"]))


if __name__ == "__main__":
    unittest.main()
