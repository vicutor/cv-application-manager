"""LaTeX rendering for a cover letter -- a plain, one-page letter, not the CV
template. Shares the CV template's font handling (XCharter under xelatex,
same charter-bold bug workaround) for visual consistency between the two
documents in an application package, but has none of its section/column
machinery -- just a sender block, date, greeting, body paragraphs, and a
sign-off."""

from dataclasses import dataclass, field

from app.services.latex.render import escape_latex

_PREAMBLE = r"""\documentclass[11pt, letterpaper]{article}
\usepackage[top=2.4 cm, bottom=2.4 cm, left=2.4 cm, right=2.4 cm]{geometry}
\usepackage{iftex}
\ifPDFTeX
    \usepackage[T1]{fontenc}
    \usepackage[utf8]{inputenc}
    \usepackage{charter}
\else
    \usepackage{fontspec}
    \setmainfont{XCharter}
\fi
\usepackage[dvipsnames]{xcolor}
\definecolor{primaryColor}{RGB}{0, 0, 0}
\usepackage[colorlinks=true, urlcolor=primaryColor]{hyperref}
\pagestyle{empty}
\setlength{\parindent}{0pt}
\setlength{\parskip}{0.85\baselineskip}
\raggedright
\begin{document}
"""


@dataclass
class CoverLetterLetter:
    full_name: str
    email: str
    phone: str
    location: str
    date_str: str
    greeting: str
    paragraphs: list[str] = field(default_factory=list)
    signoff: str = "Best,"


def render_cover_letter_tex(letter: CoverLetterLetter) -> str:
    parts: list[str] = [_PREAMBLE]

    parts.append(r"{\large\bfseries " + escape_latex(letter.full_name) + r"}\\")
    contact_bits = [b for b in [letter.email, letter.phone, letter.location] if b]
    if contact_bits:
        parts.append(escape_latex(" | ".join(contact_bits)))

    parts.append(r"\vspace{0.9cm}")
    parts.append(escape_latex(letter.date_str))
    parts.append(r"\vspace{0.5cm}")

    parts.append(escape_latex(letter.greeting))
    for paragraph in letter.paragraphs:
        parts.append(escape_latex(paragraph))

    parts.append(escape_latex(letter.signoff) + r"\\")
    parts.append(escape_latex(letter.full_name))

    parts.append(r"\end{document}")
    parts.append("")
    return "\n\n".join(parts)
