from dataclasses import asdict, dataclass, field

from app.services.latex.render import CvExperienceEntry


@dataclass
class FactCheckIssue:
    bullet_text: str
    unknown_fact_ids: list[str]


@dataclass
class FactCheckReport:
    passed: bool
    checked_bullets: int
    issues: list[FactCheckIssue] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def run_fact_check(experience: list[CvExperienceEntry], known_fact_ids: set[str]) -> FactCheckReport:
    """Every bullet must cite fact ids that actually exist in the candidate profile.
    This is the enforcement of the spec's "no invented claims" rule -- even in the
    mock pipeline, content is built directly from profile facts, so this should
    always pass by construction; it exists as a real guard, not a formality.
    """
    issues: list[FactCheckIssue] = []
    checked = 0
    for entry in experience:
        for bullet in entry.bullets:
            checked += 1
            unknown = [fid for fid in bullet.source_fact_ids if fid not in known_fact_ids]
            if unknown:
                issues.append(FactCheckIssue(bullet_text=bullet.text, unknown_fact_ids=unknown))
    return FactCheckReport(passed=not issues, checked_bullets=checked, issues=issues)
