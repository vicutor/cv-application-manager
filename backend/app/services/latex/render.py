"""Direct LaTeX source construction for a structured CV.

No template engine (Jinja or otherwise) is used here: this module builds a
complete .tex document by string concatenation from a validated,
already-fact-checked structured CV model. The preamble and section layout
(header/twocolentry/onecolentry/highlights environments, paracol-based date
columns) reproduce the user's own hand-authored main.tex template verbatim,
per their explicit direction -- only the content between environments is
generated dynamically. Compiled with xelatex (see Settings.latex_compiler):
the preamble's \\ifPDFTeX block (fontenc/inputenc/lmodern/glyphtounicode) is a
pdflatex-only Unicode-mapping workaround and is a no-op under xelatex, which
doesn't need it -- xelatex reads the UTF-8 source and font glyphs natively,
so Polish diacritics and ATS-parseable text extraction both work without it.
Both engines were verified to compile this template correctly; xelatex is
kept since it's what's actually been tested end-to-end.
"""

import re
from dataclasses import dataclass, field

_SPECIAL_CHARS = {
    "\\": r"\textbackslash{}",
    "&": r"\&",
    "%": r"\%",
    "$": r"\$",
    "#": r"\#",
    "_": r"\_",
    "{": r"\{",
    "}": r"\}",
    "~": r"\textasciitilde{}",
    "^": r"\textasciicircum{}",
}


def escape_latex(text: str) -> str:
    out = []
    for ch in text:
        out.append(_SPECIAL_CHARS.get(ch, ch))
    return "".join(out)


_NUMBER_PATTERN = r"\d[\d,]*(?:\.\d+)?\+?%?"


def _build_bold_keyword_regex(keywords: list[str]) -> re.Pattern:
    """Longer keywords first, so e.g. "Kubernetes (GKE)" style multi-word
    terms don't get pre-empted by a shorter substring match first."""
    escaped = [re.escape(k) for k in sorted(set(k for k in keywords if k), key=len, reverse=True)]
    alternation = "|".join(escaped + [_NUMBER_PATTERN]) if escaped else _NUMBER_PATTERN
    # Boundaries exclude only alnum chars (not "/", "-", "(", etc.) so adjacent
    # terms like "GCP/GKE" each match individually, matching how the user's
    # own hand-authored CV bolds them.
    return re.compile(rf"(?<![A-Za-z0-9])(?:{alternation})(?![A-Za-z0-9])", re.IGNORECASE)


def bold_keywords(text: str, keywords: list[str]) -> str:
    """Wraps technology-name and numeric-metric substrings in \\textbf{},
    matching the visual emphasis style of the user's own hand-authored CV
    template. Operates on already fact-checked text -- this only adds bold
    markup around existing substrings verbatim; it never changes, adds, or
    removes a word, so it can't introduce a new claim."""
    if not text:
        return ""
    regex = _build_bold_keyword_regex(keywords)
    out = []
    last_end = 0
    for m in regex.finditer(text):
        if m.start() < last_end:
            continue
        out.append(escape_latex(text[last_end : m.start()]))
        out.append(r"\textbf{" + escape_latex(m.group(0)) + "}")
        last_end = m.end()
    out.append(escape_latex(text[last_end:]))
    return "".join(out)


@dataclass
class CvBullet:
    text: str
    source_fact_ids: list[str] = field(default_factory=list)
    # Metadata from the drafting stage (Etap C). Unused by rendering itself --
    # kept on the bullet so the structured_cv.json artifact preserves them for
    # the fact-check/ATS stages and for debugging.
    matched_requirement_ids: list[str] = field(default_factory=list)
    priority: int = 0
    keywords: list[str] = field(default_factory=list)
    has_metric: bool = False


@dataclass
class CvExperienceEntry:
    company: str
    position: str
    date_range: str
    location: str
    bullets: list[CvBullet] = field(default_factory=list)


@dataclass
class CvSkillGroup:
    name: str
    items: list[str] = field(default_factory=list)


@dataclass
class CvProjectEntry:
    name: str
    bullets: list[str] = field(default_factory=list)
    url: str = ""


@dataclass
class CvCertificationEntry:
    name: str
    issuer: str = ""


@dataclass
class CvEducationEntry:
    institution: str
    degree: str
    date_range: str = ""


@dataclass
class CvLanguageEntry:
    name: str
    level: str = ""


