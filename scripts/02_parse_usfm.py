#!/usr/bin/env python3
"""
02_parse_usfm.py

Parse USFM sources into verse-indexed JSON, preserving:

- Verse boundaries (\\c, \\v)
- USFM footnotes (\\f ... \\f*) extracted from \ft, optionally prefixed by \fr
- Poetry structure (\\q, \\q1, \\q2, \\m, \\p) encoded into the verse text using STRUCT_DELIM markers
- USFM xrefs look like this: \\x + \\xo 1:27 \\xt Mat. 19. 4.\\x*. Parse them similarly to \\f
Output:
  build/json/sourcefilename.json

Notes:
- It is intentionally conservative: it preserves content but normalises spacing/markup artefacts.
"""

import json, argparse
import re, csv
from pathlib import Path

from definitions import *

debug = False
quiet = False

YAWEH_FN=[
    re.compile(re.escape(r'\f + \fr ')+r'\d+:\d+ '+re.escape(r'\ft When rendered in ALL CAPITAL LETTERS, “LORD” or “GOD” is the translation of God’s Proper Name (Hebrew “\+wh יהוה\+wh*”, usually pronounced Yahweh).\f*')),
    re.compile(re.escape(r'\f + \fr ')+r'\d+:\d+ '+re.escape(r'\ft LORD or GOD in all caps is from the Hebrew יהוה Yahweh except when otherwise noted as being from the short form יה Yah.\f*')),
    re.compile(re.escape(r'\f + \fr ')+r'\d+:\d+ '+re.escape(r'\ft LORD or GOD in all caps is from the Hebrew')+r'.+'+re.escape(r'\f*')),
    ]
# I suspect there's an issue with the Hebrew not being correctly identified by the RE in the second one, so I've put a wildcard match in there.

# ----------------------------
# Paths
# ----------------------------
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "build" / "json" 
OUT.mkdir(parents=True, exist_ok=True)

quiet = 0

