"""Offline tests for the page-fit trim loop's bullet-cutting logic. The real
case that motivated this: a rich profile drafted 2.5x the target page count,
and removing one bullet per retry (the old behavior) never converged within
the attempt budget. These tests verify the proportional cut actually removes
enough bullets to plausibly converge in a handful of retries.
"""

from app.services.cv_generation.pipeline import _bullets_to_trim_for_overflow, _trim_lowest_priority_bullets
from app.services.latex.render import CvBullet, CvExperienceEntry, StructuredCv


def _structured_with_bullet_counts(counts: list[int]) -> StructuredCv:
    entries = []
    for i, n in enumerate(counts):
        bullets = [
            CvBullet(text=f"entry{i} bullet{j}", source_fact_ids=[f"fact_{i}_{j}"], priority=j + 1)
            for j in range(n)
        ]
        entries.append(
            CvExperienceEntry(
                company=f"Company{i}", position="Role", date_range="2020 - present", location="", bullets=bullets
            )
        )
    return StructuredCv(
        full_name="Test Person", headline="Engineer", location="", email="", phone="",
        links={}, summary="Summary.", experience=entries, skills=[], language="en",
    )


def test_no_trim_needed_when_within_target():
    structured = _structured_with_bullet_counts([5])
    assert _bullets_to_trim_for_overflow(structured, current_pages=2, target_pages=2) == 0
    assert _bullets_to_trim_for_overflow(structured, current_pages=1, target_pages=2) == 0


def test_no_trim_when_no_bullets_exist():
    structured = _structured_with_bullet_counts([0, 0])
    assert _bullets_to_trim_for_overflow(structured, current_pages=5, target_pages=2) == 0


def test_severe_overflow_cuts_a_large_fraction_not_just_one():
    """The real-world case: 5 pages against a 2-page target with ~30 bullets
    drafted. Removing 1 bullet per retry would need dozens of attempts --
    this must cut a meaningful chunk in a single round."""
    structured = _structured_with_bullet_counts([12, 8, 6, 4])  # 30 bullets total
    cut = _bullets_to_trim_for_overflow(structured, current_pages=5, target_pages=2)
    # overflow_ratio = (5-2)/5 = 0.6; 30 * 0.6 * 1.3 = 23.4 -> 23
    assert cut == 23


def test_mild_overflow_cuts_proportionally_less():
    structured = _structured_with_bullet_counts([10])
    cut = _bullets_to_trim_for_overflow(structured, current_pages=3, target_pages=2)
    # overflow_ratio = (3-2)/3 = 0.333; 10 * 0.333 * 1.3 ~= 4.33 -> 4
    assert cut == 4


def test_cut_count_never_exceeds_total_bullets():
    structured = _structured_with_bullet_counts([2])
    cut = _bullets_to_trim_for_overflow(structured, current_pages=20, target_pages=1)
    assert cut == 2


def test_trim_removes_highest_priority_number_first():
    structured = _structured_with_bullet_counts([3])  # priorities 1, 2, 3
    removed = _trim_lowest_priority_bullets(structured, count=1)
    assert removed == 1
    remaining = [b.priority for b in structured.experience[0].bullets]
    assert remaining == [1, 2]  # priority 3 (least important) was cut


def test_trim_across_multiple_entries_picks_globally_worst():
    structured = _structured_with_bullet_counts([2, 2])
    # entry 0: priorities 1, 2 -- entry 1: priorities 1, 2
    removed = _trim_lowest_priority_bullets(structured, count=3)
    assert removed == 3
    total_remaining = sum(len(e.bullets) for e in structured.experience)
    assert total_remaining == 1


def test_trim_requesting_more_than_available_stops_gracefully():
    structured = _structured_with_bullet_counts([2])
    removed = _trim_lowest_priority_bullets(structured, count=10)
    assert removed == 2
    assert sum(len(e.bullets) for e in structured.experience) == 0


def test_full_convergence_within_a_few_rounds_for_severe_overflow():
    """Simulates the retry loop's page-estimation-free convergence: assume
    pages scale roughly with bullet count, and check the proportional cut
    reaches at-or-below the target bullet count within the real attempt
    budget (5 retries)."""
    structured = _structured_with_bullet_counts([12, 8, 6, 4])  # 30 bullets, "5 pages"
    target_bullet_count = 12  # roughly what 2 pages holds for this bullet density
    pages_per_bullet = 5 / 30
    current_pages = 5.0

    for _ in range(5):
        total = sum(len(e.bullets) for e in structured.experience)
        if total <= target_bullet_count:
            break
        cut = _bullets_to_trim_for_overflow(structured, round(current_pages), target_pages=2)
        _trim_lowest_priority_bullets(structured, cut)
        current_pages = sum(len(e.bullets) for e in structured.experience) * pages_per_bullet

    assert sum(len(e.bullets) for e in structured.experience) <= target_bullet_count
