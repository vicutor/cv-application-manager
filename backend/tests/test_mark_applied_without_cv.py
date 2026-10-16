def test_mark_applied_without_a_generated_cv(client, settings, db_session, active_profile_version):
    """The user may apply with a CV they didn't generate through this app --
    marking a posting as applied must not require a succeeded CvGeneration."""
    resp = client.post(
        "/api/jobs/import-text",
        json={
            "raw_text": "We need a Backend Engineer with 3+ years of Python experience.",
            "company_name": "No CV Co",
            "position_title": "Backend Engineer",
            "location_text": "Remote",
            "remote_mode": "remote",
        },
    )
    assert resp.status_code == 201
    job_id = resp.json()["id"]

    resp = client.post(
        f"/api/jobs/{job_id}/applications",
        json={
            "applied_at": "2026-09-02",
            "channel": "linkedin",
            "notes": "Applied with my own generic CV",
        },
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["status"] == "applied"
    assert resp.json()["cv_generation_id"] is None

    resp = client.get("/api/jobs")
    job_row = next(j for j in resp.json() if j["id"] == job_id)
    assert job_row["applied"] is True
    assert job_row["workflow_status"] == "applied"
    assert job_row["has_cv"] is False


def test_mark_applied_still_validates_a_given_cv_generation_id(client, settings, db_session, active_profile_version):
    """When a cv_generation_id IS given, it must still be a real, succeeded
    generation belonging to this posting -- the optionality doesn't weaken
    validation for the case where the field is actually used."""
    resp = client.post(
        "/api/jobs/import-text",
        json={
            "raw_text": "We need a Backend Engineer with 5+ years of Go experience.",
            "company_name": "Bad Generation Co",
            "position_title": "Backend Engineer",
            "location_text": "Remote",
            "remote_mode": "remote",
        },
    )
    job_id = resp.json()["id"]

    resp = client.post(
        f"/api/jobs/{job_id}/applications",
        json={
            "cv_generation_id": "not-a-real-generation-id",
            "applied_at": "2026-09-02",
        },
    )
    assert resp.status_code == 400
