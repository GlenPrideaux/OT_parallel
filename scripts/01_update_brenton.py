#!/usr/bin/env python3

import argparse
import csv
import re
import time
from pathlib import Path
from typing import Dict, List, Pattern, Tuple

quiet = False
progress = False

FootnoteState = bool


def load_tsv_dict(path: Path) -> Dict[str, str]:
    out: Dict[str, str] = {}
    with path.open(encoding="utf-8") as f:
        reader = csv.reader(f, delimiter="\t")
        for row in reader:
            if not row:
                continue
            if row[0].strip().startswith("#"):
                continue
            if len(row) > 3 or len(row) < 2 or not row[1].strip():
                raise ValueError(f"{path}: expected 2 columns, got {row!r}")
            out[row[0]] = row[1]
            if row[0].capitalize() != row[0]:
                out[row[0].capitalize()] = row[1].capitalize()
    return out

def load_verb_dict(path: Path) -> Dict[str, Tuple[str, str, str]]:
    out: Dict[str, [str, str, str]] = {}
    with path.open(encoding="utf-8") as f:
        reader = csv.reader(f, delimiter=",")
        for row in reader:
            if not row:
                continue
            if row[0].strip().startswith("#"):
                continue
            if len(row) > 3 or len(row) < 2 or not row[1].strip():
                raise ValueError(f"{path}: expected 2 or 3 columns, got {row!r}")
            repl = row[2] if len(row) == 3 else row[1]
            out[row[1]] = [row[0], repl, repl]
            if row[1].capitalize() != row[1]:
                out[row[1].capitalize()] = [row[0].capitalize(), repl, repl.capitalize()]
    return out

def load_tsv_rules(path: Path) -> List[Tuple[Pattern[str], str]]:
    rules: List[Tuple[Pattern[str], str, int]] = []
    with path.open(encoding="utf-8") as f:
        reader = csv.reader(f, delimiter="\t")
        for row in reader:
            if not row[0].strip():
                continue
            if row[0].strip().startswith("#"):
                continue
            if len(row) > 3 or len(row) < 2 or not row[1].strip():
                raise ValueError(f"{path}: expected 2 or 3 columns, got {row!r}")
            rules.append((re.compile(row[0]), row[1]))
    return rules


def apply_word_subs(text: str, mapping: Dict[str, str], word_counts: Dict[str,int]) -> Tuple[str, Dict[str, int]]:
    if not mapping:
        return text, word_counts,0

    start = time.perf_counter()
    pattern = re.compile(
        r"\b(" + "|".join(sorted(map(re.escape, mapping.keys()), key=len, reverse=True)) + r")\b"
    )
    def replacer(m):
        word = m.group(0)
        if word.lower() in word_counts:
            word_counts[word.lower()] += 1
        else:
            word_counts[word.lower()] = 1
        return mapping[word]
    text = pattern.sub(replacer, text)
    return [text, word_counts, time.perf_counter()-start]

CAPITALISE_RE = re.compile(r"\^\((\w+)\)")
def make_capitalised(match):
    word = match.group(1)
    return word.capitalize()

def apply_phrase_rules(text: str,
                           rules: List[Tuple[Pattern[str], str]],
                           phrase_counts: List[int],
                           ) -> Tuple[str, Dict[str, int]]:
    start = time.perf_counter()
    i = 0
    for pattern, repl in rules:
        if pattern:
            text, n = pattern.subn(repl, text)
            phrase_counts[i] += n
        i += 1
    if CAPITALISE_RE.search(text):
        text = CAPITALISE_RE.sub(make_capitalised, text)
    return [text, phrase_counts, time.perf_counter()-start]

