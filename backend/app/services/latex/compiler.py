import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass
class CompileResult:
    success: bool
    pdf_path: Path | None
    log: str
    page_count: int | None
    has_selectable_text: bool


class LatexCompileError(Exception):
    def __init__(self, log: str):
        super().__init__("LaTeX compilation failed")
        self.log = log


def _run(cmd: list[str], cwd: Path, timeout: int) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd,
        cwd=cwd,
        timeout=timeout,
        capture_output=True,
        text=True,
        env={"PATH": "/Library/TeX/texbin:/usr/bin:/bin:/usr/local/bin"},
    )


def compile_latex(
    tex_source: str,
    work_dir: Path,
    compiler: str = "xelatex",
    timeout_seconds: int = 60,
    max_pages: int = 2,
) -> CompileResult:
    """Compile a validated .tex source to PDF in an isolated working directory.

    - no shell-escape (-no-shell-escape)
    - nonstopmode + halt-on-error so a bad document fails fast rather than hanging
      on an interactive prompt
    - timeout enforced by subprocess, not by the compiler itself
    - work_dir must be a directory dedicated to this single compile attempt; nothing
      outside it is touched
    """
    work_dir.mkdir(parents=True, exist_ok=True)
    tex_path = work_dir / "cv.tex"
    tex_path.write_text(tex_source, encoding="utf-8")

    if shutil.which(compiler, path="/Library/TeX/texbin:/usr/bin:/bin:/usr/local/bin") is None:
        raise FileNotFoundError(
            f"{compiler} not found on PATH. Install a LaTeX distribution providing it "
            "(e.g. `brew install --cask basictex`)."
        )

    combined_log = ""
    try:
        for _pass in range(2):  # run twice: LaTeX needs a second pass for refs/toc if any
            proc = _run(
                [
                    compiler,
                    "-interaction=nonstopmode",
                    "-halt-on-error",
                    "-no-shell-escape",
                    "cv.tex",
                ],
                cwd=work_dir,
                timeout=timeout_seconds,
            )
            combined_log += proc.stdout + proc.stderr
    except subprocess.TimeoutExpired as exc:
        combined_log += f"\ncompilation timed out after {timeout_seconds}s"
        return CompileResult(
            success=False, pdf_path=None, log=combined_log, page_count=None, has_selectable_text=False
        )

    pdf_path = work_dir / "cv.pdf"
    if proc.returncode != 0 or not pdf_path.exists():
        return CompileResult(
            success=False, pdf_path=None, log=combined_log, page_count=None, has_selectable_text=False
        )

    page_count = _pdf_page_count(pdf_path)
    has_text = _pdf_has_selectable_text(pdf_path)

    success = page_count is not None and page_count <= max_pages and has_text
    return CompileResult(
        success=success,
        pdf_path=pdf_path if success else None,
        log=combined_log,
        page_count=page_count,
        has_selectable_text=has_text,
    )


def _pdf_page_count(pdf_path: Path) -> int | None:
    try:
        proc = subprocess.run(
            ["pdfinfo", str(pdf_path)],
            capture_output=True,
            text=True,
            timeout=15,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
    for line in proc.stdout.splitlines():
        if line.startswith("Pages:"):
            try:
                return int(line.split(":", 1)[1].strip())
            except ValueError:
                return None
    return None


def _pdf_has_selectable_text(pdf_path: Path) -> bool:
    try:
        proc = subprocess.run(
            ["pdftotext", str(pdf_path), "-"],
            capture_output=True,
            text=True,
            timeout=15,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False
    return len(proc.stdout.strip()) > 0
