import base64
from io import BytesIO
from pathlib import Path
import tempfile
import unittest

from PIL import Image

from image_assets import prepare_image, prepare_images, prefetch_images
from stimulus_catalog import load_catalog, select_sets
import random

BASE = Path(__file__).resolve().parents[1]


class ImageAssetTests(unittest.TestCase):
    def test_all_display_stimuli_decode_and_are_smaller(self):
        catalog = load_catalog(BASE)
        selection = select_sets(catalog, random.Random(42))
        posts = [p for p in catalog.records if p["id"] in selection["feed"] + selection["new"]]
        sources = {p["image"] for p in posts}
        originals = {name: (BASE / name).read_bytes() for name in sources}
        assets = []
        for post in posts:
            asset = prepare_image(BASE / post["image"], post.get("image_region"))
            with Image.open(BytesIO(base64.b64decode(asset.url.split(",", 1)[1]))) as image:
                image.load()
                self.assertEqual(image.format, "WEBP")
                self.assertLessEqual(max(image.size), 960)
                if "image_region" in post:
                    self.assertEqual(image.size, (440, 440))
            assets.append(asset)
        self.assertLess(sum(a.byte_count for a in assets), sum(map(len, originals.values())) / 2)
        for name, content in originals.items():
            self.assertEqual((BASE / name).read_bytes(), content)

    def test_crop_cache_and_file_refresh(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "source.png"
            image = Image.new("RGB", (128, 64), "red")
            image.paste("lime", (64, 0, 128, 64))
            image.save(path)
            region = {"x": 64, "y": 0, "width": 64, "height": 64, "source_width": 128}
            first = prepare_image(path, region)
            self.assertIs(first, prepare_image(path, region))
            with Image.open(BytesIO(base64.b64decode(first.url.split(",", 1)[1]))) as cropped:
                red, green, blue = cropped.getpixel((32, 32))
                self.assertGreater(green, 245)
                self.assertLess(max(red, blue), 10)
            Image.new("RGB", (128, 64), "blue").save(path)
            self.assertNotEqual(first.url, prepare_image(path, region).url)
            with self.assertRaises(ValueError):
                prepare_image(path, {**region, "x": 100})

    def test_missing_image_reports_error(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(FileNotFoundError):
                prepare_image(Path(folder) / "missing.jpg")

    def test_batch_preserves_order_and_the_existing_image_encoding(self):
        with tempfile.TemporaryDirectory() as folder:
            paths = [Path(folder) / f"{i}.png" for i in range(3)]
            for path, color in zip(paths, ["red", "green", "blue"]):
                Image.new("RGB", (64, 64), color).save(path)
            batch = prepare_images(paths)
            self.assertEqual(batch, [prepare_image(path) for path in paths])
            self.assertEqual(prepare_images([]), [])
            with self.assertRaises(FileNotFoundError):
                prepare_images([paths[0], Path(folder) / "missing.png"])

    def test_prefetch_is_shared_and_refreshes_after_a_file_change(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "face.png"
            Image.new("RGB", (64, 64), "red").save(path)
            first = prefetch_images([path])
            self.assertIs(first, prefetch_images([path]))
            self.assertIsNone(first.result(timeout=10))
            red = prepare_image(path)
            Image.new("RGB", (64, 64), "blue").save(path)
            second = prefetch_images([path])
            self.assertIsNot(first, second)
            second.result(timeout=10)
            self.assertNotEqual(red.url, prepare_image(path).url)