def extract_usfm_footnotes(raw: str, chapter: str, verse: str, footnotes: dict[tuple[str, str], tuple[str, set[str], str]]) -> list[str, dict[tuple[str, str], tuple[str, set[str], str]]]:
    """
    Return text with USFM footnote blocks replaced inline by FOOTNOTE_DELIM markers.

    Turns:  ... \\f + \\fr 1:2 \\ft Note text...\\f* ...
    Into:   ... ␞FOOTNOTE␞1:2: Note text...␞FOOTNOTE␞ ...
    In the text we just put a chapter numbered marker and the FN text ␞FOOTNOTE␞1␞FOOTNOTE␞text␞FOOTNOTE␞full␞FOOTNOTE␞ that will later
    be replaced by the text including ref that is saved in the footnote dict keyed by chapter number and text and where full is 1
    if we are putting in the full footnote, or 0 if it is a repeat and we are only putting in the footnote reference (which will end up with
    FOOTNOTE_REPEAT marker in the text).

    - Extracts \\ft content (concatenates multiple \\ft pieces)
    - If \\fr exists, trust it, otherwise create it from chater and verse
    - Removes \\+xx / \\+xx* inline markers inside the footnote so \\ft capture isn't truncated
    """

    def repl(match):
        global debug
        if debug:
            print(f"In repl with match={match}")
        def verse_key(v: str):
            m = re.match(r"(\d+)([a-z]?)", v)
            num = int(m.group(1))
            suffix = m.group(2)
            return (num, suffix)
        block = match.group(0)
        if debug:
            print(f"block={{{block}}}")
        # Remove the Yaweh footnotes

        for fn in YAWEH_FN:
            old_block = block
            block, n = fn.subn("", block)
            if n>0:
                if debug:
                    print(f"Scratched {fn} from '{old_block}'->'{block}'")
                return block
        if "all caps" in block:
            print(f"ERROR: block missed skipping Yaweh footnote: {block}")
        # remove problematic \fl ... we don't check but should only be in footnotes
        old_block = block
        block,n = FL_RE.subn(f"{FL_OPEN}\\1{FL_CLOSE} \\\\", block)
        if n>0 and debug:
            print(f"...detected \\fl: {{{old_block}}}->{{{block}}}")
        block,n = FQ_RE.subn(f"{FQ_OPEN}\\1{FQ_CLOSE} \\\\", block)
        if n>0 and debug:
            print(f"...detected \\fq: {{{old_block}}}->{{{block}}}")
        block,n = XT_RE.subn(f"{FX_OPEN}\\1{FX_CLOSE}", block)
        if n>0 and debug:
            print(f"...detected \\xt: {{{old_block}}}->{{{block}}}")

        # Remove inline character-style markers (e.g., \+wh ... \+wh*, \xt, etc. )
        block = PLUS_MARK_RE.sub("", block)
        #block = X_MARK_RE.sub("", block)

        fr_m = FR_RE.search(block)
        fr = fr_m.group(1).strip() if fr_m else f"{chapter}:{verse}"
        m = FT_RE.search(block)
        preft=(block[fr_m.end() if fr_m else 4:m.start()]) if m else block[fr_m.end() if fr_m else 4:]
        preft = preft.replace(r"\f*","").strip()
        fts = [preft] + [m.group(1).strip() for m in FT_RE.finditer(block)]
        ft = " ".join(fts).strip()
        
        if not ft:
            # Delete empty footnote blocks
            return " "
        if debug:
            print(f"Found footnote in {chapter}:{verse} fr={{{fr}}}, ft={{{ft}}}")
        if (ft, chapter) in footnotes:
            ref, verselist, firstverse = footnotes[(ft, chapter)]
            verselist.add(verse)
            ref = f"{chapter}:" + ", ".join(sorted(verselist, key=verse_key))
            footnotes[(ft, chapter)] = [f"{ref}. ", verselist, firstverse]
            if not quiet:
                print(f"Merging footnotes in chapter {chapter} verse(s) {sorted(verselist, key=verse_key)}")
            full = 0
        else:
            footnotes[(ft, chapter)] = [f"{fr} ", {verse}, verse]
            full = 1
        # Inline footnote marker at the exact position
        return f"{FOOTNOTE_DELIM}BEGIN{chapter}:{verse}{FOOTNOTE_DELIM}{ft}{FOOTNOTE_DELIM}{full}END{FOOTNOTE_DELIM}"

    return FOOTNOTE_BLOCK_RE.sub(repl, raw), footnotes

def insert_footnotes(verses: dict, footnotes: dict) -> dict:
    def build_from_groups(m):
        chapter = m.group(1)
        verse = m.group(2)
        ft = m.group(3)
        full = m.group(4)
        note = footnotes[(ft, chapter)]
        if full == "1":
            footnote = FOOTNOTE_DELIM + note[0]+ft + FOOTNOTE_DELIM
        else:
            if verse == note[2]:
                footnote = FOOTNOTE_DELIM + f"{chapter}:{verse} See previous note." + FOOTNOTE_DELIM
            else:
                footnote = FOOTNOTE_DELIM + f"{chapter}:{verse} See previous note (v.{note[2]})" + FOOTNOTE_DELIM
                
        return footnote

    def process(s):
        pat = re.compile(FOOTNOTE_DELIM + r"BEGIN(\d+):(\d+[a-z]?)" + FOOTNOTE_DELIM + r"(.+?)" + FOOTNOTE_DELIM + r"([01])END" + FOOTNOTE_DELIM)
        result = []
        last = 0

        for m in pat.finditer(s):
            # text before match
            result.append(s[last:m.start()])

            # replacement
            replacement = build_from_groups(m)
            result.append(replacement)

            last = m.end()

        # tail
        result.append(s[last:])

        return ''.join(result)

    for verse in verses:
        verses[verse] = process(verses[verse])
    return verses

