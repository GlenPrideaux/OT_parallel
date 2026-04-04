#!/usr/bin/env python3
"""
02_parse_usfm.py

Parse USFM sources into verse-indexed JSON, preserving:

- Verse boundaries (\\c, \\v)
- USFM footnotes (\\f ... \\f*) extracted from \ft, optionally prefixed by \fr
- Poetry structure (\\q, \\q1, \\q2, \\m, \\p) encoded into the verse text using STRUCT_DELIM markers

Output:
  build/json/sourcefilename.json

Notes:
- It is intentionally conservative: it preserves content but normalises spacing/markup artefacts.
"""

import json, argparse
import re
from pathlib import Path

from definitions import *

# ----------------------------
# Paths
# ----------------------------
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "build" / "json" 
OUT.mkdir(parents=True, exist_ok=True)

quiet = 0

def extract_usfm_footnotes(raw: str) -> str:
    """
    Return text with USFM footnote blocks replaced inline by FOOTNOTE_DELIM markers.

    Turns:  ... \\f + \\fr 1:2 \\ft Note text...\\f* ...
    Into:   ... ␞FOOTNOTE␞1:2: Note text...␞FOOTNOTE␞ ...

    - Extracts \\ft content (concatenates multiple \\ft pieces)
    - If \\fr exists, prefixes note with 'ref: ' (your current behaviour)
    - Removes \\+xx / \\+xx* inline markers inside the footnote so \\ft capture isn't truncated
    """

    def repl(match):
        block = match.group(0)

        # Remove inline character-style markers (e.g., \+wh ... \+wh*, \xt, etc. )
        block = PLUS_MARK_RE.sub("", block)
        block = X_MARK_RE.sub("", block)
        # remove problematic \fl ... we don't check but should only be in footnotes
        block = FL_RE.sub(f"{FL_OPEN}\\1{FL_CLOSE}", block)
        block = FQ_RE.sub(f"{FQ_OPEN}\\1{FQ_CLOSE}", block)

        fr_m = FR_RE.search(block)
        fr = fr_m.group(1).strip() if fr_m else ""

        fts = [m.group(1).strip() for m in FT_RE.finditer(block)]
        ft = " ".join(fts).strip()

        if not ft:
            # Delete empty footnote blocks
            return " "

        note = f"{fr}: {ft}" if fr else ft

        # Inline footnote marker at the exact position
        return f"{FOOTNOTE_DELIM}{note}{FOOTNOTE_DELIM}"

    return FOOTNOTE_BLOCK_RE.sub(repl, raw)

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
    line = X_BLOCK_RE.sub("", line)
    
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
def parse_usfm_file(path: Path):
    """
    Parse a USFM file into a dict of verses keyed as "CH:V".

    - Captures \\c (chapter) and \\v (verse) markers.
    - Extracts USFM footnote blocks: \\f ... \\f* (keeps \ft content, optionally prefixed by \fr)
    - Preserves poetry structure via \\q/\\q1/\\q2, \\m, \\p (encoded into the verse string)
    - Normalises inline tags and spacing

    Returns: (book_id, verses_dict)
    """
    book = None
    chapter = None
    verses = {}  # key: "CH:V" -> encoded verse text with FOOTNOTE_DELIM markers

    current_v = None
    chunks = []    # list of encoded chunks (poetry/prose)
    after_d = False
    after_p = False
    
    def flush_current():
        nonlocal current_v, chunks
        if current_v is None:
            chunks = []
            return

        text = " ".join(chunks).strip()

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
                after_d = False
                raw_text = extract_usfm_footnotes(m.group(1))
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

            # Verse marker
            m = V_RE.match(s)
            if m and chapter is not None:
                flush_current()

                vnum = int(m.group(1))
                vsuf = (m.group(2) or "").lower()   # '', 'a', 'b', ...
                current_v = f"{chapter}:{vnum}{vsuf}"

                # start verse with any pending headings (if you still have that feature)
                # if pending_headings:
                #     chunks.extend(pending_headings)
                #     pending_headings = []

                raw_text = m.group(3)
                is_heading_verse = False
                is_para = False
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

                raw_text = extract_usfm_footnotes(raw_text)
                t = normalise_line(raw_text)
                if t:
                    if is_heading_verse:
                        t = STYLE_HDG + t
                    if is_para:
                        t = STYLE_PARA + t
                    chunks.append(encode_chunk("p", 0, t))
                continue
            
            # Continuation lines: may contain poetry markers or prose continuation
            if current_v is not None and s:
                # Poetry line?
                qm = Q_RE.match(s)
                if qm:
                    level = int(qm.group(1) or "1")
                    raw_text = qm.group(2)
                    raw_text = extract_usfm_footnotes(raw_text)
                    t = normalise_line(raw_text)
                    if t:
                        chunks.append(encode_chunk("q", level, t))
                    continue

                # Poetry paragraph (flush-left)
                mm = M_RE.match(s)
                if mm:
                    raw_text = mm.group(1)
                    raw_text = extract_usfm_footnotes(raw_text)
                    t = normalise_line(raw_text)
                    if t:
                        chunks.append(encode_chunk("q", 1, t))
                    continue

                # Prose paragraph marker
                pm = P_RE.match(s)
                if pm:
                    raw_text = STYLE_PARA + pm.group(1)
                    raw_text = extract_usfm_footnotes(raw_text)
                    t = normalise_line(raw_text)
                    if t:
                        chunks.append(encode_chunk("p", 0, t))
                    continue

                # Default continuation line (treat as prose continuation)
                raw_text = s
                raw_text = extract_usfm_footnotes(raw_text)
                t = normalise_line(raw_text)
                if t:
                    chunks.append(encode_chunk("p", 0, t))

    flush_current()
    return book, verses

def default_output_name(input_path: Path) -> Path:
    if input_path.suffix:
        return OUT / (input_path.stem + ".json")
    return OUT / (input_path.name + ".json")


# ----------------------------
# Main
# ----------------------------
def main():
    parser = argparse.ArgumentParser(
        description="Parse a USFM file and write as a JSON file."
    )
    parser.add_argument("input", help="input USFM file")
    parser.add_argument(
        "-o", "--output",
        default=None,
        help="output JSON file (default: input.json)"
    )
    global quiet
    parser.add_argument(
        "-q", "--quiet",
        action="store_true"
        )
    args = parser.parse_args()
    if args.quiet:
        quiet = True
        
    usfm_path = Path(args.input)
    book, verses = parse_usfm_file(usfm_path)

    out_path = Path(args.output) if args.output else default_output_name(usfm_path)
    
    out_path.write_text(json.dumps(verses, ensure_ascii=False, indent=2), encoding="utf-8")
    if not quiet:
        print(f"Wrote {out_path} ({len(verses)} verses) from {usfm_path}")

if __name__ == "__main__":
    main()
