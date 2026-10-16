from app.services.extraction.html_to_text import html_to_text
from app.services.extraction.text_cleaning import clean_text


def test_paragraphs_become_blank_line_separated():
    raw = "<p>First paragraph.</p><p>Second paragraph.</p>"
    result = clean_text(html_to_text(raw))
    assert result == "First paragraph.\n\nSecond paragraph."


def test_br_becomes_newline():
    raw = "Line one<br>Line two<br/>Line three"
    result = clean_text(html_to_text(raw))
    assert result == "Line one\nLine two\nLine three"


def test_list_items_become_lines():
    raw = "<ul><li>Python</li><li>Kubernetes</li></ul>"
    result = clean_text(html_to_text(raw))
    assert "Python" in result.splitlines()
    assert "Kubernetes" in result.splitlines()


def test_inline_tags_collapse_to_space_not_disappear():
    raw = "Requires <strong>Python</strong>and<strong>Terraform</strong>."
    result = clean_text(html_to_text(raw))
    assert "Python" in result
    assert "Terraform" in result
    assert "Pythonand" not in result  # tag removal must not glue words together


def test_html_entities_are_unescaped():
    raw = "Salary &amp; benefits included &ndash; apply now"
    result = html_to_text(raw)
    assert "&amp;" not in result
    assert "&" in result
