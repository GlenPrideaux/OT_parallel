import csv, json, re, argparse
from pathlib import Path

from definitions import *

quiet = False

def load_spelling_map(path) -> dict[str, str]:
    mapping: dict[str, str] = {}
    path = Path(path)

    with path.open(encoding="utf-8") as f:
        for lineno, raw_line in enumerate(f, start=1):
            line = raw_line.strip()

            if not line or line.startswith("#"):
                continue

            try:
                src, dst = line.split("\t", 1)
            except ValueError as e:
                raise ValueError(
                    f"{path}:{lineno}: expected TAB-separated 'source<TAB>target'"
                ) from e

            if not src:
                raise ValueError(f"{path}:{lineno}: empty source spelling")

            # lowercase
            mapping[src] = dst
            # Capitalised
            mapping[src.capitalize()] = dst.capitalize()
            # Optional: ALL CAPS
            mapping[src.upper()] = dst.upper()
            
    return mapping

def apply_spelling_map(text: str, mapping: dict[str, str]) -> str:
    if not mapping:
        return text

    # Longest first avoids partial matches where one key contains another.
    pattern = re.compile(
        r"\b(" + "|".join(re.escape(k) for k in sorted(mapping, key=len, reverse=True)) + r")\b"
    )

    return pattern.sub(lambda m: mapping[m.group(0)], text)



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

def ref_to_tuple(ref: str):
    ch, v, suf = parse_ref(ref)
    suf_ord = 0 if suf == "" else (ord(suf) - ord("a") + 1)
    return (ch, v, suf_ord)

def expand_range(dict, start_ref: str, end_ref: str):
    keys = list(dict)
    start = keys.index(start_ref)
    end = keys.index(end_ref)
    parts = list(dict.keys())[start:end+1]
#    print(f"expand_range {start_ref}-{end_ref} returns\n{parts}")
    return parts

def get_text(mt_dict, mt_ref: str) -> str:
    if not mt_ref.strip():
        return ""
    m = RANGE_RE.match(mt_ref.strip())
    if m:
        start, end = m.group(1), m.group(2)
        parts = []
        for r in expand_range(mt_dict, start, end):
            t = mt_dict.get(r, "")
            if t:
                parts.append(t)
        return " ".join(parts).strip()
    return mt_dict.get(mt_ref.strip(), "")

def sort_key(ref: str):
    return ref_to_tuple(ref)

# We offload to the makefile the specification of files so we no longer need to use the index file.
# This enables us to only rebuild the brenton updated files and json files that are actually needed rather
# than always building everything. 
def main():
    parser = argparse.ArgumentParser(description="Prepare a CSV of parallel passages verse by verse")
    parser.add_argument("book", help="book name")
    parser.add_argument(
        "-o", "--output",
        default=None,
        help="output CSV file (default: build/book_name.csv)"
    )
    parser.add_argument(
        "-W", "--web",
        default=None,
        help="WEB file to be used for the first column"
    )
    parser.add_argument(
        "-B", "--brenton",
        default=None,
        help="Brenton (updated) file to be used for the second column"
    )
    parser.add_argument(
        "-P", "--prideaux",
        default=None,
        help="Prideaux file to be used for the third column (if any)"
    )
    parser.add_argument(
        "-M", "--mapping",
        default=None,
        help="Verse mapping file to link the columns"
    )

    parser.add_argument("-b", action="store_true", help="Use the British English version")
    global quiet
    parser.add_argument("-q", "--quiet", action="store_true")
    args = parser.parse_args()
    if args.quiet:
        quiet = True

    ROOT = Path(__file__).resolve().parents[1]
    if args.b:
        SPELLING = ROOT / "data" / "us_to_uk.tsv"
    else:
        SPELLING = ROOT / "data" / "uk_to_us.tsv"
    spelling_map = load_spelling_map(SPELLING)

#    INDEX = ROOT / "build" / "index" / "index.csv"
#    with INDEX.open(newline="", encoding="utf-8") as f:
#        web = None
#        for r in csv.DictReader(f):
#            if args.book.strip() == r["book"].strip():
#                web = r["web"]
#                webbe = r["webbe"]
#                brenton = r["Brenton"]
#                prideaux = r["Prideaux"]
#                break
    web = args.web
    brenton = args.brenton
    prideaux = args.prideaux
    if web == None:
        raise ValueError(f"No WEB file specified")
    if brenton == None:
        raise ValueError(f"No Brenton file specified")

    # use the mapping override file ... if it doesn't exist fall back to the generated mapping file
#    MAP = ROOT / "data" / "mapping" / (Path(web).stem + ".csv")
#    if not MAP.exists():
#        MAP = ROOT / "build" / "mapping" / (Path(web).stem + ".csv")
    MAP = ROOT / args.mapping
    if MAP == None:
        raise ValueError(f"No verse mapping file specified")
    MT = ROOT / web
    LXX = ROOT / brenton
    OTHER = ROOT / prideaux if prideaux else None
    OUT = Path(args.output) if args.output else ROOT / "build" / (f"{args.book}_parallel" + ("_be.csv" if args.b else ".csv"))

#    print(f"MAP={MAP}\nMT={MT}\nLXX={LXX}\nOUT={OUT}")
#    print(LXX.read_text(encoding="utf-8"))
    lxx_dict = json.loads(LXX.read_text(encoding="utf-8"))
    mt_dict  = json.loads(MT.read_text(encoding="utf-8"))
    if not OTHER is None:
        other_dict = json.loads(OTHER.read_text(encoding="utf-8"))
    rows = []
    subs_ref = False
    with MAP.open(newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            nb = r.get("notes","")
            if nb and nb.startswith("SUBS_LXX"):
                subs_ref = True
                if not quiet:
                    print("SUBS_LXX detected")
            ch = r["ch"]
            my_ref = r.get("my_ref","").strip()
            lxx_ref = r.get("lxx_ref","").strip()
            mt_ref  = (r.get("mt_ref") or "").strip()
            lxx_txt = apply_spelling_map(get_text(lxx_dict,lxx_ref), spelling_map)
            mt_txt  = get_text(mt_dict, mt_ref)
            if OTHER is None:
                rows.append({
                    "ch": ch,
                    "my_ref": lxx_ref,
                    "lxx_ref": my_ref if subs_ref else lxx_ref,
                    "lxx_text": lxx_txt,
                    "mt_ref": mt_ref,
                    "mt_text": mt_txt,
                })
            else:
                other_ref = (r.get("other_ref") or "").strip()
                other_txt = apply_spelling_map(get_text(other_dict,other_ref), spelling_map)
                rows.append({
                    "ch": ch,
                    "my_ref": lxx_ref,
                    "lxx_ref": my_ref if subs_ref else lxx_ref,
                    "lxx_text": lxx_txt,
                    "mt_ref": mt_ref,
                    "mt_text": mt_txt,
                    "other_ref": other_ref,
                    "other_text": other_txt
                })


    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", newline="", encoding="utf-8") as f:
        if OTHER is None:
            w = csv.DictWriter(f, fieldnames=["ch","my_ref","mt_ref","mt_text","lxx_ref","lxx_text"])
        else:
            w = csv.DictWriter(f, fieldnames=["ch","my_ref","mt_ref","mt_text","lxx_ref","lxx_text", "other_ref", "other_text"])
        w.writeheader()
        w.writerows(rows)

    if not quiet:
        print(f"Wrote {OUT} ({len(rows)} rows)")

if __name__ == "__main__":
    main()