@dataclass
class StructuredCv:
    full_name: str
    headline: str
    location: str
    email: str
    phone: str
    links: dict[str, str]
    summary: str
    experience: list[CvExperienceEntry]
    skills: list[CvSkillGroup]
    language: str = "en"
    certification_tagline: str = ""
    focus_tagline: str = ""
    photo_path: str = ""
    projects: list[CvProjectEntry] = field(default_factory=list)
    certifications: list[CvCertificationEntry] = field(default_factory=list)
    education: list[CvEducationEntry] = field(default_factory=list)
    languages: list[CvLanguageEntry] = field(default_factory=list)


_CONSENT_FOOTER = (
    "By submitting this CV, I consent to the processing of my personal data "
    "for recruitment purposes in accordance with applicable data protection laws."
)

# Verbatim from the user's main.tex, except pdftitle/pdfauthor which are
# filled in dynamically below. Every custom environment (header, onecolentry,
# twocolentry, highlights) and macro is reproduced exactly as authored.
_PREAMBLE_TOP = r"""\documentclass[10pt, letterpaper]{article}

% Packages:
\usepackage[
    ignoreheadfoot,
    top=1.2 cm,
    bottom=1.2 cm,
    left=1.8 cm,
    right=1.8 cm,
    footskip=0.6 cm,
]{geometry}
\usepackage{titlesec}
\usepackage{tabularx}
\usepackage{array}
\usepackage[dvipsnames]{xcolor}
\definecolor{primaryColor}{RGB}{0, 0, 0}
\usepackage{enumitem}
\usepackage{fontawesome5}
\usepackage{amsmath}
"""

_PREAMBLE_HYPERSETUP = r"""\usepackage[
    pdftitle={%s},
    pdfauthor={%s},
    pdfcreator={LaTeX},
    colorlinks=true,
    urlcolor=primaryColor
]{hyperref}
"""

_PREAMBLE_BOTTOM = r"""\usepackage[pscoord]{eso-pic}
\usepackage{calc}
\usepackage{bookmark}
\usepackage{lastpage}
\usepackage{changepage}
\usepackage{paracol}
\usepackage{ifthen}
\usepackage{needspace}
\usepackage{iftex}

\ifPDFTeX
    \input{glyphtounicode}
    \pdfgentounicode=1
    \usepackage[T1]{fontenc}
    \usepackage[utf8]{inputenc}
    \usepackage{lmodern}
    \usepackage{charter}
\else
    % The classic `charter` package is NFSS/T1-only and silently drops its
    % bold shape under XeLaTeX/LuaTeX's Unicode (TU) font encoding --
    % \textbf{} compiles with no error but renders as regular weight (caught
    % by comparing a generated PDF's bullets against the hand-authored
    % original, where bolded tech names/numbers are the whole point). XCharter
    % is the OpenType counterpart of the same typeface, built for fontspec,
    % with working bold/italic under Unicode-aware engines.
    \usepackage{fontspec}
    \setmainfont{XCharter}
\fi

\raggedright
\AtBeginEnvironment{adjustwidth}{\partopsep0pt}
\pagestyle{empty}
\setcounter{secnumdepth}{0}
\setlength{\parindent}{0pt}
\setlength{\topskip}{0pt}
\setlength{\columnsep}{0.15cm}
\pagenumbering{gobble}

\titleformat{\section}{\needspace{4\baselineskip}\bfseries\large}{}{0pt}{}[\vspace{1pt}\titlerule]

\titlespacing{\section}{-1pt}{0.14 cm}{0.08 cm}

\renewcommand\labelitemi{$\vcenter{\hbox{\small$\bullet$}}$}
\newenvironment{highlights}{
    \begin{itemize}[
        topsep=0.03 cm,
        parsep=0.03 cm,
        partopsep=0pt,
        itemsep=0pt,
        leftmargin=0 cm + 10pt
    ]
    \setlength{\baselineskip}{1.0\baselineskip}
}{
    \end{itemize}
}

\newenvironment{onecolentry}{
    \begin{adjustwidth}{
        0 cm + 0.00001 cm
    }{
        0 cm + 0.00001 cm
    }
}{
    \end{adjustwidth}
}

\newenvironment{twocolentry}[2][]{
    \onecolentry
    \def\secondColumn{#2}
    \setcolumnwidth{\fill, 4.5 cm}
    \begin{paracol}{2}
}{
    \switchcolumn \raggedleft \secondColumn
    \end{paracol}
    \endonecolentry
}

\newenvironment{header}{
    \setlength{\topsep}{0pt}\par\kern\topsep\centering\linespread{1.5}
}{
    \par\kern\topsep
}

\usepackage{graphicx}
\usepackage{tikz}

\begin{document}

\newcommand{\AND}{\unskip
    \cleaders\copy\ANDbox\hskip\wd\ANDbox
    \ignorespaces
}
\newsavebox\ANDbox
\sbox\ANDbox{$|$}
"""