def extract_usfm_xrefs(raw: str) -> str:
    """
    Return text with USFM xref blocks replaced inline by XREF_DELIM markers.

    Turns:  ... \\x + \\xo 1:2 \\xt Note text...\\x* ...
    Into:   ... ␞XREF␞1:2: Note text...␞XREF␞ ...

    - Extracts \\xt content (concatenates multiple \\xt pieces)
    - If \\xo exists, prefixes note with 'ref: ' (your current behaviour)
    - Removes \\+xx / \\+xx* inline markers inside the footnote so \\xt capture isn't truncated
    """

    def repl(match):
        block = match.group(0)

        # Remove inline character-style markers (e.g., \+wh ... \+wh*,  etc. )
        block = PLUS_MARK_RE.sub("", block)

        xo_m = XO_RE.search(block)
        xo = xo_m.group(1).strip() if xo_m else ""

        xts = [m.group(1).strip() for m in XT_RE.finditer(block)]
        xt = " ".join(xts).strip()

        if not xt:
            # Delete empty xref blocks
            return " "

        note = f"{xo}: {xt}" if xo else xt

        # Inline footnote marker at the exact position
        return f"{XREF_DELIM}{note}{XREF_DELIM}"

    return XREF_BLOCK_RE.sub(repl, raw)

# ----------------------------
# Inline cleanup / normalisation
# ----------------------------

def normalise_line(line: str) -> str:
    """
    Clean a fragment of verse text (not the whole verse structure).
    IMPORTANT: Footnotes should already be extracted before calling this.
    """

    # Normalise non-breaking spaces
    line = line.replace("\u00A0", " ")
    line = W_BLOCK_RE.sub(r"\1", line)
    line = line.replace("\\add*", ADD_CLOSE)
    line = line.replace("\\add ", ADD_OPEN)
    line = line.replace("\\sc*", SC_CLOSE)
    line = line.replace("\\sc ", SC_OPEN)
    line = line.replace("\\sup*", SUP_CLOSE)
    line = line.replace("\\sup ", SUP_OPEN)
    line = line.replace("\\qs*", QS_CLOSE)
    line = line.replace("\\qs ", QS_OPEN)
    
    line = line.replace(LRM_UNICODE, "")
    
    # Remove pipe attributes (Strong’s/lemma/etc.)
    line = PIPE_ATTR_RE.sub("", line)

    #remove cross references
    #line = X_BLOCK_RE.sub("", line)
    
    # Remove leftover star markers
    line = STAR_RE.sub("", line)

    # Remove USFM inline markers (replace with a space to preserve word breaks)
    # But will it really remove word breaks anyway? Isn't this adding unwanted spaces?
    # This is what made the following ugly spacing hacks necessary.
    # Change to replace with empty string
    line = USFM_MARK_RE.sub("", line)

    # Remove stray pipes
    line = line.replace("|", " ")

    # Collapse whitespace early
    line = re.sub(r"\s+", " ", line).strip()

    # Fix contractions/possessives: apostrophe BETWEEN letters
    # don ' t -> don't, Yahweh ’s -> Yahweh’s
#    line = re.sub(r"(?<=\w)\s*([’'])\s*(?=\w)", r"\1", line)

    # Quote spacing:
    # Remove spaces AFTER opening quotes: ‘ I -> ‘I, “ I -> “I, ' I -> 'I
#    line = re.sub(r"([‘“'\"])\s+(\w)", r"\1\2", line)

    # Ensure a space AFTER closing double quotes when a word follows: ”for -> ” for
#    line = re.sub(r"([”\"])(\w)", r"\1 \2", line)

    # Ensure a space AFTER closing single quote ONLY when it follows punctuation:
    # ;’for -> ;’ for
#    line = re.sub(r"([,.;:!?])([’'])(\w)", r"\1\2 \3", line)

    # Remove space before common punctuation
#    line = re.sub(r"\s+([,.;:!?])", r"\1", line)

    return line


# ----------------------------
# Poetry structure encoding
# ----------------------------
# We encode structure into verse text so the LaTeX generator can render poetry lines:
#
#   ␞Q:2␞line text   (poetry line with indent level 2)
#   ␞P␞prose text    (prose chunk)
#
STRUCT_DELIM = "\u241E"  # ␞ (record separator symbol)
STYLE_HDG = f"{STRUCT_DELIM}STYLE:HDG{STRUCT_DELIM}"
STYLE_PARA = f"{STRUCT_DELIM}STYLE:PARA{STRUCT_DELIM}"

def encode_chunk(kind: str, indent: int, text: str) -> str:
    if kind == "q":
        return f"{STRUCT_DELIM}Q:{indent}{STRUCT_DELIM}{text}"
    return f"{STRUCT_DELIM}P{STRUCT_DELIM}{text}"


