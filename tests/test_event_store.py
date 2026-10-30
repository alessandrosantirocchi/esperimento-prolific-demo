import subprocess
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from event_store import read_events, save_events


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

    def test_failed_batch_can_be_retried_without_partial_commit(self):
        bad = event("e2")
        bad["details"] = object()
        with self.assertRaises(TypeError):
            save_events("session", [event(), bad], self.path)
        save_events("session", [event(), event("e2", "dislike")], self.path)
        self.assertEqual(len(read_events(self.path)), 2)