def _header_block(cv: StructuredCv) -> str:
    contact_lines = []
    if cv.email:
        contact_lines.append(r"\href{mailto:" + cv.email + "}{" + escape_latex(cv.email) + "} \\\\")
    if cv.phone:
        tel = "".join(ch for ch in cv.phone if ch.isdigit() or ch == "+")
        contact_lines.append(r"\href{tel:" + tel + "}{" + escape_latex(cv.phone) + "} \\\\")
    for label, url in cv.links.items():
        contact_lines.append(r"\href{" + url + "}{" + escape_latex(url.split("//")[-1]) + "}")
    if cv.location:
        contact_lines.append(r"\newline " + escape_latex(cv.location))
    contact_block = "\n            \\vspace{0.05cm}\n            ".join(contact_lines)

    identity_lines = [
        r"{\fontsize{21 pt}{21 pt}\selectfont \textbf{" + escape_latex(cv.full_name) + r"}} \\[0.16cm]",
        r"{\fontsize{11 pt}{11 pt}\selectfont " + escape_latex(cv.headline) + r"} \\[0.10cm]",
    ]
    if cv.certification_tagline:
        identity_lines.append(
            r"{\fontsize{10 pt}{10 pt}\selectfont " + escape_latex(cv.certification_tagline) + r"} \\[0.12cm]"
        )
    if cv.focus_tagline:
        identity_lines.append(
            r"{\fontsize{10 pt}{10 pt}\selectfont " + escape_latex(cv.focus_tagline) + r"} \\[0.14cm]"
        )
    identity_block = "\n            ".join(identity_lines)

    if cv.photo_path:
        return (
            r"""\begin{header}
    \begin{tabularx}{\textwidth}{Xc}
        \begin{minipage}[t]{0.72\textwidth}
            \raggedright
            \vspace{-2.6cm}
            """
            + identity_block
            + "\n\n            "
            + contact_block
            + r"""
        \end{minipage}
        &
        \begin{minipage}[t]{0.28\textwidth}
            \centering
            \begin{tikzpicture}
                \clip (0,0) circle (1.45cm);
                \node at (0,0) {\includegraphics[width=4.4cm,height=4.4cm,keepaspectratio]{"""
            + cv.photo_path
            + r"""}};
            \end{tikzpicture}
        \end{minipage}
    \end{tabularx}
\end{header}
"""
        )

    return (
        r"""\begin{header}
    """
        + identity_block
        + "\n\n    "
        + contact_block
        + r"""
\end{header}
"""
    )


def _experience_section(cv: StructuredCv, keywords: list[str]) -> list[str]:
    if not cv.experience:
        return []
    lines = [r"\section{Experience}"]
    for i, entry in enumerate(cv.experience):
        if i > 0:
            lines.append(r"\vspace{0.08 cm}")
        lines.append(r"\begin{twocolentry}{" + escape_latex(entry.date_range) + "}")
        position_line = r"\textbf{" + escape_latex(entry.position) + r"}, " + escape_latex(entry.company)
        if entry.location:
            position_line += ", " + escape_latex(entry.location)
        lines.append(position_line)
        lines.append(r"\end{twocolentry}")
        if entry.bullets:
            lines.append(r"\vspace{0.04 cm}")
            lines.append(r"\begin{onecolentry}")
            lines.append(r"\begin{highlights}")
            for bullet in entry.bullets:
                lines.append(r"\item " + bold_keywords(bullet.text, keywords))
            lines.append(r"\end{highlights}")
            lines.append(r"\end{onecolentry}")
    return lines


