from app.services.candidate_profile.schema import CandidateProfile
from app.services.latex.render import CvSkillGroup


def group_skills_by_category(profile: CandidateProfile) -> list[CvSkillGroup]:
    """Groups profile skills into named CvSkillGroups by their `category`
    field, preserving first-seen category order and skill order within each
    category. Skills are always shown in full, comprehensively -- the CV
    should show off the full breadth of experience, not a model-curated
    subset (unlike bullets, which are selected/prioritized for space).
    Skills without a category (older profiles, e.g. the fixture) fall into a
    single "Skills" group so nothing is lost.
    """
    groups: dict[str, list[str]] = {}
    order: list[str] = []
    for skill in profile.skills:
        label = skill.category or "Skills"
        if label not in groups:
            groups[label] = []
            order.append(label)
        groups[label].append(skill.name)
    return [CvSkillGroup(name=label, items=groups[label]) for label in order]
