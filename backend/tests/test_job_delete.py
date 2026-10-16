import time

from app.models.job_posting import JobPosting


def test_delete_job_removes_row_and_artifacts(client, settings, db_session, active_profile_version):
    resp = client.post(
        "/api/jobs/import-text",
        json={
            "raw_text": "We need a Backend Engineer with 3+ years of Python experience.",
            "company_name": "Delete Test Co",
            "position_title": "Backend Engineer",
            "location_text": "Remote",
            "remote_mode": "remote",
        },
    )
    assert resp.status_code == 201
    job_id = resp.json()["id"]

    resp = client.post(f"/api/jobs/{job_id}/cv-generations", json={})
    assert resp.status_code == 202
    generation_id = resp.json()["id"]

    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        gen = client.get(f"/api/cv-generations/{generation_id}").json()
        if gen["status"] in ("succeeded", "failed"):
            break
        time.sleep(0.5)
    assert gen["status"] == "succeeded", gen

    job_dir = settings.jobs_dir / job_id
    assert job_dir.exists()
    assert any(job_dir.rglob("cv.pdf"))

    resp = client.delete(f"/api/jobs/{job_id}")
    assert resp.status_code == 204

    assert db_session.get(JobPosting, job_id) is None
    assert not job_dir.exists()

    resp = client.get(f"/api/jobs/{job_id}")
    assert resp.status_code == 404

    resp = client.delete(f"/api/jobs/{job_id}")
    assert resp.status_code == 404


def test_archive_job_hides_without_deleting(client, db_session):
    resp = client.post(
        "/api/jobs/import-text",
        json={
            "raw_text": "We need a Data Engineer with strong SQL and Airflow experience.",
            "company_name": "Archive Test Co",
            "position_title": "Data Engineer",
            "location_text": "Remote",
            "remote_mode": "remote",
        },
    )
    job_id = resp.json()["id"]

    resp = client.post(f"/api/jobs/{job_id}/archive")
    assert resp.status_code == 200
    assert resp.json()["workflow_status"] == "archived"

    # Still fetchable directly, just excluded when filtering for non-archived.
    resp = client.get(f"/api/jobs/{job_id}")
    assert resp.status_code == 200
    assert resp.json()["workflow_status"] == "archived"
