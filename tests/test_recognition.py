from collections import Counter
import random
import tempfile
import unittest

from recognition import make_plan, score_response
from stimulus_catalog import load_catalog, select_sets
from catalog_fixture import create_catalog


class RecognitionTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.catalog = load_catalog(create_catalog(folder.name))
        selection = select_sets(self.catalog, random.Random(42))
        by_id = {r["id"]: r for r in self.catalog.records}
        self.study = {"posts": [by_id[i] for i in selection["feed"]],
                      "recognition_new_posts": [by_id[i] for i in selection["new"]]}

    def test_balanced_old_and_new_with_no_first_phase_lures(self):
        study = self.study
        plan = make_plan(study["posts"], study["recognition_new_posts"], random.Random(42))
        by_id = {p["id"]: p for p in study["posts"] + study["recognition_new_posts"]}
        old_ids = {p["id"] for p in study["posts"]}
        self.assertEqual(len(plan), 60)
        self.assertEqual(len({p["trial_id"] for p in plan}), 60)
        self.assertEqual({p["post_id"] for p in plan if p["target"] == "OLD"}, old_ids)
        self.assertEqual([p["trial_id"] for p in plan], [f"R{i:03}" for i in range(1, 61)])
        for target in ("OLD", "NEW"):
            trials = [t for t in plan if t["target"] == target]
            self.assertEqual(len(trials), 30)
            self.assertEqual(Counter((by_id[t["post_id"]]["source_type"], by_id[t["post_id"]]["gender"]) for t in trials),
                             {(category, gender): 5 for category in ("real", "gan", "transformer") for gender in ("F", "M")})
            self.assertTrue(all((t["post_id"] in old_ids) == (target == "OLD") for t in trials))
        def image_identity(post):
            return (post["image"], tuple(sorted(post.get("image_region", {}).items())))
        self.assertFalse({image_identity(p) for p in study["posts"]} &
                         {image_identity(p) for p in study["recognition_new_posts"]})
        for post in study["recognition_new_posts"]:
            self.assertTrue((self.catalog.base / post["image"]).is_file())

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
            make_plan(self.study["posts"], self.study["posts"])

    def test_wrong_category_or_gender_quotas_are_rejected(self):
        for field, value in (("source_type", "other"), ("gender", "other")):
            with self.subTest(field=field):
                new = [dict(p) for p in self.study["recognition_new_posts"]]
                new[0][field] = value
                with self.assertRaises(ValueError):
                    make_plan(self.study["posts"], new)
