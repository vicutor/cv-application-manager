import html
import re

_BR_RE = re.compile(r"(?i)<br\s*/?>")
_BLOCK_TAG_RE = re.compile(r"(?i)</?(p|div|li|h[1-6]|tr|blockquote|ul|ol)(?:\s[^>]*)?>")
_TAG_RE = re.compile(r"<[^>]+>")


def html_to_text(raw_html: str) -> str:
    """Convert (possibly embedded) HTML into readable plain text, preserving
    paragraph/list structure instead of collapsing every tag to a single space.
    Job boards commonly embed real HTML in a JSON-LD `description` field (schema.org
    explicitly allows it) -- treating it as already-plain text loses every line
    break, which is what made early extractions read as one run-on paragraph.
    """
    text = _BR_RE.sub("\n", raw_html)
    text = _BLOCK_TAG_RE.sub("\n", text)
    text = _TAG_RE.sub(" ", text)
    return html.unescape(text)