# ----------------------------
# Core parser
# ----------------------------
def parse_usfm_file(path: Path, xrefs: dict[str, str]):
    """
    Parse a USFM file into a dict of verses keyed as "CH:V".

    - Captures \\c (chapter) and \\v (verse) markers.
    - Extracts USFM footnote blocks: \\f ... \\f* (keeps \ft content, optionally prefixed by \fr)
    - Preserves poetry structure via \\q/\\q1/\\q2, \\m, \\p (encoded into the verse string)
    - Normalises inline tags and spacing

    Returns: (book_id, verses_dict)
    """
    book = None
    longbook = None
    chapter = None
    footnotes : dict[tuple[str, str], tuple[str, set[str]]] = {} # key: [text of the fn excluding the ref part., chapter]
    verses = {}  # key: "CH:V" -> encoded verse text with FOOTNOTE_DELIM markers

    current_v = None
    chunks = []    # list of encoded chunks (poetry/prose)
    after_d = False
    after_p = False
    after_q = False
    
    def flush_current():
        nonlocal current_v, chunks, book, xrefs
        if current_v is None:
            chunks = []
            return

        text = " ".join(chunks).strip()
        if not xrefs is None:
            key = f"{longbook} {current_v}"
            if debug:
                print(key)
            if key in xrefs:
                ref_list = xrefs[key]
                sp = text.find(STRUCT_DELIM,1)+1
                text=f"{text[:sp]}{XREF_DELIM}{current_v}: {ref_list}{XREF_DELIM}{text[sp:]}"
                if debug:
                    print(text)

        verses[current_v] = text
        chunks = []

    with path.open("r", encoding="utf-8", errors="ignore") as f:
        for raw in f:
            line = raw.rstrip("\n")

            # Book id
            if line.startswith("\\id "):
                parts = line.strip().split()
                if len(parts) >= 2:
                    book = parts[1].upper()
                continue
            # Long Book id
            if line.startswith("\\h "):
                longbook = line[3:].strip()
                continue

            s = line.strip()
            # Chapter marker
            m = C_RE.match(s)
            if m:
                flush_current()
                chapter = m.group(1)
                current_v = None
                continue


            # If we start with '\d ' and have additional content,
            # AND we are at the start of a chapter, we are probably a psalm heading
            # so treat it as verse zero
            m = D_RE.match(s)
            if m and current_v is None:
                current_v = f"{chapter}:0"
                verse_only = "0"
                after_d = False
                raw_text, footnotes = extract_usfm_footnotes(m.group(1), chapter, verse_only, footnotes)
                raw_text = extract_usfm_xrefs(raw_text)
                t = normalise_line(raw_text)
                if t:
                    t = STYLE_HDG + t
                    chunks.append(encode_chunk("p", 0, t))
                continue

            if s == r"\d":
                # we don't need to store \d itself for our purposes; just remember it
                after_d = True
                continue
            if s == r"\p" or s == r"\p ":
                # we don't need to store \p itself for our purposes; just remember it
                after_p = True
                continue
            if re.match(r"^\\q[1-9]?$",s):
                after_q = True
                continue
            # Verse marker
            m = V_RE.match(s)
            if m and chapter is not None:
                flush_current()

                vnum = int(m.group(1))
                vsuf = (m.group(2) or "").lower()   # '', 'a', 'b', ...
                current_v = f"{chapter}:{vnum}{vsuf}"
                verse_only = f"{vnum}{vsuf}"

                # start verse with any pending headings (if you still have that feature)
                # if pending_headings:
                #     chunks.extend(pending_headings)
                #     pending_headings = []

                raw_text = m.group(3)
                is_heading_verse = False
                is_para = False
                is_poet = False
                # If it follows \d, treat as a heading-verse
                if after_d:
                    is_heading_verse = True
                    after_d = False  # consumed the \d context
                else:
                    after_d = False  # \d context only applies to the immediate next verse
                # If it follows \p, treat as a paragraph starter
                if after_p:
                    is_para = True
                    after_p = False  # consumed the \d context
                else:
                    after_p = False  # \d context only applies to the immediate next verse
                if after_q:
                    is_poet = True
                after_q = False
                raw_text, footnotes = extract_usfm_footnotes(raw_text, chapter, verse_only, footnotes)
                raw_text = extract_usfm_xrefs(raw_text)
                t = normalise_line(raw_text)
                if t:
                    if is_heading_verse:
                        t = STYLE_HDG + t
                    if is_para:
                        t = STYLE_PARA + t
                    if is_poet:
                        chunks.append(encode_chunk("q", 0, t)) # verse level poetry has to be first level.
                    else:
                        chunks.append(encode_chunk("p", 0, t))
                continue
            
            # Continuation lines: may contain poetry markers or prose continuation
            if current_v is not None and s:
                # Poetry line?
                qm = Q_RE.match(s)
                if qm:
                    level = int(qm.group(1) or "1")
                    raw_text = qm.group(2)
                    raw_text, footnotes = extract_usfm_footnotes(raw_text, chapter, verse_only, footnotes)
                    raw_text = extract_usfm_xrefs(raw_text)
                    t = normalise_line(raw_text)
                    if t:
                        chunks.append(encode_chunk("q", level-1, t))
                    continue

                # Poetry paragraph (flush-left)
                mm = M_RE.match(s)
                if mm:
                    raw_text = mm.group(1)
                    raw_text, footnotes = extract_usfm_footnotes(raw_text, chapter, verse_only, footnotes)
                    raw_text = extract_usfm_xrefs(raw_text)
                    t = normalise_line(raw_text)
                    if t:
                        chunks.append(encode_chunk("q", 1, t))
                    continue

                # Prose paragraph marker
                pm = P_RE.match(s)
                if pm:
                    raw_text = STYLE_PARA + pm.group(1)
                    raw_text, footnotes = extract_usfm_footnotes(raw_text, chapter, verse_only, footnotes)
                    raw_text = extract_usfm_xrefs(raw_text)
                    t = normalise_line(raw_text)
                    if t:
                        chunks.append(encode_chunk("p", 0, t))
                    continue

                # Default continuation line (treat as prose continuation)
                raw_text = s
                raw_text, footnotes = extract_usfm_footnotes(raw_text, chapter, verse_only, footnotes)
                raw_text = extract_usfm_xrefs(raw_text)
                t = normalise_line(raw_text)
                if t:
                    chunks.append(encode_chunk("p", 0, t))

    flush_current()
    verses = insert_footnotes(verses, footnotes)
    return book, verses