# replace "Seek not" with "Don't seek"; "fear not" with "don't be afraid", etc.
# also "fear them not" with "don't fear them"
# Experimental imperatives: "Arise ye" with "Arise"; but not "Enter thou and all thy family"
# and not if a ? follows, in which case we change "Know ye" to "Do you know"
def apply_verb_rules(text: str, rules: List[Tuple[str, Tuple[str,str,str]]], verb_counts: List[int]) -> Tuple[str, List[int]]:
    times = [0,0,0,0,0]
    dontlist = ""
    Dontlist = ""
    verblist = ""
    for verb, [dont,repl,caprepl]  in rules.items():
        verblist = verblist + "|" + verb if verblist else verb
        if dont == "don't" : # might be an imperative; doesn't or didn't would be indicative
            dontlist = verb if not dontlist else dontlist + "|" + verb 
        if dont == "Don't" : # might be an imperative; doesn't or didn't would be indicative
            Dontlist = verb if not Dontlist else Dontlist + "|" + verb

        
    start = time.perf_counter()
    count = 0
    def inc_count(key):
        verb_counts[key] = verb_counts[key] + 1 if verb_counts[key] else 1
    # verb not -> don't verb
    # verbest not -> doesn't verb
    def vn_replacer(m):
        inc_count(m.group(1).lower())
        return rules[m.group(1)][0] + " " + rules[m.group(1)][1] 
    start = time.perf_counter()
    pattern = re.compile(r"\b(" + verblist + r") not\b")
    text = pattern.sub(vn_replacer, text)
    times[0]=time.perf_counter()-start

    # verb (ye|thou) not -> don't you verb ... invariably a question
    def vyn_replacer(m):
        inc_count(m.group(1).lower())
        return rules[m.group(1)][0] + " " + m.group(2) + " " + rules[m.group(1)][1] 
    start = time.perf_counter()
    pattern = re.compile(r"\b(" + verblist + r") (thou|ye) not\b")
    text = pattern.sub(vyn_replacer, text)
    times[1]=time.perf_counter()-start

    # verb something not -> don't verb something
    # verbeth something not -> doesn't verb something

    def vsn_replacer(m):
        inc_count(m.group(1).lower())
        return rules[m.group(1)][0] + " " + rules[m.group(1)][1] + " " + m.group(2)
    start = time.perf_counter()
    pattern = re.compile(r"\b(" + verblist + r") ([a-zA-Z]+|\\add [^\\]+\\add\*) not\b")
    text = pattern.sub(vsn_replacer, text)        
    times[2]=time.perf_counter()-start

    # verb you ... ? -> do you verb ... ?
    start = time.perf_counter()
    doyou="do you "
    def dy_replacer(m):
        inc_count(m.group(1).lower())
        return doyou + rules[m.group(1)][1] + m.group(3)
    pattern = re.compile(f"\\b({dontlist})\s+(ye|thou)\b([^.?]+\\?)")
    text = pattern.sub(dy_replacer, text)
    doyou="Do you "
    pattern = re.compile(f"\\b({Dontlist})\s+(ye|thou)\b([^.?]+\\?)")
    text = pattern.sub(dy_replacer, text)
    times[3]=time.perf_counter()-start
    
    # verb ye ... (not a question) -> verb ... unless it's verb ye and ...
    start = time.perf_counter()
    def vy_replacer(m):
        inc_count(m.group(1).lower())
        return rules[m.group(1)][2] + m.group(3)
    pattern = re.compile(r"\b(" + dontlist + "|" + Dontlist + r")\s+(ye|thou)\b(?!\s+and\b)([^.?]*\.)") # verb thou (not and) ... . (not ?)
    text = pattern.sub(vy_replacer, text)
    times[4]=time.perf_counter()-start

    return [text, verb_counts, times]

QUESTION_RE = re.compile(r"[!?]\s+([a-z])")
def cleanup_text(text: str) -> str:
    nl = text.endswith("\n")
    text = re.sub(r"\b[Dd]o not be be\b", lambda m: "Do not be" if m.group(0)[0].isupper() else "do not be", text)
    text = re.sub(r"\s{2,}", " ", text)
    if nl and not text.endswith("\n"):
        text = text+"\n"
    match = QUESTION_RE.search(text)
    while match:
        repl = match.group(1).upper()
        text = text[:match.start(1)] + repl + text[match.end(1):]
        match = QUESTION_RE.search(text)
    return text


def modernise_text(
    text: str,
    phrase_rules: List[Tuple[Pattern[str], str]],
    word_subs: Dict[str, str],
    verb_rules: Dict[str,Tuple[str,str]],
    phrase_counts:List[int],
    word_counts: Dict[str, int],
    verb_counts: Dict[str, int],
) -> Tuple[str, List[int],Dict[str, int],Dict[str, int]]:
    text, phrase_counts, time_p = apply_phrase_rules(text, phrase_rules, phrase_counts)
    text, verb_counts, time_v = apply_verb_rules(text, verb_rules, verb_counts)
    text, word_counts, time_w = apply_word_subs(text, word_subs, word_counts)
    text = cleanup_text(text)
    return [text, phrase_counts, word_counts, verb_counts, [time_p, time_v, time_w]]


