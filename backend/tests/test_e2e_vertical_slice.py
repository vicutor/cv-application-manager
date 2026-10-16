"""End-to-end test of the first vertical slice, mirroring spec section 20's E2E flow:
empty DB -> configure profile -> add a fixture posting via pasted text -> confirm
extraction -> generate a CV via the (currently mocked) pipeline -> see the PDF ->
mark as applied -> check status on the list -> re-import the same posting and see
the duplicate warning.

No network calls and no paid LLM calls: the CV pipeline is fully deterministic
(built directly from the candidate profile) and LaTeX compilation runs a real local
xelatex, not a mock -- that's the one genuinely slow, environment-dependent step, so
it gets a generous poll timeout.
"""

import time

import pytest

JOB_PAYLOAD = {
    "raw_text": (
        "We are hiring a Platform Engineer to help scale our internal developer "
        "platform. You will work with Kubernetes, Terraform and CI/CD pipelines "
        "daily, alongside a small, senior team."
    ),
    "source_url": "https://example.com/jobs/e2e-vertical-slice",
    "company_name": "Vertical Slice Inc",
    "position_title": "Platform Engineer",
    "location_text": "Remote",
    "remote_mode": "remote",
    "technologies": ["Kubernetes", "Terraform", "CI/CD"],
}


def _wait_for_terminal_status(client, generation_id: str, timeout_seconds: int = 30) -> dict:
    deadline = time.monotonic() + timeout_seconds
    data = {}
    while time.monotonic() < deadline:
        resp = client.get(f"/api/cv-generations/{generation_id}")
        assert resp.status_code == 200
        data = resp.json()
        if data["status"] in ("succeeded", "failed"):
            return data
        time.sleep(0.5)
    pytest.fail(f"generation did not reach a terminal status within {timeout_seconds}s: {data}")


def test_vertical_slice_end_to_end(client, active_profile_version):
    # 1 & 2: empty-ish DB with an active candidate profile configured (fixture).
    assert active_profile_version.is_active

    # 3 & 4: add a posting via pasted text; our import-text request already carries
    # the user-confirmed company/title fields (the "correction before save" step).
    resp = client.post("/api/jobs/import-text", json=JOB_PAYLOAD)
    assert resp.status_code == 201, resp.text
    job = resp.json()
    job_id = job["id"]
    assert job["company_name"] == JOB_PAYLOAD["company_name"]
    assert job["workflow_status"] == "new"

    # List and detail views show the posting.
    resp = client.get("/api/jobs")
    assert resp.status_code == 200
    assert any(j["id"] == job_id for j in resp.json())

    resp = client.get(f"/api/jobs/{job_id}")
    assert resp.status_code == 200
    assert resp.json()["position_title"] == JOB_PAYLOAD["position_title"]

    # 5: generate a CV using the mocked (deterministic, no paid LLM) pipeline.
    resp = client.post(f"/api/jobs/{job_id}/cv-generations", json={})
    assert resp.status_code == 202, resp.text
    generation_id = resp.json()["id"]
    assert resp.json()["status"] == "queued"

    generation = _wait_for_terminal_status(client, generation_id)
    assert generation["status"] == "succeeded", generation.get("error_message")
    assert generation["fact_check_status"] == "passed"
    assert generation["pdf_page_count"] is not None
    assert generation["pdf_page_count"] <= generation["target_pages"]

    # 6: see (download) the PDF and the .tex source.
    resp = client.get(f"/api/cv-generations/{generation_id}/pdf")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
    assert len(resp.content) > 1000  # a real compiled PDF, not an empty stub

    resp = client.get(f"/api/cv-generations/{generation_id}/tex")
    assert resp.status_code == 200
    assert b"\\documentclass" in resp.content
    assert b"\\end{document}" in resp.content

    # Regenerating must never overwrite the previous version.
    resp = client.post(f"/api/jobs/{job_id}/cv-generations", json={})
    assert resp.status_code == 202
    second_generation_id = resp.json()["id"]
    assert resp.json()["version_number"] == 2
    second_generation = _wait_for_terminal_status(client, second_generation_id)
    assert second_generation["status"] == "succeeded"
    assert second_generation_id != generation_id

    resp = client.get(f"/api/jobs/{job_id}/cv-generations")
    assert resp.status_code == 200
    versions = {g["version_number"] for g in resp.json()}
    assert versions == {1, 2}

    # 7: mark as applied, using the first generated CV version.
    resp = client.post(
        f"/api/jobs/{job_id}/applications",
        json={
            "cv_generation_id": generation_id,
            "applied_at": "2026-09-01",
            "channel": "company_form",
            "notes": "Applied via the careers page",
        },
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["status"] == "applied"

    # 8: status is immediately visible on the list, without opening the detail view.
    resp = client.get("/api/jobs")
    job_row = next(j for j in resp.json() if j["id"] == job_id)
    assert job_row["applied"] is True
    assert job_row["applied_at"] is not None
    assert job_row["workflow_status"] == "applied"
    assert job_row["has_cv"] is True

    # 9: re-importing the identical posting must surface a duplicate warning, not
    # silently create a second, independent record.
    resp = client.post("/api/jobs/import-text", json=JOB_PAYLOAD)
    assert resp.status_code == 409
    duplicate = resp.json()["detail"]
    assert duplicate["job_posting_id"] == job_id
    assert duplicate["match_level"] == "exact"

    # The user can still consciously save it as a separate posting.
    resp = client.post("/api/jobs/import-text", json={**JOB_PAYLOAD, "allow_duplicate": True})
    assert resp.status_code == 201
    assert resp.json()["id"] != job_id