def default_output_name(input_path: Path) -> Path:
    if input_path.suffix:
        return OUT / (input_path.stem + ".json")
    return OUT / (input_path.name + ".json")


# ----------------------------
# Main
# ----------------------------
def main():
    global quiet, debug
    parser = argparse.ArgumentParser(
        description="Parse a USFM file and write as a JSON file."
    )
    parser.add_argument("input", help="input USFM file")
    parser.add_argument(
        "-o", "--output",
        default=None,
        help="output JSON file (default: input.json)"
    )
    parser.add_argument(
        "-x", "--xrefs",
        default=None,
        help="insert cross references from file"
    )
    parser.add_argument(
        "-q", "--quiet",
        action="store_true"
        )
    parser.add_argument(
        "--debug",
        action="store_true"
        )
    args = parser.parse_args()
    if args.quiet:
        quiet = True
    if args.debug:
        debug = True

    xrefs=None
    if args.xrefs:
        xrefs={}
        xrefs_path = Path(args.xrefs)
        with open(xrefs_path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f, delimiter="\t")
            for row in reader:
                xrefs[row['ref']]=row['xrefs']
        if not quiet:
            print(f"Read {len(xrefs)} xrefs from {args.xrefs}")
    usfm_path = Path(args.input)
    book, verses = parse_usfm_file(usfm_path, xrefs)

    out_path = Path(args.output) if args.output else default_output_name(usfm_path)    
    out_path.write_text(json.dumps(verses, ensure_ascii=False, indent=2), encoding="utf-8")
    if not quiet:
        print(f"Wrote {out_path} ({len(verses)} verses) from {usfm_path}")

if __name__ == "__main__":
    main()
