"""Validate the researcher manifest and reserve separate study/new face sets."""

from collections import Counter
import csv
from dataclasses import dataclass
from functools import lru_cache
import hashlib
import json
from pathlib import Path, PurePosixPath, PureWindowsPath
import random

from PIL import Image, ImageOps

from experiment_protocol import (CATEGORIES, GENDERS, FACES_PER_CELL, FEED_SIZE,
                                 NEW_SIZE, PROTOCOL_VERSION)

METADATA_FIELDS = ("stimulus_id", "filename", "source_type", "gender", "stimulus_type")
DISPLAY_FIELDS = ("id", "image_url", "image_position", "avatar_url", "username", "caption",
                  "location", "initial_likes", "minutes_ago", "verified", "comments")


class CatalogError(ValueError):
    def __init__(self, errors, report=None):
        self.errors = errors
        self.report = report or {}
        super().__init__("\n".join(errors))


@dataclass
class Catalog:
    base: Path
    records: list[dict]
    fingerprint: str
    report: dict


@lru_cache(maxsize=512)
def _inspect(filename, mtime_ns, byte_size):
    path = Path(filename)
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    with Image.open(path) as image:
        image.verify()
    with Image.open(path) as source:
        image = ImageOps.exif_transpose(source).convert("RGBA")
        pixels = hashlib.sha256(f"{image.width}x{image.height}:".encode() + image.tobytes()).hexdigest()
    return digest.hexdigest(), pixels


def _relative_image(base, filename):
    name = filename.replace("\\", "/")
    relative = PurePosixPath(name)
    if relative.is_absolute() or PureWindowsPath(name).drive or ".." in relative.parts:
        raise ValueError("il percorso deve essere relativo a images/")
    if relative.parts and relative.parts[0] == "images":
        relative = PurePosixPath(*relative.parts[1:])
    candidate = (base / "images" / relative).resolve()
    root = (base / "images").resolve()
    if not root.is_relative_to(base) or not candidate.is_relative_to(root):
        raise ValueError("il percorso esce dalla cartella images/")
    if candidate.suffix.lower() not in {".jpg", ".jpeg", ".png", ".webp"}:
        raise ValueError("formato non supportato (JPG, PNG, WEBP)")
    if not candidate.is_file():
        raise ValueError("file mancante; controllare anche maiuscole/minuscole")
    return candidate, candidate.relative_to(base).as_posix()


def _pool_shortages(records):
    counts = Counter((r["source_type"], r["gender"]) for r in records)
    required = 2 * FACES_PER_CELL
    return [f"Stimoli insufficienti per {category}/{gender}: {counts[(category, gender)]} "
            f"disponibili, almeno {required} richiesti "
            f"({FACES_PER_CELL} nel feed e {FACES_PER_CELL} NEW distinti)."
            for category in CATEGORIES for gender in GENDERS
            if counts[(category, gender)] < required]


