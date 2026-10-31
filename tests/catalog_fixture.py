"""Small generated image fixtures; no participant images or research records."""

import csv
from pathlib import Path

from PIL import Image


def create_catalog(base, per_cell=12):
    base = Path(base)
    (base / "images").mkdir()
    rows = []
    for category in ("real", "gan", "transformer"):
        for gender in ("F", "M"):
            for number in range(per_cell):
                identifier = f"{category}_{gender}_{number:03}"
                filename = identifier + ".png"
                Image.new("RGB", (32, 32), (len(rows)*3 % 256, number*17, 51)).save(base / "images" / filename)
                rows.append({"stimulus_id": identifier, "filename": filename,
                             "source_type": category, "gender": gender})
    with (base / "stimuli.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["stimulus_id", "filename", "source_type", "gender"])
        writer.writeheader()
        writer.writerows(rows)
    return base
