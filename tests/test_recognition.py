import json
from pathlib import Path
import random
import unittest

from recognition import make_plan, score_response

STUDY = json.loads((Path(__file__).resolve().parents[1] / "posts.json").read_text())


class RecognitionTests(unittest.TestCase):
    def test_balanced_old_and_new_with_no_first_phase_lures(self):
        plan = make_plan(STUDY["posts"], STUDY["recognition_new_posts"], random.Random(42))
        by_id = {p["id"]: p for p in STUDY["posts"] + STUDY["recognition_new_posts"]}
        old_ids = {p["id"] for p in STUDY["posts"]}
        self.assertEqual(len(plan), 20)
        self.assertEqual(len({p["trial_id"] for p in plan}), 20)
        for target in ("OLD", "NEW"):
            trials = [t for t in plan if t["target"] == target]
            self.assertEqual(len(trials), 10)
            for kind in ("real", "deepfake"):
                self.assertEqual(sum(by_id[t["post_id"]]["stimulus_type"] == kind for t in trials), 5)
            self.assertTrue(all((t["post_id"] in old_ids) == (target == "OLD") for t in trials))
        def image_identity(post):
            return (post["image"], tuple(sorted(post.get("image_region", {}).items())))
        self.assertFalse({image_identity(p) for p in STUDY["posts"]} &
                         {image_identity(p) for p in STUDY["recognition_new_posts"]})
        for post in STUDY["recognition_new_posts"]:
            self.assertTrue((Path(__file__).resolve().parents[1] / post["image"]).is_file())

    def test_scoring_and_invalid_responses(self):
        plan = [{"post_id": "old", "target": "OLD"}, {"post_id": "new", "target": "NEW"}]
        self.assertTrue(score_response(plan, "old", "OLD")["correct"])
        self.assertFalse(score_response(plan, "old", "NEW")["correct"])
        self.assertTrue(score_response(plan, "new", "NEW")["correct"])
        for post_id, choice in [("absent", "OLD"), ("old", "LIKE"), ("old", [])]:
            with self.assertRaises(ValueError):
                score_response(plan, post_id, choice)

    def test_lures_cannot_overlap_study_stimuli(self):
        with self.assertRaises(ValueError):
            make_plan(STUDY["posts"], STUDY["posts"])
