from app.services.deduplication.fingerprint import content_hash, dedupe_fingerprint, normalize_token
from app.services.extraction.text_cleaning import clean_text


def test_content_hash_is_stable_and_sensitive():
    a = clean_text("Great   job posting.  \nWith details.   ")
    b = clean_text("Great job posting.\nWith details.")
    assert content_hash(a) == content_hash(b)  # inline whitespace differences washed out by cleaning
    assert content_hash(a) != content_hash("Something entirely different.")


def test_dedupe_fingerprint_ignores_case_and_punctuation():
    fp1 = dedupe_fingerprint("Acme Corp.", "DevOps Engineer", "Remote")
    fp2 = dedupe_fingerprint("acme corp", "devops engineer", "remote")
    assert fp1 == fp2


def test_dedupe_fingerprint_distinguishes_different_roles():
    fp1 = dedupe_fingerprint("Acme Corp", "DevOps Engineer", "Remote")
    fp2 = dedupe_fingerprint("Acme Corp", "Platform Engineer", "Remote")
    assert fp1 != fp2


def test_normalize_token_strips_punctuation():
    assert normalize_token("C++/Kubernetes!!") == "c kubernetes"
