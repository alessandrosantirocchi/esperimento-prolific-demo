from collections import Counter
import csv
import io
import os
from pathlib import Path
import random
import tempfile
import unittest

from PIL import Image

from catalog_fixture import create_catalog
from export_data import csv_bytes, final_reactions
from experiment_protocol import PROTOCOL_VERSION
from recognition import make_plan
from stimulus_catalog import CatalogError, load_catalog, select_sets, display_post, public_history


class CatalogTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.base = create_catalog(folder.name)

    def rows(self):
        with (self.base / "stimuli.csv").open(newline="") as handle:
            return list(csv.DictReader(handle))

    def write_rows(self, rows):
        with (self.base / "stimuli.csv").open("w", newline="", encoding="utf-8-sig") as handle:
            writer = csv.DictWriter(handle, fieldnames=["stimulus_id", "filename", "source_type", "gender"])
            writer.writeheader()
            writer.writerows(rows)

    def test_relative_nested_paths_and_working_directory(self):
        rows = self.rows()
        nested = self.base / "images" / "sottocartella"
        nested.mkdir()
        (self.base / "images" / rows[0]["filename"]).rename(nested / "volto è.png")
        rows[0]["filename"] = "images/sottocartella/volto è.png"
        self.write_rows(rows)
        cwd = os.getcwd()
        try:
            os.chdir(self.base / "images")
            catalog = load_catalog(self.base)
        finally:
            os.chdir(cwd)
        self.assertEqual(catalog.records[0]["image"], "images/sottocartella/volto è.png")
        self.assertEqual(catalog.records[0]["filename"], rows[0]["filename"])

    def test_random_sets_keep_counts_gender_and_unseen_reserve(self):
        catalog = load_catalog(self.base)
        by_id = {r["id"]: r for r in catalog.records}
        feed_orders, memory_orders = set(), set()
        for seed in range(30):
            rng = random.Random(seed)
            selection = select_sets(catalog, rng)
            feed = [by_id[i] for i in selection["feed"]]
            new = [by_id[i] for i in selection["new"]]
            self.assertEqual(len(feed), 30)
            self.assertEqual(len(new), 30)
            self.assertEqual(selection["protocol_version"], PROTOCOL_VERSION)
            self.assertFalse(set(selection["feed"]) & set(selection["new"]))
            expected = {(category, gender): 5 for category in ("real", "gan", "transformer") for gender in ("F", "M")}
            for group in (feed, new):
                self.assertEqual(Counter((p["source_type"], p["gender"]) for p in group), expected)
            plan = make_plan(feed, new, rng)
            self.assertEqual(len(plan), 60)
            self.assertEqual({t["post_id"] for t in plan if t["target"] == "OLD"}, set(selection["feed"]))
            for target in ("OLD", "NEW"):
                self.assertEqual(Counter((by_id[t["post_id"]]["source_type"], by_id[t["post_id"]]["gender"])
                                         for t in plan if t["target"] == target), expected)
            feed_orders.add(tuple(selection["feed"]))
            memory_orders.add(tuple(t["post_id"] for t in plan))
        self.assertGreater(len(feed_orders), 1)
        self.assertGreater(len(memory_orders), 1)

    def test_exact_minimum_catalog_has_enough_separate_new_faces(self):
        rows = [r for r in self.rows() if int(r["stimulus_id"].rsplit("_", 1)[1]) < 10]
        self.write_rows(rows)
        catalog = load_catalog(self.base)
        selection = select_sets(catalog, random.Random(12))
        self.assertEqual(len(set(selection["feed"] + selection["new"])), 60)
        self.assertEqual(catalog.report["available_after_feed"], 30)
        self.assertEqual(catalog.report["required_new_faces"], 30)

    def test_missing_file_and_case_mismatch_are_reported(self):
        rows = self.rows()
        rows[0]["filename"] = rows[0]["filename"].upper()
        self.write_rows(rows)
        with self.assertRaises(CatalogError) as error:
            load_catalog(self.base)
        self.assertIn("file mancante", str(error.exception))

    def test_duplicate_ids_and_files_are_rejected(self):
        rows = self.rows()
        rows[1]["stimulus_id"] = rows[0]["stimulus_id"]
        rows[1]["filename"] = rows[0]["filename"]
        self.write_rows(rows)
        with self.assertRaises(CatalogError) as error:
            load_catalog(self.base)
        self.assertIn("stimulus_id duplicato", str(error.exception))
        self.assertIn("file ripetuto", str(error.exception))

    def test_equal_pixels_in_different_files_cannot_become_new_faces(self):
        rows = self.rows()
        with Image.open(self.base / "images" / rows[0]["filename"]) as image:
            image.save(self.base / "images" / rows[1]["filename"], compress_level=0)
        with self.assertRaises(CatalogError) as error:
            load_catalog(self.base)
        self.assertIn("duplicat", str(error.exception))

    def test_paths_cannot_escape_images(self):
        rows = self.rows()
        rows[0]["filename"] = "../outside.png"
        self.write_rows(rows)
        with self.assertRaises(CatalogError) as error:
            load_catalog(self.base)
        self.assertIn("percorso deve essere relativo", str(error.exception))

    def test_insufficient_reserve_is_an_error_not_face_reuse(self):
        rows = self.rows()
        gan_f = [r for r in rows if (r["source_type"], r["gender"]) == ("gan", "F")]
        rows = [r for r in rows if r not in gan_f] + gan_f[:9]
        self.write_rows(rows)
        with self.assertRaises(CatalogError) as error:
            load_catalog(self.base)
        self.assertIn("Stimoli insufficienti", str(error.exception))
        self.assertIn("gan/F: 9 disponibili, almeno 10 richiesti", str(error.exception))

    def test_metadata_is_required_and_not_inferred_from_names(self):
        rows = self.rows()
        rows[0]["gender"] = ""
        rows[1]["source_type"] = "fake"
        self.write_rows(rows)
        with self.assertRaises(CatalogError) as error:
            load_catalog(self.base)
        self.assertIn("gender", str(error.exception))
        self.assertIn("source_type", str(error.exception))

    def test_metadata_is_exported_but_not_sent_to_participants(self):
        record = load_catalog(self.base).records[0]
        private = {**record, "event_id":"e", "event_type":"like", "session_id":"s", "participant_id":"p",
                   "post_id":record["id"], "details":{"filename":record["filename"],"gender":record["gender"],"target":"OLD","correct":True}}
        row = next(csv.DictReader(io.StringIO(csv_bytes([private]).decode("utf-8-sig"))))
        for field in ("stimulus_id", "filename", "source_type", "gender"):
            self.assertEqual(row[field], record[field])
            self.assertNotIn(field, display_post(record))
            self.assertNotIn(field, public_history([private])[0])
            self.assertNotIn(field, public_history([private])[0]["details"])
            self.assertEqual(final_reactions([private])[0][field], record[field])
        self.assertNotIn("target", public_history([private])[0]["details"])
        self.assertNotIn("correct", public_history([private])[0]["details"])
