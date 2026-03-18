#!/usr/bin/env python3
"""
Scan a directory for PNG files, extract `invokeai_metadata` from each,
and attempt to parse it with InvokeGenerationMetadataAdapter.

Reports successes, missing metadata, and parse errors with details.

Usage:
    python scripts/test_png_metadata.py /path/to/png/directory [--recursive]
    python scripts/test_png_metadata.py /path/to/pngs --save-failures
"""

import argparse
import json
import sys
from pathlib import Path

from PIL import Image

from invoke_metadata.metadata import InvokeGenerationMetadataAdapter


def extract_invokeai_metadata(png_path: Path) -> str | None:
    """Return the raw metadata string from a PNG, or None if absent.

    Checks for ``invokeai_metadata`` first, then falls back to the
    older ``sd-metadata`` tag used by earlier InvokeAI versions.
    """
    with Image.open(png_path) as img:
        return img.info.get("invokeai_metadata") or img.info.get("sd-metadata")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Test parsing of invokeai_metadata in PNG files."
    )
    parser.add_argument("directory", type=Path, help="Directory containing PNG files")
    parser.add_argument(
        "--recursive", "-r", action="store_true", help="Search subdirectories"
    )
    parser.add_argument(
        "--save-failures",
        "-s",
        action="store_true",
        help="Write failed JSON metadata to tests/example_jsons/",
    )
    args = parser.parse_args()

    if not args.directory.is_dir():
        print(f"Error: {args.directory} is not a directory", file=sys.stderr)
        return 1

    glob_pattern = "**/*.png" if args.recursive else "*.png"
    png_files = sorted(args.directory.glob(glob_pattern))

    if not png_files:
        print(f"No PNG files found in {args.directory}")
        return 0

    adapter = InvokeGenerationMetadataAdapter()
    total = len(png_files)
    parsed_ok = 0
    no_metadata = 0
    json_errors = []
    parse_errors = []
    file_errors = []

    for png_path in png_files:
        try:
            raw = extract_invokeai_metadata(png_path)
        except Exception as e:
            file_errors.append((png_path, e))
            continue
        if raw is None:
            no_metadata += 1
            continue

        # Step 1: decode JSON
        try:
            json_data = json.loads(raw)
        except json.JSONDecodeError as e:
            json_errors.append((png_path, e))
            continue

        # Step 2: parse with adapter
        try:
            adapter.parse(json_data)
            parsed_ok += 1
        except Exception as e:
            parse_errors.append((png_path, json_data, e))

    # ── Summary ──────────────────────────────────────────────────────
    print(f"\nScanned {total} PNG files:")
    print(f"  Parsed OK:      {parsed_ok}")
    print(f"  No metadata:    {no_metadata}")
    print(f"  Bad files:      {len(file_errors)}")
    print(f"  JSON errors:    {len(json_errors)}")
    print(f"  Parse errors:   {len(parse_errors)}")

    if file_errors:
        print("\n── Bad/unreadable PNG files ───────────────────────────")
        for path, err in file_errors:
            print(f"  {path}")
            print(f"    {type(err).__name__}: {err}")

    if json_errors:
        print("\n── JSON decode errors ─────────────────────────────────")
        for path, err in json_errors:
            print(f"  {path}")
            print(f"    {err}")

    if parse_errors:
        print("\n── Metadata parse errors ──────────────────────────────")
        for path, _data, err in parse_errors:
            print(f"  {path}")
            print(f"    {type(err).__name__}: {err}")

    # ── Save failures ────────────────────────────────────────────────
    if args.save_failures and parse_errors:
        examples_dir = Path(__file__).resolve().parent.parent / "tests" / "example_jsons"
        examples_dir.mkdir(parents=True, exist_ok=True)
        existing = sorted(examples_dir.glob("example*.json"))
        next_num = 1
        if existing:
            # Find highest existing example number
            last = existing[-1].stem  # e.g. "example12"
            next_num = int(last.removeprefix("example")) + 1

        saved = 0
        for path, data, _err in parse_errors:
            out_path = examples_dir / f"example{next_num}.json"
            out_path.write_text(json.dumps(data, indent=2) + "\n")
            print(f"  Saved: {out_path}  (from {path.name})")
            next_num += 1
            saved += 1
        print(f"\n  Wrote {saved} failed JSON(s) to {examples_dir}")

    return 1 if (json_errors or parse_errors) else 0


if __name__ == "__main__":
    sys.exit(main())
