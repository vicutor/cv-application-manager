"""Etap A/B persistence tests. These do NOT call the real Claude API -- they
exercise the persistence/validation logic that sits between the LLM response and
the database, using hand-built response objects. The one thing this system must
never do is write a fabricated fact id into the database, so that's the behavior
under test here.
"""

from app.models.job_analysis import JobAnalysis
from app.schemas.job import JobImportTextRequest
from app.services.cv_generation.analysis import (
    JobAnalysisResult,
    all_requirements,
    assign_requirement_ids,
    persist_job_analysis,
)
from app.services.cv_generation.evidence_matching import (
    EvidenceMatchItem,
    EvidenceMatchResult,
    persist_evidence_matches,
)
from app.services.ingestion.text_import import import_from_text

SAMPLE_ANALYSIS = JobAnalysisResult(
    must_have=["Python", "PostgreSQL"],
    nice_to_have=["Kubernetes"],
    responsibilities=["Ship backend services"],
    ats_keywords=["Python", "PostgreSQL", "Kubernetes"],
    domain_signals=["fintech"],
    seniority_signals=["Senior"],
    screening_risks=["EU work authorization required"],
)


def _make_job(db_session):
    outcome = import_from_text(
        db_session,
        JobImportTextRequest(
            company_name="Test Co",
            position_title="Backend Engineer",
            raw_text="A" * 30,
            allow_duplicate=True,
        ),
    )
    return outcome.job_posting


def test_assign_requirement_ids_is_deterministic_and_stable():
    must_have, nice_to_have = assign_requirement_ids(SAMPLE_ANALYSIS)
    assert must_have == [
        {"id": "must_1", "text": "Python"},
        {"id": "must_2", "text": "PostgreSQL"},
    ]
    assert nice_to_have == [{"id": "nice_1", "text": "Kubernetes"}]


def test_persist_job_analysis_maps_all_fields(db_session, settings):
    job = _make_job(db_session)
    row = persist_job_analysis(db_session, job, SAMPLE_ANALYSIS, settings)

    assert row.job_posting_id == job.id
    assert row.must_have == [
        {"id": "must_1", "text": "Python"},
        {"id": "must_2", "text": "PostgreSQL"},
    ]
    assert row.nice_to_have == [{"id": "nice_1", "text": "Kubernetes"}]
    assert row.responsibilities == ["Ship backend services"]
    assert row.ats_keywords == ["Python", "PostgreSQL", "Kubernetes"]
    assert row.domain_signals == ["fintech"]
    assert row.seniority_signals == ["Senior"]
    assert row.screening_risks == ["EU work authorization required"]
    assert row.model_provider == "anthropic"
    assert row.prompt_version == "analysis-v1"

    reqs = all_requirements(row)
    assert reqs == [
        {"id": "must_1", "text": "Python"},
        {"id": "must_2", "text": "PostgreSQL"},
        {"id": "nice_1", "text": "Kubernetes"},
    ]


def test_persist_evidence_matches_drops_hallucinated_fact_ids(db_session, settings):
    job = _make_job(db_session)
    job_analysis = JobAnalysis(job_posting_id=job.id, must_have=[], nice_to_have=[])
    db_session.add(job_analysis)
    db_session.commit()
    db_session.refresh(job_analysis)

    known_fact_ids = {"real_fact_1", "real_fact_2"}

    result = EvidenceMatchResult(
        matches=[
            EvidenceMatchItem(
                requirement_id="must_1",
                candidate_fact_ids=["real_fact_1", "made_up_fact_id"],
                match_type="direct",
                confidence=0.9,
                reason="Directly matches.",
                must_not_claim=False,
            ),
            EvidenceMatchItem(
                requirement_id="must_2",
                candidate_fact_ids=["completely_fake_id"],
                match_type="direct",
                confidence=0.95,
                reason="Model claims a strong match, but the id doesn't exist.",
                must_not_claim=False,
            ),
            EvidenceMatchItem(
                requirement_id="must_3",
                candidate_fact_ids=[],
                match_type="none",
                confidence=0.0,
                reason="No evidence.",
                must_not_claim=True,
            ),
        ]
    )

    rows = persist_evidence_matches(db_session, job_analysis, result, known_fact_ids)
    by_requirement = {}
    for row in rows:
        by_requirement.setdefault(row.requirement_id, []).append(row)

    # must_1: the real id survives as its own row; the fake id is silently dropped,
    # never written to candidate_fact_id.
    must_1_rows = by_requirement["must_1"]
    assert len(must_1_rows) == 1
    assert must_1_rows[0].candidate_fact_id == "real_fact_1"
    assert must_1_rows[0].match_type == "direct"
    # the dropped id is recorded in the reason text for debuggability, but never
    # written to candidate_fact_id itself (checked above).
    assert "dropped unknown fact id" in must_1_rows[0].reason
    assert "made_up_fact_id" in must_1_rows[0].reason

    # must_2: every fact id the model returned was fake -- despite the model
    # claiming match_type="direct", the persisted row must downgrade to "none"
    # and must_not_claim=True. Fabricated evidence must never survive persistence.
    must_2_rows = by_requirement["must_2"]
    assert len(must_2_rows) == 1
    assert must_2_rows[0].candidate_fact_id is None
    assert must_2_rows[0].match_type == "none"
    assert must_2_rows[0].must_not_claim is True

    # must_3: genuinely no evidence, passes through unchanged.
    must_3_rows = by_requirement["must_3"]
    assert len(must_3_rows) == 1
    assert must_3_rows[0].candidate_fact_id is None
    assert must_3_rows[0].must_not_claim is True

    # No row anywhere may reference a fact id outside the known set.
    for row in rows:
        if row.candidate_fact_id is not None:
            assert row.candidate_fact_id in known_fact_ids


def test_persist_evidence_matches_multiple_valid_facts_become_separate_rows(db_session, settings):
    job = _make_job(db_session)
    job_analysis = JobAnalysis(job_posting_id=job.id, must_have=[], nice_to_have=[])
    db_session.add(job_analysis)
    db_session.commit()
    db_session.refresh(job_analysis)

    known_fact_ids = {"fact_a", "fact_b"}
    result = EvidenceMatchResult(
        matches=[
            EvidenceMatchItem(
                requirement_id="must_1",
                candidate_fact_ids=["fact_a", "fact_b"],
                match_type="partial",
                confidence=0.6,
                reason="Two related facts.",
                must_not_claim=False,
            )
        ]
    )

    rows = persist_evidence_matches(db_session, job_analysis, result, known_fact_ids)
    assert len(rows) == 2
    assert {r.candidate_fact_id for r in rows} == {"fact_a", "fact_b"}
    assert all(r.requirement_id == "must_1" for r in rows)
