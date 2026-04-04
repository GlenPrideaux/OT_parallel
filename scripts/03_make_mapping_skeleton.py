import json, argparse
import csv
from pathlib import Path

quiet = False
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "build" / "mapping"

import re

REF_RE = re.compile(r'^(\d+):(\d+)([a-z]?)$', re.IGNORECASE)

def parse_ref(ref: str) -> tuple[int, int, str]:
    """
    Parses '24:40a' -> (24, 40, 'a')
           '24:40'  -> (24, 40, '')
    """
    ref = ref.strip()
    m = REF_RE.match(ref)
    if not m:
        raise ValueError(f"Bad ref format: {ref!r}")
    ch = int(m.group(1))
    v  = int(m.group(2))
    suf = (m.group(3) or "").lower()
    return ch, v, suf

def ref_sort_key(ref: str) -> tuple[int, int, int]:
    """
    Sort order: 40 < 40a < 40b < 41
    """
    ch, v, suf = parse_ref(ref)
    suf_ord = 0 if suf == "" else (ord(suf) - ord("a") + 1)
    return (ch, v, suf_ord)

def sort_key(ref: str):
    return ref_sort_key(ref)

def sanity(ref: str, prev_ref: str):
    if prev_ref == '':
        return
    prev_ch, prev_v, prev_suf = sort_key(prev_ref)
    ch, v, suf = sort_key(ref)
    if not (ch == prev_ch + 1 and v == 1 or ch == prev_ch and v == prev_v + 1 or ch == prev_ch and v == prev_v and suf == prev_suf + 1):
        if not quiet:
            print(f"WARNING: {ref} follows {prev_ref} out of sequence")
    
def default_output_name(input_path: Path) -> Path:
    if input_path.suffix:
        return OUT / (input_path.stem + ".csv")
    return OUT / (input_path.name + ".csv")

def main():
    parser = argparse.ArgumentParser(
        description="Read a JSON scripture file and create a mapping CSV file ready for manual editing."
    )
    parser.add_argument("input", help="input JSON file")
    parser.add_argument(
        "-o", "--output",
        default=None,
        help="output CSV file (default: input.csv)"
    )
    global quiet
    parser.add_argument(
        "-q", "--quiet",
        action="store_true"
        )
    args = parser.parse_args()
    if args.quiet:
        quiet = True

    json_path = Path(args.input)
    out_path = Path(args.output) if args.output else default_output_name(usfm_path)

    verses = json.loads(json_path.read_text(encoding="utf-8"))
    refs = sorted(verses.keys(), key=sort_key)
    rowcount = 0
        
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="", encoding="utf-8") as f:
        prev_key = ""
        w = csv.writer(f)
        w.writerow(["ch", "my_ref", "mt_ref", "lxx_ref", "other_ref", "note"])
        prev_ch = None
        has_zero = False
        for r in refs:
            ch, v, suff = parse_ref(r)
            sanity(r, prev_key)
            prev_key = r
            if ch != prev_ch:
                has_zero = False
                prev_ch = ch
            if v == 0:
                has_zero = True
            v = v+1
            w.writerow([ch, r, r, r if not has_zero else f"{ch}:{v}", r])  # identity placeholder
            rowcount += 1
        if not quiet:
            print(f"Wrote skeleton mapping with {rowcount} rows -> {out_path}")
            print(f"Manually copy this to data/mapping/ and edit to align verses.")

if __name__ == "__main__":
    main()
