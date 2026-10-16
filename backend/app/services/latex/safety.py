import re

# Commands that could execute arbitrary code, read/write arbitrary files, or reach
# the network from inside the compiled document. Rejected outright before compiling.
_FORBIDDEN_PATTERNS = [
    re.compile(r"\\write18"),
    re.compile(r"\\immediate\s*\\write18"),
    re.compile(r"\\include\s*\{"),
    re.compile(r"\\openin"),
    re.compile(r"\\openout"),
    re.compile(r"\\directlua"),
    re.compile(r"\\luaexec"),
    re.compile(r"\\catcode"),
    re.compile(r"\\special\s*\{"),
    re.compile(r"\\usepackage\s*\{\s*shellesc\s*\}"),
]

# \input is forbidden everywhere except this one, specific, hardcoded filename
# (loaded by the preamble itself, never from dynamic/user-influenced content):
# glyphtounicode.tex is TeX Live's own ToUnicode-mapping file, needed for
# ATS-parseable text extraction under pdflatex.
_INPUT_RE = re.compile(r"\\input\s*\{([^}]*)\}")
_ALLOWED_INPUT_FILES = {"glyphtounicode"}

ALLOWED_PACKAGES = {
    "fontspec",
    "geometry",
    "hyperref",
    "parskip",
    "polyglossia",
    "xcolor",
    # main.tex template packages (see app/services/latex/render.py)
    "titlesec",
    "tabularx",
    "array",
    "enumitem",
    "fontawesome5",
    "amsmath",
    "eso-pic",
    "calc",
    "bookmark",
    "lastpage",
    "changepage",
    "paracol",
    "ifthen",
    "needspace",
    "iftex",
    "fontenc",
    "inputenc",
    "lmodern",
    "charter",
    "graphicx",
    "tikz",
}

_PACKAGE_RE = re.compile(r"\\usepackage(?:\[[^\]]*\])?\{([^}]+)\}")


class UnsafeLatexError(Exception):
    def __init__(self, reasons: list[str]):
        super().__init__("; ".join(reasons))
        self.reasons = reasons


def validate_latex_source(tex_source: str) -> None:
    """Reject LaTeX source containing shell-escape, arbitrary file I/O, or other
    dangerous constructs, and reject any \\usepackage outside the whitelist.
    Raises UnsafeLatexError; never silently strips content.
    """
    reasons: list[str] = []

    for pattern in _FORBIDDEN_PATTERNS:
        if pattern.search(tex_source):
            reasons.append(f"forbidden construct matched: {pattern.pattern}")

    for match in _INPUT_RE.finditer(tex_source):
        arg = match.group(1).strip()
        if arg not in _ALLOWED_INPUT_FILES:
            reasons.append(f"\\input with disallowed argument: {arg!r}")

    for match in _PACKAGE_RE.finditer(tex_source):
        packages = [p.strip() for p in match.group(1).split(",")]
        for pkg in packages:
            if pkg not in ALLOWED_PACKAGES:
                reasons.append(f"package not in whitelist: {pkg!r}")

    if reasons:
        raise UnsafeLatexError(reasons)
