import re
from dataclasses import asdict, dataclass, field

_WORD_RE = re.compile(r"[a-z0-9+.#]+")


def _tokenize(text: str) -> set[str]:
    return set(_WORD_RE.findall(text.lower()))


@dataclass
class AtsReport:
    score: float
    matched_keywords: list[str] = field(default_factory=list)
    missing_keywords: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def run_ats_audit(job_technologies: list[str], cv_skill_names: list[str], cv_text: str) -> AtsReport:
    """Coverage of job-listed technologies against what the CV actually states.
    Deliberately does not add keywords beyond what the candidate profile already
    supports -- this only measures coverage, it never injects unverified terms.
    """
    if not job_technologies:
        return AtsReport(score=1.0, matched_keywords=[], missing_keywords=[])

    cv_tokens = _tokenize(" ".join(cv_skill_names) + " " + cv_text)
    matched = [tech for tech in job_technologies if _tokenize(tech) <= cv_tokens]
    missing = [tech for tech in job_technologies if tech not in matched]
    score = len(matched) / len(job_technologies)
    return AtsReport(score=round(score, 2), matched_keywords=matched, missing_keywords=missing)