def _skills_section(cv: StructuredCv) -> list[str]:
    if not cv.skills and not cv.languages:
        return []
    lines = [r"\section{Skills \& Technologies}", r"\vspace{0.05 cm}"]
    for group in cv.skills:
        if not group.items:
            continue
        items = ", ".join(escape_latex(i) for i in group.items)
        lines.append(r"\textbf{" + escape_latex(group.name) + r"}: " + items + r" \\")
        lines.append(r"\vspace{0.05 cm}")
    if cv.languages:
        parts = []
        for lang in cv.languages:
            if lang.level:
                parts.append(f"{escape_latex(lang.name)} {escape_latex(lang.level)}")
            else:
                parts.append(escape_latex(lang.name))
        lines.append(r"\begin{onecolentry}")
        lines.append(r"\textbf{Languages:} " + ", ".join(parts))
        lines.append(r"\end{onecolentry}")
    return lines


def _projects_section(cv: StructuredCv, keywords: list[str]) -> list[str]:
    if not cv.projects:
        return []
    lines = [r"\section{Projects}"]
    for i, project in enumerate(cv.projects):
        if i > 0:
            lines.append(r"\vspace{0.08 cm}")
        header_arg = (r"\href{" + project.url + "}{" + escape_latex(project.url) + "}") if project.url else ""
        lines.append(r"\begin{twocolentry}{" + header_arg + "}")
        lines.append(r"\textbf{" + escape_latex(project.name) + "}")
        lines.append(r"\end{twocolentry}")
        if project.bullets:
            lines.append(r"\vspace{0.04 cm}")
            lines.append(r"\begin{onecolentry}")
            lines.append(r"\begin{highlights}")
            for text in project.bullets:
                lines.append(r"\item " + bold_keywords(text, keywords))
            lines.append(r"\end{highlights}")
            lines.append(r"\end{onecolentry}")
    return lines


def _certifications_section(cv: StructuredCv) -> list[str]:
    if not cv.certifications:
        return []
    lines = [r"\section{Certification}", r"\vspace{0.08 cm}"]
    for cert in cv.certifications:
        text = escape_latex(cert.name)
        if cert.issuer:
            text += " -- " + escape_latex(cert.issuer)
        lines.append(r"\begin{onecolentry}")
        lines.append(text)
        lines.append(r"\end{onecolentry}")
        lines.append(r"\vspace{0.04 cm}")
    return lines


def _education_section(cv: StructuredCv) -> list[str]:
    if not cv.education:
        return []
    lines = [r"\section{Education}"]
    for i, edu in enumerate(cv.education):
        if i > 0:
            lines.append(r"\vspace{0.08 cm}")
        lines.append(r"\begin{samepage}")
        lines.append(r"\begin{twocolentry}{" + escape_latex(edu.date_range) + "}")
        lines.append(r"\textbf{" + escape_latex(edu.institution) + "}")
        lines.append(r"\end{twocolentry}")
        lines.append(r"\vspace{0.04 cm}")
        lines.append(r"\begin{onecolentry}")
        lines.append(escape_latex(edu.degree))
        lines.append(r"\vspace{0.04 cm}")
        lines.append(r"\end{onecolentry}")
        lines.append(r"\end{samepage}")
    return lines


def render_cv_tex(cv: StructuredCv) -> str:
    """Builds a complete, compilable pdflatex document matching the user's
    main.tex template structure and style exactly."""
    pdf_title = escape_latex(f"{cv.full_name} CV")
    pdf_author = escape_latex(cv.full_name)
    # Technology/skill names double as the bold-keyword vocabulary for
    # summary/experience/project text, matching how the user's own
    # hand-authored CV bolds tech names and numbers inline.
    keywords = [name for group in cv.skills for name in group.items]

    parts: list[str] = [_PREAMBLE_TOP, _PREAMBLE_HYPERSETUP % (pdf_title, pdf_author), _PREAMBLE_BOTTOM]
    parts.append(_header_block(cv))
    parts.append(r"\vspace{0.08 cm}")

    if cv.summary:
        parts.append(r"\section{Summary}")
        parts.append(r"\begin{onecolentry}")
        parts.append(bold_keywords(cv.summary, keywords))
        parts.append(r"\end{onecolentry}")

    parts.extend(_skills_section(cv))
    parts.extend(_experience_section(cv, keywords))
    parts.extend(_projects_section(cv, keywords))
    parts.extend(_certifications_section(cv))
    parts.extend(_education_section(cv))

    parts.append(r"\vspace{0.08 cm}")
    parts.append(r"\begin{samepage}")
    parts.append(_CONSENT_FOOTER)
    parts.append(r"\end{samepage}")
    parts.append(r"\end{document}")
    parts.append("")
    return "\n".join(parts)
