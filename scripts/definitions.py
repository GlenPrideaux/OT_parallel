import re

# ----------------------------
# USFM structural regexes
# ----------------------------
C_RE = re.compile(r"^\\c\s+([0-9A-F]+)\s*$")
V_RE = re.compile(r"^\\v\s+(\d+)([a-z]?)\s+(.*)$")
D_RE = re.compile(r"^\\d\s+(.*)$")

# Poetry / paragraph markers (often appear on their own lines)
Q_RE = re.compile(r"^\\q(\d*)\s+(.*)$")   # \q, \q1, \q2 ...
M_RE = re.compile(r"^\\m\s+(.*)$")        # \m ...
P_RE = re.compile(r"^\\p\s+(.*)$")        # \p ...

# ----------------------------
# Footnote extraction (USFM)
# ----------------------------
FOOTNOTE_BLOCK_RE = re.compile(r"\\f\b.*?\\f\*", re.DOTALL)
XREF_BLOCK_RE = re.compile(r"\\x\b.*?\\x\*\s?", re.DOTALL)
FR_RE = re.compile(r"\\fr\b\s*([^ ]+)")
FT_RE = re.compile(r"\\ft\b\s*([^\\]+)")
FL_RE = re.compile(r"\\fl\b\s*(.+?) \\")
FQ_RE = re.compile(r"\\fqa?\b\s*(.+?) \\")
# Some footnotes contain inline “character style” runs like \+wh ... \+wh*
# These contain backslashes and will truncate naive \ft capture unless removed first.
PLUS_MARK_RE = re.compile(r"\\\+[A-Za-z]+[* ]?")  # matches \+wh and \+wh* etc.
X_MARK_RE = re.compile(r"\\x[A-Za-z]+[* ]?")  # matches \x and \xt, \x* etc.

X_BLOCK_RE = re.compile(r"\\x\b.*?\\x\*")
XO_RE = re.compile(r"\\xo\b\s*([^\\]+)")
XT_RE = re.compile(r"\\xt\b\s*([^\\]+)")

# Markers inserted into verse strings so the LaTeX generator can turn them into \footnote{...}
FOOTNOTE_DELIM = "\u241EFOOTNOTE\u241E"  # ␞FOOTNOTE␞ (very unlikely in source)
FOOTNOTE_REPEAT = "\u241EFOOTNOTEREPEAT\u241E"  # ␞FOOTNOTE␞ (very unlikely in source)
XREF_DELIM = "\u241EXREF\u241E"

ADD_OPEN = "\u241EADDOPEN\u241E"
ADD_CLOSE = "\u241EADDCLOSE\u241E"
SC_OPEN = "\u241ESCOPEN\u241E"
SC_CLOSE = "\u241ESCCLOSE\u241E"
SUP_OPEN = "\u241ESUPOPEN\u241E"
SUP_CLOSE = "\u241ESUPCLOSE\u241E"
FL_OPEN = "\u241EFLOPEN\u241E"
FL_CLOSE = "\u241EFLCLOSE\u241E"
FQ_OPEN = "\u241EFQOPEN\u241E"
FQ_CLOSE = "\u241EFQCLOSE\u241E"
FX_OPEN = "\u241EFXOPEN\u241E"
FX_CLOSE = "\u241EFXCLOSE\u241E"
QS_OPEN = "\u241EQSOPEN\u241E"
QS_CLOSE = "\u241EQSCLOSE\u241E"

HEBREW_RE = re.compile(r'[\u0590-\u05FF]+')
GREEK_RE = re.compile(r"[\u0370-\u03FF\u1F00-\u1FFF]+")

STRUCT_DELIM = "\u241E"
STYLE_HDG = f"{STRUCT_DELIM}STYLE:HDG{STRUCT_DELIM}"
STYLE_PARA = f"{STRUCT_DELIM}STYLE:PARA{STRUCT_DELIM}"

RANGE_RE = re.compile(r"^([0-9A-F]+:\d+[a-z]*)\s*-\s*([0-9A-F]+:\d+[a-z]*)$")
REF_RE = re.compile(r'^([0-9A-F]+):(\d+)([a-z]*)$', re.IGNORECASE)

PIPE_ATTR_RE = re.compile(r'\|[A-Za-z]+="[^"]*"')   # |strong="H3068", |lemma="..."
USFM_MARK_RE = re.compile(r'\\[+]?[A-Za-z]+\d*\*?')     # \w, \w*, \add, \add*, etc.
STAR_RE = re.compile(r"\*+")                        # stray * markers (some editions)

W_BLOCK_RE = re.compile(r"\\[+]?w\s([^|]*)\|strong=\"H[0-9]+\"\\[+]?w\*", re.DOTALL)

LRM_UNICODE = "\u200e"
