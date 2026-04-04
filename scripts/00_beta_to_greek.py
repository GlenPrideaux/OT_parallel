#!/usr/bin/env python3

import argparse
import re
import unicodedata
from pathlib import Path

BETA_TO_GREEK = {
    "A": "α",
    "B": "β",
    "G": "γ",
    "D": "δ",
    "E": "ε",
    "Z": "ζ",
    "H": "η",
    "Q": "θ",
    "I": "ι",
    "K": "κ",
    "L": "λ",
    "M": "μ",
    "N": "ν",
    "C": "ξ",
    "O": "ο",
    "P": "π",
    "R": "ρ",
    "S": "σ",
    "T": "τ",
    "U": "υ",
    "F": "φ",
    "X": "χ",
    "Y": "ψ",
    "W": "ω",
}

COMBINING = {
    ")": "\u0313",   # smooth breathing
    "(": "\u0314",   # rough breathing
    "/": "\u0301",   # acute
    "\\": "\u0300",  # grave
    "=": "\u0342",   # circumflex
    "|": "\u0345",   # iota subscript
    "+": "\u0308",   # diaeresis
}

REF_RE = re.compile(r"^[1-4A-Za-z]+\s+\d+:\d+[a-z]?$")


def betacode_to_greek(token: str) -> str:
    """
    Convert a single Beta Code token (e.g. E)PI\\, *IWAKIM, BASILEU\\S)
    to Unicode Greek.
    """
    out = []
    i = 0
    uppercase = False
    pending_mods = []

    while i < len(token):
        ch = token[i]

        if ch == "*":
            uppercase = True
            i += 1
            continue

        if ch in COMBINING:
            pending_mods.append(COMBINING[ch])
            i += 1
            continue

        if ch.upper() in BETA_TO_GREEK:
            base = BETA_TO_GREEK[ch.upper()]
            if uppercase:
                base = base.upper()
                uppercase = False

            i += 1

            # collect any modifiers that follow this letter
            trailing_mods = []
            while i < len(token) and token[i] in COMBINING:
                trailing_mods.append(COMBINING[token[i]])
                i += 1

            greek_char = base + "".join(pending_mods) + "".join(trailing_mods)
            pending_mods = []
            out.append(greek_char)
            continue

        # preserve punctuation / anything else
        out.append(ch)
        i += 1

    greek = unicodedata.normalize("NFC", "".join(out))

    # final sigma
    greek = re.sub(r"σ(?=$|[.,;:!?·])", "ς", greek)
    if greek.endswith("σ"):
        greek = greek[:-1] + "ς"

    return greek


def flush(ref: str, words: list[str], out_lines: list[str]) -> None:
    if ref is None:
        return
    out_lines.append(ref)
    line = " ".join(words)
    line = re.sub(r"\s+([,.;:!?])", r"\1", line)
    out_lines.append(line)
    out_lines.append("")


def convert_mlxx(text: str) -> str:
    out_lines = []
    current_ref = None
    current_words = []

    for raw_line in text.splitlines():
        line = raw_line.strip()

        if not line:
            continue

        if REF_RE.match(line):
            flush(current_ref, current_words, out_lines)
            current_ref = line
            current_words = []
            continue

        first_field = line.split()[0]
        current_words.append(betacode_to_greek(first_field))

    flush(current_ref, current_words, out_lines)
    return "\n".join(out_lines).rstrip() + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Convert MLXX first-column Beta Code to readable Greek.")
    parser.add_argument("input", help="input MLXX file")
    parser.add_argument("-o", "--output", help="output file (default: stdout)")
    args = parser.parse_args()

    input_path = Path(args.input)
    text = input_path.read_text(encoding="utf-8")
    result = convert_mlxx(text)

    if args.output:
        Path(args.output).write_text(result, encoding="utf-8")
    else:
        print(result, end="")


if __name__ == "__main__":
    main()
