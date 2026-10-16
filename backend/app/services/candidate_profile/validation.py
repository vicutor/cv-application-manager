import hashlib
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from pydantic import ValidationError

from app.services.candidate_profile.schema import CandidateProfile


@dataclass
class ProfileValidationResult:
    profile: CandidateProfile | None
    errors: list[str] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return self.profile is not None and not self.errors


def content_hash(raw_yaml: str) -> str:
    return hashlib.sha256(raw_yaml.encode("utf-8")).hexdigest()


def collect_fact_ids(profile: CandidateProfile) -> set[str]:
    """All identifiers a skill's evidence_refs is allowed to point at."""
    ids: set[str] = {f.id for f in profile.summary_facts}
    for exp in profile.experience:
        ids.update(r.id for r in exp.responsibilities)
        ids.update(a.id for a in exp.achievements)
    return ids


def _all_declared_ids(profile: CandidateProfile) -> list[str]:
    ids: list[str] = [f.id for f in profile.summary_facts]
    for exp in profile.experience:
        ids.append(exp.id)
        ids.extend(r.id for r in exp.responsibilities)
        ids.extend(a.id for a in exp.achievements)
    ids.extend(s.id for s in profile.skills)
    ids.extend(e.id for e in profile.education)
    ids.extend(c.id for c in profile.certifications)
    ids.extend(p.id for p in profile.projects)
    return ids


def validate_profile(profile: CandidateProfile) -> list[str]:
    errors: list[str] = []

    all_ids = _all_declared_ids(profile)
    seen: set[str] = set()
    for entity_id in all_ids:
        if entity_id in seen:
            errors.append(f"duplicate identifier: {entity_id!r}")
        seen.add(entity_id)

    fact_ids = collect_fact_ids(profile)
    for skill in profile.skills:
        for ref in skill.evidence_refs:
            if ref not in fact_ids:
                errors.append(
                    f"skill {skill.id!r} has evidence_refs entry {ref!r} "
                    "that does not match any responsibility/achievement/summary fact id"
                )

    return errors


def load_and_validate_yaml(path: Path) -> ProfileValidationResult:
    raw = path.read_text(encoding="utf-8")
    try:
        data = yaml.safe_load(raw)
    except yaml.YAMLError as exc:
        return ProfileValidationResult(profile=None, errors=[f"invalid YAML: {exc}"])

    try:
        profile = CandidateProfile.model_validate(data)
    except ValidationError as exc:
        return ProfileValidationResult(profile=None, errors=[str(exc)])

    errors = validate_profile(profile)
    return ProfileValidationResult(profile=profile, errors=errors)