def split_preserving_footnotes(line: str) -> List[Tuple[bool, str]]:
    """
    Split a line into segments:
      (True, text)  = footnote segment (skip modernising)
      (False, text) = normal segment (modernise)
    Handles multiple footnotes in one line.
    """
    parts: List[Tuple[bool, str]] = []
    pos = 0

    while True:
        start = line.find(r"\f ", pos)
        if start == -1:
            parts.append((False, line[pos:]))
            break

        if start > pos:
            parts.append((False, line[pos:start]))

        end = line.find(r"\f*", start)
        if end == -1:
            # Unterminated footnote: treat rest of line as footnote
            parts.append((True, line[start:]))
            break

        end += len(r"\f*")
        parts.append((True, line[start:end]))
        pos = end

    return parts


def modernise_usfm_line(
    line: str,
    phrase_rules: List[Tuple[Pattern[str], str]],
    word_subs: Dict[str, str],
    verb_rules: Dict[str,Tuple[str,str]],
    phrase_counts:List[int],
    word_counts: Dict[str, int],
    verb_counts: Dict[str, int],
    skip_footnotes: bool = True,
) -> Tuple[str, List[int],Dict[str, int],Dict[str, int]]:
    if not skip_footnotes:
        return modernise_text(line, phrase_rules, word_subs, verb_rules, phrase_counts, word_counts, verb_counts)

    pieces = split_preserving_footnotes(line)
    out: List[str] = []
    times = [0,0,0]
    
    for is_footnote, chunk in pieces:
        if is_footnote:
            out.append(chunk)
        else:
            text, phrase_counts, word_counts, verb_counts, times = modernise_text(chunk, phrase_rules, word_subs, verb_rules, phrase_counts, word_counts, verb_counts)
            out.append(text)

    return ["".join(out), phrase_counts, word_counts, verb_counts, times]


def write_phrase_counts(review_path: Path, phrase_rules: List[Tuple[Pattern[str], str]], phrase_counts: List[int]) -> None:
    target_file = review_path / "brenton_phrase_counts.csv"
    if target_file.exists():
        old_phrase_counts = []
        with target_file.open(encoding="utf-8") as f:
            reader = csv.reader(f)
            i = -1
            for row in reader:
                if i>=0:
                    old_phrase_counts.append(int(row[2]))
                i += 1
            if len(old_phrase_counts) == len(phrase_counts):
                phrase_counts = [a+b for a,b in zip(phrase_counts, old_phrase_counts)]
    with target_file.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["pattern", "replacement", "count"])
        i = 0;
        for rule in phrase_rules:
            writer.writerow([rule[0], rule[1], phrase_counts[i]])
            i += 1
def write_word_counts(review_path: Path, word_rules: Dict[str, str], word_counts: Dict[str, int]) -> None:
    target_file = review_path / "brenton_word_counts.csv"
    if target_file.exists():
        with target_file.open(encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row["word"].lower() in word_counts:
                    word_counts[row["word"].lower()] += int(row["count"])
                else:
                    word_counts[row["word"].lower()] = int(row["count"])
    with target_file.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["word", "replacement", "count"])
        for rule in sorted(word_rules.keys(), key=len, reverse=True):
            if (rule == rule.lower() or rule.lower() not in word_rules) and rule.lower() in word_counts:
                writer.writerow([rule, word_rules[rule], word_counts[rule.lower()]])
def write_verb_counts(review_path: Path, verb_rules: Dict[str, Tuple[str,str]], verb_counts: Dict[str, int]) -> None:
    target_file = review_path / "brenton_verb_counts.csv"
    if target_file.exists():
        with target_file.open(encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if verb_rules[row["verb"]]:
                    verb_counts[row["verb"]] += int(row["count"])
    with target_file.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["dont", "verb", "replacement", "count"])
        for rule in verb_rules:
            if rule == rule.lower() or rule.lower() not in verb_rules:
                writer.writerow([verb_rules[rule][0], rule, verb_rules[rule][1], verb_counts[rule.lower()]])


