import csv, argparse, re
from pathlib import Path

from definitions import *

quiet = False

def wrap_greek(text):
    return GREEK_RE.sub(lambda m: r'\textgreek{' + m.group(0) + '}', text)
def wrap_hebrew(text):
    return HEBREW_RE.sub(lambda m: r'\texthebrew{' + m.group(0) + '}', wrap_greek(text))

def inject_latex_footnotes(escaped_text: str) -> str:
    # escaped_text is already LaTeX-escaped
    parts = escaped_text.split(FOOTNOTE_DELIM)
    if len(parts) == 1:
        return escaped_text

    out = [parts[0]]
    # parts alternates: text, footnote, text, footnote, ...
    for i in range(1, len(parts), 2):
        fn = parts[i].strip()
        if fn:
            out.append(r"\footnote{" + fn + "}")
        if i + 1 < len(parts):
            out.append(parts[i + 1])
    return "".join(out)

def esc(s: str) -> str:
    if s is None:
        return ""
    s = s.replace("\\", r"\textbackslash{}")
    s = s.replace("&", r"\&").replace("%", r"\%").replace("$", r"\$")
    s = s.replace("#", r"\#").replace("_", r"\_").replace("{", r"\{").replace("}", r"\}")
    s = s.replace("~", r"\textasciitilde{}").replace("^", r"\textasciicircum{}")
    return s

def render_markers(escaped_text: str) -> str:
    return (escaped_text
            .replace(ADD_OPEN, r"\textit{")
            .replace(ADD_CLOSE, "}")
            .replace(SC_OPEN, r"\textsc{")
            .replace(SC_CLOSE, "}")
            .replace(SUP_OPEN, r"\textsuperscript{")
            .replace(SUP_CLOSE, "}")
            .replace(FL_OPEN, r"\textbf{")
            .replace(FL_CLOSE, "}")
            .replace(FQ_OPEN, r"\textbf{")
            .replace(FQ_CLOSE, "}")
            .replace(QS_OPEN, r"\hfill\textit{")
            .replace(QS_CLOSE, "}")
           )

def render_structured_to_latex(escaped_text: str) -> str:
    if STRUCT_DELIM not in escaped_text:
        return escaped_text

    def render_heading_verse(text: str) -> str:
        # Space above + bold, but still stays in the column (not spanning both)
        return r"\DescriptiveHeading{" + text.strip() + r"}"

    parts = escaped_text.split(STRUCT_DELIM)
    out = []
    i = 0
    pending_heading = False
    PILCROW = r"{\small\textparagraph\thinspace}"
    
    while i < len(parts):
        token = parts[i]

        # Our style marker is a standalone token after splitting
        if token == "STYLE:HDG":
            pending_heading = True
            i += 1
            continue

        if token.startswith("Q:"):
            indent = int(token[2:]) if token[2:].isdigit() else 1
            if i + 1 < len(parts):
                line = parts[i + 1].strip()
                # If you ever tag a poem line as heading, you can decide what to do here.
                out.append(rf"\poemline{{{indent}}}{{{line}}}")
                i += 2
            else:
                i += 1

        elif token == "P":
            if i+2 < len(parts) and parts[i+2] == "STYLE:PARA":
                i += 2
                if len(out):
                    out.append(r"\par" + PILCROW)
                else:
                    out.append(PILCROW)
                
            if i + 1 < len(parts):
                seg = parts[i + 1].strip()

                # Sometimes seg is empty because the verse starts with ␞STYLE:HDG␞
                # In that case, just skip the empty payload.
                if seg:
                    if pending_heading:
                        out.append(render_heading_verse(seg) + " ")
                        pending_heading = False
                    else:
                        out.append(seg + " ")
                i += 2
            else:
                i += 1

        else:
            # Fallback: plain text token
            if token.strip():
                if pending_heading:
                    out.append(render_heading_verse(token) + " ")
                    pending_heading = False
                else:
                    out.append(token.strip() + " ")

            i += 1

    rendered = "".join(out).strip()

    if r"\poemline" in rendered:
        rendered = r"{\raggedright " + rendered + "}"
    return rendered


def parse_ref(ref: str) -> tuple[int, int]:
    # ref like "12:7" (ignore any suffixes if you later add them)
    ch_s, v_s = ref.split(":", 1)
    # if you ever use 7a/7* etc, keep only leading digits for verse
    v_digits = "".join(c for c in v_s if c.isdigit())
    return int(ch_s), int(v_digits) if v_digits else 0

def default_output_name(input_path: Path) -> Path:
    if input_path.suffix:
        return Path("tex/" + input_path.stem + ".tex")
    return Path("tex/" + input_path.name + ".tex")


def main():
    parser = argparse.ArgumentParser(description="Turn a parallel csv file into a corresponding LaTeX file")
    parser.add_argument("input", help="input csv file name")
    parser.add_argument("book", help="Book name")
    
    parser.add_argument(
        "-o", "--output",
        default=None,
        help="output CSV file (default: tex/input_file_name.tex)"
    )

    global quiet
    parser.add_argument(
        "-q", "--quiet",
        action="store_true"
        )
    args = parser.parse_args()
    if args.quiet:
        quiet = True

    rows = []
    INP = Path(args.input)
    OUT = Path(args.output) if args.output else default_output_name(INP)
    with INP.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8") as out:
        out.write(f"\\BookHeading{{{args.book}}}\n")

        current_ch = None
        output_buf = ""
        c_has_thirdcol = False
        for r in rows:
            ch = r["ch"]
            if ch != current_ch:
                if current_ch is not None:
                    if c_has_thirdcol:
                        out.write("\\begin{paracol}{3}\\ColumnHeadings[3]\n")
                    else:
                        out.write("\\begin{paracol}{2}\\ColumnHeadings[2]\n")
                    out.write(output_buf)
                    output_buf = ""
                    c_has_thirdcol = False
                    out.write("\\end{paracol}\n")
                out.write(f"\\ChapterHeading{{{ch}}}\n")
                current_ch = ch

            lxx_ref = esc(r["lxx_ref"])
            mt_ref  = esc(r["mt_ref"])
            lxx_txt = esc(r["lxx_text"])
            mt_txt = esc(r["mt_text"])
            other_ref = r.get("other_ref","")
            if other_ref:
                other_ref = esc(other_ref)
                c_has_thirdcol = True
                other_txt = esc(r["other_text"])
            else:
                other_txt=""
            lxx_txt = render_structured_to_latex(inject_latex_footnotes(render_markers(wrap_hebrew(lxx_txt))))
            mt_txt  = render_structured_to_latex(inject_latex_footnotes(render_markers(wrap_hebrew(mt_txt))))
            if c_has_thirdcol:
                other_txt  = render_structured_to_latex(inject_latex_footnotes(render_markers(wrap_hebrew(other_txt))))
                output_buf += f"\\VerseTriple{{{mt_ref}}}{{{mt_txt}}}{{{lxx_ref}}}{{{lxx_txt}}}{{{other_ref}}}{{{other_txt}}}\n"
            else:
                output_buf += f"\\VersePair{{{mt_ref}}}{{{mt_txt}}}{{{lxx_ref}}}{{{lxx_txt}}}\n"
        if c_has_thirdcol:
            out.write("\\begin{paracol}{3}\\ColumnHeadings[3]\n")
        else:
            out.write("\\begin{paracol}{2}\\ColumnHeadings[2]\n")
        out.write(output_buf)
        out.write("\\end{paracol}\n\n")
    if not quiet:
        print(f"Wrote {OUT}")

if __name__ == "__main__":
    main()
