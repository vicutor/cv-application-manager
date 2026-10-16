from app.services.latex.render import bold_keywords


def test_bolds_matching_skill_names():
    text = "Operated a Kubernetes platform on GCP using Terraform."
    result = bold_keywords(text, ["Kubernetes", "GCP", "Terraform"])
    assert r"\textbf{Kubernetes}" in result
    assert r"\textbf{GCP}" in result
    assert r"\textbf{Terraform}" in result


def test_bolds_numbers_and_percentages():
    text = "Reduced deployment time by 40% across 18 microservices."
    result = bold_keywords(text, [])
    assert r"\textbf{40\%}" in result
    assert r"\textbf{18}" in result


def test_adjacent_slash_separated_terms_both_bolded():
    text = "Built GCP/GKE infrastructure from scratch."
    result = bold_keywords(text, ["GCP", "GKE"])
    assert r"\textbf{GCP}" in result
    assert r"\textbf{GKE}" in result
    # the slash itself stays outside the bold spans
    assert r"\textbf{GCP}/\textbf{GKE}" in result


def test_does_not_bold_substring_inside_a_longer_word():
    text = "Worked at Gogcpland on unrelated things."
    result = bold_keywords(text, ["GCP"])
    assert r"\textbf" not in result


def test_output_is_latex_escaped():
    text = "Handled 50% cost & risk reduction using C++."
    result = bold_keywords(text, [])
    assert r"\%" in result
    assert r"\&" in result
    assert "C++" in result  # + has no special meaning, left as-is


def test_empty_text_returns_empty_string():
    assert bold_keywords("", ["GCP"]) == ""


def test_no_keywords_and_no_numbers_leaves_text_unbolded_but_escaped():
    text = "Led cross-team collaboration on secure delivery."
    result = bold_keywords(text, ["GCP", "Terraform"])
    assert r"\textbf" not in result
    assert result == text  # no special chars to escape either