def process_file(
    src: Path,
    dst: Path,
    review_path: Path,
    phrase_rules: List[Tuple[Pattern[str], str]],
    word_subs: Dict[str, str],
    verb_rules: Dict[str,Tuple[str,str]],
    skip_footnotes: bool = True,
    show_timing: bool = False
) -> None:
    changed_rows: List[Tuple[int, str, str]] = []
    output_lines: List[str] = []
    phrase_counts: List[int] = [0 for k in phrase_rules]
    word_counts: Dict[str, int] = {k:0 for k in word_subs}
    verb_counts: Dict[str, int] = {k:0 for k in verb_rules}
    time_w=0
    time_v=[0,0,0,0,0]
    time_p=0
    
    with src.open(encoding="utf-8") as f:
        for i, line in enumerate(f, start=1):
            if line.strip().startswith(r"\c"):
                if progress:
                    print(".", end="", flush=True)
            new_line, phrase_counts,word_counts,verb_counts, times = modernise_usfm_line(
                line=line,
                phrase_rules=phrase_rules,
                word_subs=word_subs,
                verb_rules=verb_rules,
                phrase_counts=phrase_counts,
                word_counts=word_counts,
                verb_counts=verb_counts,
                skip_footnotes=skip_footnotes,
            )
            time_p += times[0]
            time_v = [a + b for a, b in zip(time_v, times[1])]
            time_w += times[2]
            output_lines.append(new_line)
#            if new_line.strip() != line.strip():
#                changed_rows.append((i, line.rstrip("\n"), new_line.rstrip("\n")))

    dst.write_text("".join(output_lines), encoding="utf-8")
    if review_path:
        write_phrase_counts(review_path, phrase_rules, phrase_counts)
        write_word_counts(review_path, word_subs, word_counts)
        write_verb_counts(review_path, verb_rules, verb_counts)
    if show_timing:
        print(f"\nProcessing times: phrase {time_p}, verb {time_v}, word {time_w}", end="")


def default_output_name(input_path: Path) -> Path:
    if input_path.suffix:
        return input_path.with_name(input_path.stem + "-modern" + input_path.suffix)
    return input_path.with_name(input_path.name + "-modern")


def default_review_name(output_path: Path) -> Path:
    return output_path.with_suffix(".review.csv")


def main() -> None:
    global quiet
    global progress
    parser = argparse.ArgumentParser(
        description="Modernise archaic English in a USFM file while preserving markers."
    )
    parser.add_argument("input", help="input USFM file")
    parser.add_argument(
        "-o", "--output",
        default=None,
        help="output USFM file (default: input name with -modern added)"
    )
    parser.add_argument(
        "--review",
        default=None,
        help="path to put the counts files for review."
    )
    parser.add_argument(
        "--data-dir",
        default="data",
        help="directory containing TSV rule files (default: data)"
    )
    parser.add_argument(
        "--include-footnotes",
        action="store_true",
        help="also modernise text inside footnotes"
    )
    parser.add_argument(
        "-t", "--show-timing",
        action="store_true"
        )
    parser.add_argument(
        "-q", "--quiet",
        action="store_true"
        )
    parser.add_argument(
        "-p", "--progress",
        action="store_true",
        help = "show progress dots"
        )

    args = parser.parse_args()
    if args.quiet:
        quiet = True
    if args.progress:
        progress = True
    input_path = Path(args.input)
    output_path = Path(args.output) if args.output else default_output_name(input_path)
    review_path = Path(args.review) if args.review else None
    data_dir = Path(args.data_dir)

    word_subs = load_tsv_dict(data_dir / "brenton_word_subs.tsv")
    phrase_rules = load_tsv_rules(data_dir / "brenton_phrase_rules.tsv")
    verb_rules = load_verb_dict(data_dir / "verblist.csv")
    process_file(
        src=input_path,
        dst=output_path,
        review_path=review_path,
        phrase_rules=phrase_rules,
        word_subs=word_subs,
        verb_rules=verb_rules,
        skip_footnotes=not args.include_footnotes,
        show_timing = args.show_timing
    )

    if not quiet:
        print(f"\nWrote modernised USFM: {output_path}")
    elif progress:
        print()

if __name__ == "__main__":
    main()
