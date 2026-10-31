"""Cached display derivatives. Original stimulus files are never overwritten."""

import base64
from dataclasses import dataclass
from functools import lru_cache
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageOps


@dataclass(frozen=True)
class DisplayImage:
    url: str
    width: int
    height: int
    byte_count: int


def prepare_image(path: Path, region: dict | None = None) -> DisplayImage:
    path = path.resolve()
    stamp = path.stat()
    crop = None
    if region is not None:
        crop = tuple(region[key] for key in ("x", "y", "width", "height", "source_width"))
    return _prepare(str(path), stamp.st_mtime_ns, stamp.st_size, crop)


@lru_cache(maxsize=128)
def _prepare(filename: str, mtime_ns: int, size: int, crop: tuple | None) -> DisplayImage:
    with Image.open(filename) as source:
        image = ImageOps.exif_transpose(source)
        profile = image.info.get("icc_profile")
        if crop is not None:
            x, y, width, height, source_width = crop
            if (any(type(v) is not int for v in crop) or source_width != image.width
                    or x < 0 or y < 0 or width <= 0 or height <= 0
                    or x + width > image.width or y + height > image.height):
                raise ValueError(f"Invalid stimulus region: {Path(filename).name}")
            image = image.crop((x, y, x + width, y + height))
        if "A" in image.getbands() or "transparency" in image.info:
            rgba = image.convert("RGBA")
            background = Image.new("RGBA", rgba.size, "#f1f1f1")
            image = Image.alpha_composite(background, rgba).convert("RGB")
        else:
            image = image.convert("RGB")
        image.thumbnail((960, 960), Image.Resampling.LANCZOS)
        buffer = BytesIO()
        options = {"icc_profile": profile} if profile else {}
        image.save(buffer, "WEBP", quality=92, method=4, **options)
        content = buffer.getvalue()
        return DisplayImage("data:image/webp;base64," + base64.b64encode(content).decode("ascii"),
                            image.width, image.height, len(content))
