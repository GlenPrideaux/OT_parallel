#!/usr/bin/env python3

import argparse
import re
import unicodedata
import csv
from pathlib import Path


def load_tsv(path: Path):
    out = []
    with path.open(encoding="latin-1", newline="") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            if not any(row.values()):
                continue
            if row[next(iter(row))].strip().startswith("#"):
                continue
            out.append(row)
    return out

def write_tsv(d, path):
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, delimiter="\t")

        # header row
        writer.writerow(["ref", "xrefs"])

        # data rows
        for k, v in d.items():
            writer.writerow([k, v])
            
bible_books = {
    "Genesis": "Gen",
    "Exodus": "Exod",
    "Leviticus": "Lev",
    "Numbers": "Num",
    "Deuteronomy": "Deut",
    "Joshua": "Josh",
    "Judges": "Judg",
    "Ruth": "Ruth",
    "1 Samuel": "1 Sam",
    "2 Samuel": "2 Sam",
    "1 Kings": "1 Kgs",
    "2 Kings": "2 Kgs",
    "1 Chronicles": "1 Chron",
    "2 Chronicles": "2 Chron",
    "Ezra": "Ezra",
    "Nehemiah": "Neh",
    "Esther": "Esth",
    "Job": "Job",
    "Psalms": "Ps",
    "Proverbs": "Prov",
    "Ecclesiastes": "Eccl",
    "Song of Solomon": "Song",
    "Isaiah": "Isa",
    "Jeremiah": "Jer",
    "Lamentations": "Lam",
    "Ezekiel": "Ezek",
    "Daniel": "Dan",
    "Hosea": "Hos",
    "Joel": "Joel",
    "Amos": "Amos",
    "Obadiah": "Obad",
    "Jonah": "Jonah",
    "Micah": "Mic",
    "Nahum": "Nah",
    "Habakkuk": "Hab",
    "Zephaniah": "Zeph",
    "Haggai": "Hag",
    "Zechariah": "Zech",
    "Malachi": "Mal",
    "Matthew": "Matt",
    "Mark": "Mark",
    "Luke": "Luke",
    "John": "John",
    "Acts": "Acts",
    "Romans": "Rom",
    "1 Corinthians": "1 Cor",
    "2 Corinthians": "2 Cor",
    "Galatians": "Gal",
    "Ephesians": "Eph",
    "Philippians": "Phil",
    "Colossians": "Col",
    "1 Thessalonians": "1 Thess",
    "2 Thessalonians": "2 Thess",
    "1 Timothy": "1 Tim",
    "2 Timothy": "2 Tim",
    "Titus": "Titus",
    "Philemon": "Phlm",
    "Hebrews": "Heb",
    "James": "Jas",
    "1 Peter": "1 Pet",
    "2 Peter": "2 Pet",
    "1 John": "1 John",
    "2 John": "2 John",
    "3 John": "3 John",
    "Jude": "Jude",
    "Revelation": "Rev"
    }

def abbrev(full_name: str) -> str:
    return bible_books[full_name]

book_positions = {k: i for i, k in enumerate(bible_books, start=1)}
abbrev_positions = {abbrev(k): i for i, k in enumerate(bible_books, start=1)}

def get_position(d, key):
    for i, k in enumerate(d.keys(), start=1):
        if k == key:
            return i
    return None

def is_OT(book:str) -> bool:
    return (book_positions[book] < 40 )

def format_ref(book, ch, v, fullnames=False):
    if fullnames:
        return f"{book} {ch}:{v}"
    else:
        return abbrev(book)+f" {ch}:{v}"
def format_range(book, cha, va, chb, vb):
    rval = format_ref(book, cha, va)
    if (cha == chb or chb == '') and va != vb and vb != '':
        rval = f"{rval}--{vb}"
    if cha != chb and chb != '':
        rval = f"{rval}--{chb}:{vb}"
    return rval

def parse_ref(ref, fullnames=False):
    pattern = re.compile(r"^(.+?)\s+(\d+):(\d+)(--.+)?$")
    m = pattern.match(ref)
    if not m:
        raise ValueError(f"Invalid ref: {ref}")
    book, chapter, verse, rest = m.groups()
    return (book_positions[book] if fullnames else abbrev_positions[book]), int(chapter), int(verse), rest

def combine_targets(target, prev_target, this_target):
    prev_book, prev_chapter, prev_verse, prev_rest = parse_ref(prev_target)
    book, chapter, verse, rest = parse_ref(this_target)
    # If they're the same, don't repeat
    if book == prev_book and chapter == prev_chapter and verse == prev_verse and rest == prev_rest:
        return target
    if book != prev_book:
        return f"{target}, {this_target}"
    if prev_rest and not rest:
        # this target is a single verse. Is it included in the previous range?
        pattern = re.compile(r"^--(?:(\d+):)?(\d+)$")
        m = pattern.match(prev_rest)
        if m[1] > chapter or m[2] > verse:
            # this target is included in the previous range; drop it.
            return target
        if m[1] == chapter or prev_chapter == chapter and not m[1]:
            # same chapter; just append a verse
            return f"{target}, {verse}"
        # otherwise append the chapter and verse
        return f"{target}, {chapter}:{verse}"
    #if rest and not prev_rest:
        # previous target was a single verse. Is it included in this range? Actually sorting prevents this since the first verse
        # of the current range must come after the previous verse, so we're always going to append.
    if chapter == prev_chapter:
        return f"{target}, {verse}"
    else:
        return f"{target}, {chapter}:{verse}"


    
def main() -> None:
    parser = argparse.ArgumentParser(description="Convert xref spreadsheet into a usable database of cross references for insertion into the WEB.")
    parser.add_argument("-i", "--input", help="--input .tsv file (default data/002xref.tsv)", default="data/002xref.tsv")
    parser.add_argument("-o", "--output", help="output file (default: build/xref.tsv)", default="build/xref.tsv")
    parser.add_argument("-q", "--quiet",  action="store_true")
    args = parser.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output)
    
    raw = load_tsv(input_path)
    cooked = []
    for row in raw:
        a_ref = format_ref(row['Book_1'],row['Ch_1_1'],row['V_1_1'], fullnames=True)
        a_range = format_range(row['Book_1'],row['Ch_1_1'],row['V_1_1'],row['Ch_1_2'],row['V_1_2']) 
        b_ref = format_ref(row['Book_2'],row['Ch_2_1'],row['V_2_1'], fullnames=True)
        b_range = format_range(row['Book_2'],row['Ch_2_1'],row['V_2_1'],row['Ch_2_2'],row['V_2_2']) 
        if is_OT(row['Book_1']):
            cooked.append([a_ref, b_range])
        if is_OT(row['Book_2']):
            cooked.append([b_ref, a_range])
    cooked.sort(key=lambda x: parse_ref(x[0], fullnames=True)+parse_ref(x[1]))
    packaged={}
    prev = None
    targets = None
    prev_target = None
    for ref in cooked:
        #print(f"ref={ref} prev={prev} targets={targets} prev_target={prev_target}")
        if ref[0] != prev:
            if prev:
                packaged[prev] = targets
            prev = ref[0]
            targets = ref[1]
            prev_target = ref[1]
        else:
            targets = combine_targets(targets, prev_target, ref[1])
            prev_target = ref[1]
    if targets:
        packaged[prev] = targets

    write_tsv(packaged, output_path)
    if not args.quiet:
        print(f"Wrote cross references to {args.output}")
    #print(packaged)
if __name__ == "__main__":
    main()
