import pytest

from app.services.latex.render import escape_latex
from app.services.latex.safety import UnsafeLatexError, validate_latex_source

SAFE_DOC = r"""
\documentclass{article}
\usepackage{fontspec}
\usepackage{geometry}
\begin{document}
Hello world.
\end{document}
"""


def test_safe_document_passes():
    validate_latex_source(SAFE_DOC)  # must not raise


@pytest.mark.parametrize(
    "dangerous_fragment",
    [
        r"\immediate\write18{rm -rf /}",
        r"\input{/etc/passwd}",
        r"\include{../../secrets}",
        r"\directlua{os.execute('ls')}",
    ],
)
def test_forbidden_constructs_are_rejected(dangerous_fragment):
    with pytest.raises(UnsafeLatexError):
        validate_latex_source(SAFE_DOC + dangerous_fragment)


def test_non_whitelisted_package_is_rejected():
    with pytest.raises(UnsafeLatexError):
        validate_latex_source(SAFE_DOC.replace(r"\usepackage{geometry}", r"\usepackage{shellesc}"))


def test_escape_latex_handles_special_characters():
    assert escape_latex("100% & $5 #1 _test_") == r"100\% \& \$5 \#1 \_test\_"
