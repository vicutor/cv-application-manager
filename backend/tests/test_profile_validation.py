from pathlib import Path

from app.services.candidate_profile.validation import collect_fact_ids, load_and_validate_yaml

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
FIXTURE_PROFILE_PATH = REPO_ROOT / "fixtures" / "candidate.example.yaml"


def test_example_profile_is_valid():
    result = load_and_validate_yaml(FIXTURE_PROFILE_PATH)
    assert result.is_valid, result.errors
    assert result.profile is not None
    assert result.profile.person.full_name


def test_collect_fact_ids_includes_responsibilities_and_achievements():
    result = load_and_validate_yaml(FIXTURE_PROFILE_PATH)
    fact_ids = collect_fact_ids(result.profile)
    assert "resp_examplecorp_001" in fact_ids
    assert "ach_examplecorp_001" in fact_ids


def test_duplicate_ids_are_rejected(tmp_path):
    bad_yaml = tmp_path / "bad.yaml"
    bad_yaml.write_text(
        """
schema_version: 1
person:
  full_name: "Test Person"
summary_facts:
  - id: dup_id
    statement: "First fact"
experience:
  - id: dup_id
    company: "Acme"
    position: "Engineer"
    start_date: "2020-01"
skills: []
""",
        encoding="utf-8",
    )
    result = load_and_validate_yaml(bad_yaml)
    assert not result.is_valid
    assert any("duplicate identifier" in e for e in result.errors)


def test_skill_evidence_ref_must_point_to_existing_fact(tmp_path):
    bad_yaml = tmp_path / "bad_ref.yaml"
    bad_yaml.write_text(
        """
schema_version: 1
person:
  full_name: "Test Person"
skills:
  - id: skill_x
    name: "X"
    level: "advanced"
    evidence_refs:
      - "nonexistent_fact"
""",
        encoding="utf-8",
    )
    result = load_and_validate_yaml(bad_yaml)
    assert not result.is_valid
    assert any("does not match any" in e for e in result.errors)
