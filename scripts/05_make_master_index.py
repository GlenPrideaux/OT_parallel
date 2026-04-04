#!/usr/bin/env python3

import argparse
import csv
from pathlib import Path

quiet = False

BOOK_MAP = {
    # Pentateuch
    "Genesis": "Genesis",
    "Exodus": "Exodus",
    "Leviticus": "Leviticus",
    "Numbers": "Numbers",
    "Deuteronomy": "Deuteronomy",

    # Historical books
    "Jesus Nave": "Joshua",
    "Judges": "Judges",
    "Ruth": "Ruth",
    "Kings I": "1 Samuel",
    "Kings II": "2 Samuel",
    "Kings III": "1 Kings",
    "Kings IV": "2 Kings",
    "Chronicles I": "1 Chronicles",
    "Chronicles II": "2 Chronicles",
    "Esdras I": "1 Esdras",
    "Esdras II": "Ezra",
    "Nehemiah": "Nehemiah",
    "Tobit": "Tobit",
    "Judith": "Judith",
    "Esther": "Esther",
    "Esther (Greek)": "Esther (Greek)",
    "1 Maccabees": "1 Maccabees",
    "2 Maccabees": "2 Maccabees",
    "3 Maccabees": "3 Maccabees",
    "4 Maccabees": "4 Maccabees",

    # Wisdom / poetry
    "Psalms": "Psalms",
    "Psalm": "Psalms",
    "Prayer of Manasses": "Prayer of Manasseh",
    "Job": "Job",
    "Proverbs": "Proverbs",
    "Ecclesiastes": "Ecclesiastes",
    "Canticles": "Song of Solomon",
    "Wisdom": "Wisdom",
    "Wisdom of Solomon": "Wisdom",
    "Wisdom Of Solomon": "Wisdom",
    "Ecclesiasticus": "Sirach",
    "Sirach": "Sirach",

    # Major prophets
    "Esaias": "Isaiah",
    "Jeremias": "Jeremiah",
    "Baruch": "Baruch",
    "Lamentations": "Lamentations",
    "Epistle of Jeremy": "Letter of Jeremiah",
    "Jezekiel": "Ezekiel",
    "Daniel (Greek)": "Daniel (Greek)",
    "Susanna": "Susanna",
    "Bel and the Dragon": "Bel and the Dragon",

    # Minor prophets
    "Osee": "Hosea",
    "Amos": "Amos",
    "Michæas": "Micah",
    "Joel": "Joel",
    "Obdias": "Obadiah",
    "Jonas": "Jonah",
    "Naum": "Nahum",
    "Ambacum": "Habakkuk",
    "Sophonias": "Zephaniah",
    "Aggæus": "Haggai",
    "Zacharias": "Zechariah",
    "Malachias": "Malachi",
    "Ezra and Nehemiah": "Ezra",
}

# Helpful alternate forms
ALIASES = {
    "Kingdoms I": "Kings I",
    "Kingdoms II": "Kings II",
    "Kingdoms III": "Kings III",
    "Kingdoms IV": "Kings IV",
    "1 Kingdoms": "Kings I",
    "2 Kingdoms": "Kings II",
    "3 Kingdoms": "Kings III",
    "4 Kingdoms": "Kings IV",
    "1 Kings (LXX)": "Kings I",
    "2 Kings (LXX)": "Kings II",
    "3 Kings (LXX)": "Kings III",
    "4 Kings (LXX)": "Kings IV",
    "Oseee": "Osee",
    "Habacuc": "Ambacum",
    "Habakkuk": "Ambacum",
}


def translate_book_name(name: str) -> str:
    name = name.strip()
    name = ALIASES.get(name, name)
    return BOOK_MAP.get(name, name)


def read_index(path: Path) -> dict[str, str]:
    data: dict[str, str] = {}

    with path.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            book = translate_book_name(row["book_name"].strip())
            # Esther and Daniel need special treatment
            if book == "Esther (Greek)" and not "web" in str(path):
                book = "Esther"
            if book == "Daniel (Greek)" and not "web" in str(path):
                book = "Daniel"
            file_name = row["file_name"].strip()
            data[book] = file_name

    return data

def make_safe(book: str) -> str:
    return book.replace(" ", "_").replace("(", "").replace(")", "")


def build_master_index(base_dir: Path, output_csv: Path) -> None:
    web_index = read_index(base_dir / "web" / "index.csv")
    webbe_index = read_index(base_dir / "webbe" / "index.csv")
    brenton_index = read_index(base_dir / "Brenton" / "index.csv")
    prideaux_index = read_index(base_dir / "Prideaux" / "index.csv")

    output_mk = base_dir / "index.mk"
    
    all_books = sorted(set(web_index) & set(webbe_index) & set(brenton_index), key=lambda b: int(Path(web_index[b]).name.split("-", 1)[0]))
    if not quiet:
        print(all_books)
    ot = ["OT",":="]
    with output_csv.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, delimiter=' ')
        for book in all_books:
            writer.writerow([
                "BOOK_0" + (Path(web_index.get(book, "")).name.split("-",1)[0]) + "-" + make_safe(book),
                ":=",
                make_safe(book),
                web_index.get(book, ""),
                webbe_index.get(book, ""),
                brenton_index.get(book, ""),
                prideaux_index.get(book, ""),
            ])
            ot.append("0" + (Path(web_index.get(book, "")).name.split("-",1)[0]) + "-" + make_safe(book))
        writer.writerow(ot)
            

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Combine web, webbe, and Brenton book indices into a master index."
    )
    parser.add_argument(
        "--base-dir",
        default="build/index",
        help="base directory containing web/, webbe/, and Brenton/ (default: build/index)",
    )
    parser.add_argument(
        "-o",
        "--output",
        default=None,
        help="output CSV file (default: <base-dir>/index.csv)",
    )
    global quiet
    parser.add_argument(
        "-q", "--quiet",
        action="store_true"
        )
    args = parser.parse_args()
    if args.quiet:
        quiet = True

    base_dir = Path(args.base_dir)
    output_csv = Path(args.output) if args.output else base_dir / "index.csv"

    build_master_index(base_dir, output_csv)
    if not quiet:
        print(f"Wrote {output_csv}")


if __name__ == "__main__":
    main()
