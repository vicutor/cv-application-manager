from pathlib import Path

from app.services.extraction.jsonld import find_jobposting_jsonld, map_jsonld_to_candidate

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
FIXTURE_WITH_JSONLD = REPO_ROOT / "fixtures" / "html" / "justjoinit_devops_sample.html"
FIXTURE_WITHOUT_JSONLD = REPO_ROOT / "fixtures" / "html" / "generic_no_jsonld_sample.html"
FIXTURE_EMBEDDED_HTML_DESCRIPTION = REPO_ROOT / "fixtures" / "html" / "nofluffjobs_devsecops_sample.html"
FIXTURE_PRACUJ_NULL_DESCRIPTION = REPO_ROOT / "fixtures" / "html" / "pracuj_localization_pm_sample.html"


def test_finds_jobposting_jsonld_block():
    html = FIXTURE_WITH_JSONLD.read_text(encoding="utf-8")
    data = find_jobposting_jsonld(html)
    assert data is not None
    assert data["@type"] == "JobPosting"
    assert data["title"] == "Devops Engineer"


def test_returns_none_when_no_jsonld_present():
    html = FIXTURE_WITHOUT_JSONLD.read_text(encoding="utf-8")
    assert find_jobposting_jsonld(html) is None


def test_maps_jsonld_to_candidate_fields():
    html = FIXTURE_WITH_JSONLD.read_text(encoding="utf-8")
    data = find_jobposting_jsonld(html)
    candidate = map_jsonld_to_candidate(data, "https://justjoin.it/job-offer/codetalent-devops-engineer-warszawa-devops")

    assert candidate.company_name == "CodeTalent"
    assert candidate.position_title == "Devops Engineer"
    assert candidate.remote_mode == "remote"  # jobLocationType: TELECOMMUTE
    assert candidate.location_text == "Warszawa, PL"
    assert candidate.salary_min == 20400
    assert candidate.salary_max == 28800
    assert candidate.salary_currency == "PLN"
    assert candidate.salary_period == "monthly"
    assert "Kubernetes" in candidate.description_raw_text
    assert candidate.extraction_method == "json_ld"
    assert candidate.external_job_id == "codetalent-devops-engineer-warszawa-devops"


def test_maps_embedded_html_description_to_readable_paragraphs():
    """NoFluffJobs (and similar boards) embed real HTML -- Word/OneDrive export
    markup with <p>, <li>, <br> -- directly inside the JSON-LD description string.
    Naively stripping tags to nothing collapses the whole thing into one run-on
    paragraph; this asserts paragraph/list structure survives as blank lines.
    """
    html = FIXTURE_EMBEDDED_HTML_DESCRIPTION.read_text(encoding="utf-8")
    data = find_jobposting_jsonld(html)
    candidate = map_jsonld_to_candidate(
        data, "https://nofluffjobs.com/pl/job/gcp-devsecops-engineer-mindbox-krakow"
    )

    assert candidate.company_name == "Mindbox Sp. z o.o."
    assert candidate.position_title == "GCP DevSecOps Engineer"
    assert "\n\n" in candidate.description_clean_text  # real paragraph breaks, not one blob
    assert "<p" not in candidate.description_clean_text
    assert "&amp;" not in candidate.description_clean_text


def test_maps_pracuj_null_description_with_string_hiring_organization():
    """pracuj.pl's JobPosting JSON-LD sets description to a literal null and
    puts the real content in its own non-standard fields (responsibilities,
    experienceRequirements, jobBenefits), and hiringOrganization is a plain
    string rather than an Organization object. Naive extraction turns the null
    into the literal text "None" and drops the company name entirely.
    """
    html = FIXTURE_PRACUJ_NULL_DESCRIPTION.read_text(encoding="utf-8")
    data = find_jobposting_jsonld(html)
    candidate = map_jsonld_to_candidate(
        data, "https://www.pracuj.pl/praca/localization-project-manager-warszawa,oferta,1005138702"
    )

    assert candidate.company_name == "Mindbox Sp. z o.o."
    assert candidate.position_title == "Localization Project Manager"
    assert "None" not in candidate.description_clean_text
    assert "Lead end-to-end localization project execution" in candidate.description_clean_text
    assert "Bachelor's degree in Localization" in candidate.description_clean_text
