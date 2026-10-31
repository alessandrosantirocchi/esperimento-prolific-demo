import subprocess
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from event_store import read_events, save_events, delete_sessions, is_session_deleted, SessionDeletedError


def event(identifier="e1", kind="like"):
    return {"event_id": identifier, "participant_id": "TEST001", "event_type": kind,
            "post_id": "P001", "stimulus_id": "TEMP001", "stimulus_type": "real",
            "server_received_ts": "2026-10-30T12:00:00+00:00", "details": {}}


class EventStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "events.sqlite3"

    def test_reactions_survive_new_process_and_repeated_delivery(self):
        rows = [event("e1"), event("e2", "unlike"), event("e3", "dislike")]
        save_events("session-a", rows, self.path)
        save_events("session-a", rows, self.path)
        output = subprocess.check_output([
            sys.executable, "-c",
            "from event_store import read_events; from pathlib import Path; "
            "import sys; print([e['event_type'] for e in read_events(Path(sys.argv[1]))])",
            str(self.path),
        ], text=True)
        self.assertIn("['like', 'unlike', 'dislike']", output)
        self.assertEqual(len(read_events(self.path)), 3)

    def test_sessions_do_not_overwrite_one_another(self):
        with ThreadPoolExecutor(max_workers=4) as pool:
            list(pool.map(lambda n: save_events(f"session-{n}", [event()], self.path), range(4)))
        self.assertEqual(len(read_events(self.path)), 4)

    def test_read_only_export_does_not_create_or_modify_database(self):
        self.assertEqual(read_events(self.path), [])
        self.assertFalse(self.path.exists())
        save_events("session-a", [event()], self.path)
        before = self.path.read_bytes()
        self.assertEqual(len(read_events(self.path)), 1)
        self.assertEqual(self.path.read_bytes(), before)

    def test_failed_batch_can_be_retried_without_partial_commit(self):
        bad = event("e2")
        bad["details"] = object()
        with self.assertRaises(TypeError):
            save_events("session", [event(), bad], self.path)
        save_events("session", [event(), event("e2", "dislike")], self.path)
        self.assertEqual(len(read_events(self.path)), 2)

    def test_delete_only_selected_sessions_and_block_delayed_writes(self):
        save_events("delete-me", [event("e1"), event("e2", "dislike")], self.path)
        save_events("keep-me", [event("e1")], self.path)
        result = delete_sessions(["delete-me"], self.path)
        self.assertEqual(result, {"sessions": 1, "events": 2})
        self.assertEqual({r["session_id"] for r in read_events(self.path)}, {"keep-me"})
        self.assertTrue(is_session_deleted("delete-me", self.path))
        self.assertFalse(is_session_deleted("keep-me", self.path))
        with self.assertRaises(SessionDeletedError):
            save_events("delete-me", [event("late-event")], self.path)
        self.assertEqual(len(read_events(self.path)), 1)

    def test_empty_selection_never_deletes_everything(self):
        save_events("keep", [event()], self.path)
        for selection in ([], [""], "keep"):
            with self.assertRaises(ValueError):
                delete_sessions(selection, self.path)
        self.assertEqual(len(read_events(self.path)), 1)
        delete_sessions(["not-found' OR 1=1 --"], self.path)
        self.assertEqual(len(read_events(self.path)), 1)

    def test_concurrent_delete_cannot_be_undone_by_late_writers(self):
        save_events("delete-me", [event()], self.path)
        save_events("keep-me", [event()], self.path)
        def write(number):
            try:
                save_events("delete-me", [event(f"late-{number}")], self.path)
            except SessionDeletedError:
                pass
        with ThreadPoolExecutor(max_workers=5) as pool:
            writers = [pool.submit(write, n) for n in range(4)]
            deletion = pool.submit(delete_sessions, ["delete-me"], self.path)
            for writer in writers:
                writer.result()
            deletion.result()
        self.assertEqual({r["session_id"] for r in read_events(self.path)}, {"keep-me"})
