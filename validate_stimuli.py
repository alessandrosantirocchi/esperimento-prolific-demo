"""Run from any directory: python /path/to/repository/validate_stimuli.py."""

import argparse
import json
from pathlib import Path

from stimulus_catalog import CatalogError, load_catalog
from experiment_protocol import FEED_SIZE, NEW_SIZE, MEMORY_SIZE


def main():
    parser = argparse.ArgumentParser(description="Verifica immagini e manifest di InstaLab")
    parser.add_argument("--json", action="store_true", help="Mostra il risultato in JSON")
    args = parser.parse_args()
    try:
        catalog = load_catalog(Path(__file__).resolve().parent)
        report, errors = catalog.report, []
    except CatalogError as exc:
        report, errors = exc.report, exc.errors
    if args.json:
        print(json.dumps({**report, "errors": errors}, ensure_ascii=False, indent=2))
    else:
        print("Verifica stimoli: " + ("NON SUPERATA" if errors else "SUPERATA"))
        print(f"Protocollo: {FEED_SIZE} volti nel feed; {MEMORY_SIZE} prove di memoria ({FEED_SIZE} OLD + {NEW_SIZE} NEW)")
        print(f"Righe CSV: {report.get('manifest_rows', 0)}; stimoli validi: {report.get('valid_records', 0)}")
        for label, count in report.get("counts", {}).items():
            print(f"  {label}: {count}")
        print(f"Volti non presentati dopo il feed: {report.get('available_after_feed', 0)}; NEW richiesti: {report.get('required_new_faces', NEW_SIZE)}")
        for message in errors + report.get("warnings", []):
            print(message)
        for filename in report.get("unlisted_files", []):
            print(f"Non elencato: {filename}")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
