import re

_WHITESPACE_RE = re.compile(r"[ \t\f\v]+")
_BLANK_LINES_RE = re.compile(r"\n{3,}")


def clean_text(raw_text: str) -> str:
    """Minimal deterministic cleanup: normalize whitespace, collapse blank lines.
    No LLM involved -- this is the pre-LLM/pre-heuristic normalization step that
    happens regardless of which extraction strategy runs next.
    """
    text = raw_text.replace("\r\n", "\n").replace("\r", "\n")
    lines = [_WHITESPACE_RE.sub(" ", line).strip() for line in text.split("\n")]
    text = "\n".join(lines)
    text = _BLANK_LINES_RE.sub("\n\n", text)
    return text.strip()