def load_catalog(base: Path) -> Catalog:
    base = base.resolve()
    manifest = base / "stimuli.csv"
    if not manifest.is_file():
        raise CatalogError(["stimuli.csv non trovato accanto ad app.py"])
    errors, records = [], []
    seen_ids, seen_paths, seen_bytes, seen_pixels = {}, {}, {}, {}
    report = {"manifest_rows": 0, "counts": {}, "unlisted_files": [], "warnings": []}
    try:
        with manifest.open(encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            required = {"stimulus_id", "filename", "source_type", "gender"}
            if not required <= set(reader.fieldnames or []):
                raise CatalogError(["Colonne richieste: stimulus_id,filename,source_type,gender (CSV UTF-8, separatore virgola)"])
            for line, row in enumerate(reader, 2):
                if not any(value for value in row.values()):
                    continue
                report["manifest_rows"] += 1
                values = {key: (row.get(key) or "").strip() for key in required}
                row_errors = []
                if not all(values.values()) or None in row:
                    row_errors.append("campi obbligatori vuoti o numero di colonne non valido")
                source_type = values["source_type"].lower()
                gender = values["gender"].upper()
                if source_type not in CATEGORIES:
                    row_errors.append("source_type deve essere real, gan o transformer")
                if gender not in {"F", "M"}:
                    row_errors.append("gender deve contenere l'etichetta F o M")
                identifier = values["stimulus_id"]
                if identifier in seen_ids:
                    row_errors.append(f"stimulus_id duplicato (riga {seen_ids[identifier]})")
                seen_ids[identifier] = line
                try:
                    path, relative = _relative_image(base, values["filename"])
                    if relative in seen_paths:
                        row_errors.append(f"file ripetuto (riga {seen_paths[relative]})")
                    seen_paths[relative] = line
                    stamp = path.stat()
                    content_hash, pixel_hash = _inspect(str(path), stamp.st_mtime_ns, stamp.st_size)
                    if content_hash in seen_bytes:
                        row_errors.append(f"contenuto del file duplicato (riga {seen_bytes[content_hash]})")
                    elif pixel_hash in seen_pixels:
                        row_errors.append(f"pixel dell'immagine duplicati (riga {seen_pixels[pixel_hash]})")
                    seen_bytes[content_hash], seen_pixels[pixel_hash] = line, line
                except (OSError, ValueError) as exc:
                    row_errors.append(str(exc))
                if row_errors:
                    errors.extend(f"Riga {line} ({values['filename']}): {message}" for message in row_errors)
                    continue
                records.append({"id": f"S{line-1:05}", **values, "source_type": source_type,
                                "gender": gender, "image": relative, "sha256": content_hash,
                                "stimulus_type": "real" if source_type == "real" else "deepfake"})
    except UnicodeDecodeError as exc:
        raise CatalogError(["stimuli.csv deve essere salvato in UTF-8"]) from exc
    counts = Counter((r["source_type"], r["gender"]) for r in records)
    report["counts"] = {f"{category}/{gender}": counts[(category, gender)] for category in sorted(CATEGORIES) for gender in ("F", "M")}
    report["valid_records"] = len(records)
    root = base / "images"
    if root.is_dir():
        for path in root.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in {".jpg", ".jpeg", ".png", ".webp"}:
                continue
            resolved = path.resolve()
            if not resolved.is_relative_to(base):
                errors.append(f"Percorso esterno al repository: {path.relative_to(base)}")
            elif resolved.relative_to(base).as_posix() not in seen_paths:
                report["unlisted_files"].append(path.relative_to(base).as_posix())
        report["unlisted_files"].sort()
    errors.extend(_pool_shortages(records))
    report["available_after_feed"] = max(0, len(records)-FEED_SIZE)
    report["required_new_faces"] = NEW_SIZE
    report["protocol_version"] = PROTOCOL_VERSION
    if report["unlisted_files"]:
        report["warnings"].append("Alcune immagini non sono elencate nel CSV e non saranno utilizzate.")
    if errors:
        raise CatalogError(errors, report)
    fingerprint = hashlib.sha256(json.dumps({"protocol_version": PROTOCOL_VERSION,
                                            "records": records}, sort_keys=True).encode()).hexdigest()
    return Catalog(base, records, fingerprint, report)


def select_sets(catalog: Catalog, rng=None):
    rng = rng or random.SystemRandom()
    shortages = _pool_shortages(catalog.records)
    if shortages:
        raise CatalogError(shortages, catalog.report)
    feed, new = [], []
    for category in CATEGORIES:
        for gender in GENDERS:
            pool = [r for r in catalog.records if r["source_type"] == category and r["gender"] == gender]
            chosen = rng.sample(pool, 2*FACES_PER_CELL)
            feed.extend(r["id"] for r in chosen[:FACES_PER_CELL])
            new.extend(r["id"] for r in chosen[FACES_PER_CELL:])
    rng.shuffle(feed)
    rng.shuffle(new)
    return {"fingerprint": catalog.fingerprint, "protocol_version": PROTOCOL_VERSION,
            "feed": feed, "new": new}


def display_post(record):
    return {key: record[key] for key in DISPLAY_FIELDS if key in record}


def public_history(events):
    detail_fields = {"method", "text", "length", "username", "page", "response",
                     "response_time_ms", "displayed_client_ts", "threshold", "visibility_basis", "visible_height_px"}
    rows = []
    for event in events:
        row = {key: event[key] for key in ("event_id", "event_type", "post_id", "client_ts", "elapsed_ms", "trial_id") if key in event}
        details = event.get("details", {})
        row["details"] = {key: value for key, value in details.items() if key in detail_fields} if isinstance(details, dict) else {}
        rows.append(row)
    return rows
