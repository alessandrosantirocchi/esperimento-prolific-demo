import base64
from io import BytesIO
import json
from pathlib import Path
import tempfile
import unittest

from PIL import Image

from image_assets import prepare_image

BASE = Path(__file__).resolve().parents[1]


class ImageAssetTests(unittest.TestCase):
    def test_all_display_stimuli_decode_and_are_smaller(self):
        study = json.loads((BASE / "posts.json").read_text())
        posts = study["posts"] + study["recognition_new_posts"]
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
