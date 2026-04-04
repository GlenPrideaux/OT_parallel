import csv, json, re, argparse
from pathlib import Path

from definitions import *


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
    return parts

def sort_key(ref: str):
    return ref_to_tuple(ref)

def main():
    parser = argparse.ArgumentParser(description="Check that the mapping includes every verse")
    parser.add_argument("book", help="book name")
    parser.add_argument("--source", "-s", default = "Brenton", help = "web or Brenton or Prideaux: check which input"
    )

    args = parser.parse_args()

    ROOT = Path(__file__).resolve().parents[1]

    INDEX = ROOT / "index.mk"
    with INDEX.open(newline="", encoding="utf-8") as f:
        web = None
        for r in csv.DictReader(f, delimiter=' ', fieldnames=['bookid','equal','book','web','webbe','Brenton','Prideaux']):
            if args.book.strip().replace(' ','_').lower() == r["book"].strip().lower():
                web = r["web"]
                webbe = r["webbe"]
                brenton = r["Brenton"]
                prideaux = r["Prideaux"]
                break
    if web == None:
        raise ValueError(f"No mapping found for book name: {args.book}")

    # use the mapping override file ... if it doesn't exist fall back to the generated mapping file
    MAP = ROOT / "data" / "mapping" / (Path(web).stem + ".csv")
    if not MAP.exists():
        MAP = ROOT / "build" / "mapping" / (Path(web).stem + ".csv")
        
    MT = ROOT / web
    LXX = ROOT / brenton
    Prideaux = ROOT / prideaux

    if args.source.lower() == "web":
        source = MT
    elif args.source.lower() == "prideaux":
        source = Prideaux
    elif args.source.lower() == "brenton":
        source = LXX
    else:
        raise ValueError("Invalid source: we only recognise web, Brenton and Prideaux.")
#    print(f"MAP={MAP}\nMT={MT}\nLXX={LXX}\nOUT={OUT}")
#    print(LXX.read_text(encoding="utf-8"))
    dict = json.loads(source.read_text(encoding="utf-8"))

    with MAP.open(newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if args.source.lower() == "web":
                ref = r["mt_ref"].strip()
            elif args.source.lower() == "brenton":
                ref = r["lxx_ref"].strip()
            else:
                ref = r["other_ref"].strip()
            if not ref:
                continue
            m = RANGE_RE.match(ref)
            if m:
                start, end = m.group(1), m.group(2)
                for r in expand_range(dict, start, end):
                    if r in dict:
                        del dict[r]
                    else:
                        print(f"   (Map references {ref} but no such verse is found in source.)") 
            else:
                if ref in dict:
                    del dict[ref]
                else:
                    print(f"   (Map references {ref} but no such verse is found in source.)") 
    if len(dict) > 0:
        print("UNUSED VERSES! The following verses exist in the source but are not referenced in the mapping file.")
        for ref in dict.keys():
            print(f"\t {ref}")
    else:
        print("No unused verses.")

if __name__ == "__main__":
    main()
