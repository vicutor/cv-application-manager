def test_application_progresses_through_funnel_and_is_visible_on_job_detail(
    client, settings, db_session, active_profile_version
):
    """The granular funnel (responded -> hr_interview -> technical_interview ->
    offer) is the whole point of this feature: mark how far a real application
    got, see it reflected on the job detail response, and be able to correct
    a stage (e.g. back to applied) rather than only moving forward."""
    resp = client.post(
        "/api/jobs/import-text",
        json={
            "raw_text": "We need a Platform Engineer with strong Kubernetes experience." + "C" * 30,
            "company_name": "Funnel Test Co",
            "position_title": "Platform Engineer",
            "location_text": "Remote",
            "remote_mode": "remote",
        },
    )
    assert resp.status_code == 201
    job_id = resp.json()["id"]

    resp = client.post(
        f"/api/jobs/{job_id}/applications",
        json={"applied_at": "2026-09-10", "channel": "linkedin"},
    )
    assert resp.status_code == 201
    application_id = resp.json()["id"]
    assert resp.json()["status"] == "applied"

    for stage in ["responded", "hr_interview", "technical_interview", "offer"]:
        resp = client.patch(f"/api/applications/{application_id}", json={"status": stage})
        assert resp.status_code == 200, resp.text
        assert resp.json()["status"] == stage

    resp = client.get(f"/api/jobs/{job_id}")
    assert resp.status_code == 200
    detail = resp.json()
    assert detail["workflow_status"] == "offer"
    assert len(detail["applications"]) == 1
    assert detail["applications"][0]["status"] == "offer"

    # Correcting a mistake (e.g. offer fell through) must work, not just forward progress.
    resp = client.patch(f"/api/applications/{application_id}", json={"status": "rejected"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "rejected"


def test_invalid_status_is_rejected(client, settings, db_session, active_profile_version):
    resp = client.post(
        "/api/jobs/import-text",
        json={
            "raw_text": "We need a Backend Engineer with strong Python experience." + "D" * 30,
            "company_name": "Funnel Test Co 2",
            "position_title": "Backend Engineer",
            "location_text": "Remote",
            "remote_mode": "remote",
        },
    )
    job_id = resp.json()["id"]
    resp = client.post(
        f"/api/jobs/{job_id}/applications",
        json={"applied_at": "2026-09-10", "channel": "other"},
    )
    application_id = resp.json()["id"]

    resp = client.patch(f"/api/applications/{application_id}", json={"status": "ghosted_forever"})
    assert resp.status_code == 400
