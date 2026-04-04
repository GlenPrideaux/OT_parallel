#!/usr/bin/env python3

import argparse, re
import csv
from pathlib import Path

quiet = False

def extract_h_line(path: Path) -> str:
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")
            if line.startswith(r"\h "):
                return line[3:].strip()
            if line == r"\h":
                return ""
    return ""


def build_index(input_dir: Path, alternate: Path, json_dir: Path, output_csv: Path) -> None:
    usfm_files = sorted(input_dir.glob("*.usfm"))
    index = {}
    for usfm_file in usfm_files:
        json_file = json_dir / (usfm_file.stem + ".json")
        book_name = extract_h_line(usfm_file)
        index[book_name] = json_file
    if alternate:
        usfm_files = sorted(alternate.glob("*.usfm"))
        for usfm_file in usfm_files:
            json_file = json_dir / (usfm_file.stem + ".json")
            book_name = extract_h_line(usfm_file)
            index[book_name] = json_file

    with output_csv.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["book_name", "file_name"])

        for book_name in index:
            json_file = index[book_name]
            writer.writerow([book_name, json_file])

def json_path(input_path: Path) -> Path:
    JSON = {
        Path("source/eng-web_usfm"): "build/json/WEB",
        Path("source/eng-webbe_usfm"): "build/json/WEBBE",
        Path("source/eng-Brenton-updated_usfm"): "build/json/Brenton",
        Path("build/eng-Brenton-updated_usfm"): "build/json/Brenton",
        Path("source/eng-Prideaux_usfm"): "build/json/Prideaux",
        }
    return Path(JSON[input_path])

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Create a CSV index of JSON files using the \\h lines in the corresponding USFM file."
    )
    parser.add_argument("input_dir", help="directory containing .usfm files")
    parser.add_argument("-a", "--alternate", default=None,help="alternate directory containing .usfm files")
    parser.add_argument("-j", "--json", default=None,help="directory containing .json files")
    parser.add_argument("-o", "--output", default=None, help="output CSV file (default: input_dir/index.csv)", )
    global quiet
    parser.add_argument("-q", "--quiet", action="store_true" )
    args = parser.parse_args()
    if args.quiet:
        quiet = True

    input_dir = Path(args.input_dir)
    alternate = Path(args.alternate) if args.alternate else None
    output_csv = Path(args.output) if args.output else input_dir / "index.csv"
    json = Path(args.json) if args.json else json_path(input_dir)
    build_index(input_dir, alternate, json, output_csv)
    if not quiet:
        print(f"Wrote {output_csv}")


if __name__ == "__main__":
    main()
