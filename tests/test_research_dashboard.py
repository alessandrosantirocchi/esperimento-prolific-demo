import os
from pathlib import Path
import unittest
from unittest.mock import patch

from streamlit.testing.v1 import AppTest
from research_dashboard import configured_password

APP = Path(__file__).resolve().parents[1] / "app.py"
RECORDS = [{"session_id": "s1", "event_id": "e1", "participant_id": "SUBJECT_A",
            "event_type": "recognition_response", "phase": "recognition", "post_id": "P001",
            "stimulus_id": "TEMP001", "details": {"response": "OLD", "target": "OLD", "correct": True, "response_time_ms": 320}}]


class PasswordConfigurationTests(unittest.TestCase):
    def test_documentation_placeholder_does_not_enable_access(self):
        with patch.dict(os.environ, {"INSTALAB_RESEARCHER_PASSWORD": "SOSTITUISCI_CON_UNA_PASSWORD_PRIVATA"}):
            self.assertIsNone(configured_password())


class ResearchDashboardTests(unittest.TestCase):
    def setUp(self):
        password = patch("research_dashboard.configured_password", return_value="test-only-access")
        self.password = password.start()
        self.addCleanup(password.stop)
        reader = patch("research_dashboard.read_events", return_value=RECORDS)
        self.reader = reader.start()
        self.addCleanup(reader.stop)
        deletion = patch("research_dashboard.delete_sessions", return_value={"sessions": 1, "events": 1})
        self.deletion = deletion.start()
        self.addCleanup(deletion.stop)

    def app(self):
        app = AppTest.from_file(str(APP))
        app.query_params["researcher"] = "1"
        return app.run()

    def login(self, app):
        app.text_input[0].set_value("test-only-access")
        app.button[0].click().run()

    def test_missing_configuration_fails_closed(self):
        self.password.return_value = None
        app = self.app()
        self.assertFalse(app.exception)
        self.assertEqual(len(app.text_input), 0)
        self.reader.assert_not_called()
        self.assertNotIn("intro_consent_accepted", app.session_state)

    def test_wrong_password_does_not_read_database(self):
        app = self.app()
        app.text_input[0].set_value("wrong")
        app.button[0].click().run()
        self.assertFalse(app.exception)
        self.assertEqual(len(app.error), 1)
        self.assertEqual(app.text_input[0].value, "")
        self.reader.assert_not_called()
        self.deletion.assert_not_called()

    def test_deletion_requires_selection_and_explicit_confirmation(self):
        app = self.app()
        self.login(app)
        button = next(b for b in app.button if b.label == "Elimina le sessioni selezionate")
        self.assertTrue(button.disabled)
        selector = next(m for m in app.multiselect if m.key == "research_delete_sessions")
        selector.set_value(["s1"]).run()
        next(b for b in app.button if b.label == "Elimina le sessioni selezionate").click().run()
        self.assertFalse(app.exception)
        self.deletion.assert_not_called()
        next(b for b in app.button if b.label == "Elimina definitivamente").click().run()
        self.assertFalse(app.exception)
        self.deletion.assert_not_called()
        next(t for t in app.text_input if t.key == "research_delete_confirmation").set_value("ELIMINA")
        next(b for b in app.button if b.label == "Elimina definitivamente").click().run()
        self.assertFalse(app.exception)
        self.deletion.assert_called_once_with(["s1"])

    def test_password_rotation_cancels_pending_deletion(self):
        app = self.app()
        self.login(app)
        next(m for m in app.multiselect if m.key == "research_delete_sessions").set_value(["s1"]).run()
        next(b for b in app.button if b.label == "Elimina le sessioni selezionate").click().run()
        self.password.return_value = "rotated-test-access"
        app.run()
        self.assertFalse(app.exception)
        self.assertNotIn("research_pending_delete", app.session_state)
        self.deletion.assert_not_called()

    def test_authenticated_downloads_logout_and_rotation(self):
        app = self.app()
        self.login(app)
        self.assertFalse(app.exception)
        self.reader.assert_called()
        self.assertEqual(app.metric[1].value, "1")
        self.assertNotIn("research_password", app.session_state)
        self.password.return_value = "rotated-test-access"
        self.reader.reset_mock()
        app.run()
        self.assertFalse(app.exception)
        self.assertEqual(len(app.text_input), 1)
        self.reader.assert_not_called()

        self.password.return_value = "test-only-access"
        self.login(app)
        self.reader.reset_mock()
        app.button[1].click().run()
        self.assertFalse(app.exception)
        self.assertEqual(len(app.text_input), 1)
        self.reader.assert_not_called()

    def test_feed_metrics_download_keeps_assignment_when_filtering_memory(self):
        self.reader.return_value = [
            {"session_id":"s1", "event_id":"start", "participant_id":"SUBJECT_A", "event_type":"session_started",
             "details":{"post_order":["P001"], "stimuli":[{"id":"P001","stimulus_id":"TEMP001","source_type":"gan","gender":"F"}]}},
            {"session_id":"s1", "event_id":"tracking", "participant_id":"SUBJECT_A", "event_type":"feed_tracking_started", "details":{"tracking_version":1}},
            {"session_id":"s1", "event_id":"final", "participant_id":"SUBJECT_A", "event_type":"feed_tracking_finalized", "details":{"tracking_version":1}},
            *RECORDS,
        ]
        app = self.app()
        self.login(app)
        next(s for s in app.selectbox if s.key == "research_phase").set_value("recognition").run()
        self.assertFalse(app.exception)
        download = next(e.proto for e in app.get("download_button") if e.proto.label == "Metriche del feed (CSV)")
        self.assertFalse(download.disabled)

    def test_repeated_failed_logins_are_throttled_without_reading_records(self):
        with patch("research_dashboard.time.monotonic", return_value=100):
            app = self.app()
            for _ in range(5):
                app.text_input[0].set_value("wrong")
                app.button[0].click().run()
            self.assertFalse(app.exception)
            self.assertTrue(app.button[0].disabled)
            self.reader.assert_not_called()
        with patch("research_dashboard.time.monotonic", return_value=161):
            app.run()
            self.login(app)
            self.assertFalse(app.exception)
            self.reader.assert_called()
