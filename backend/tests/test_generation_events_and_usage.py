"""Offline tests for the pipeline event log, per-generation cost totals, and
the /api/usage/summary aggregation. Uses the mock pipeline (via the TestClient,
same as the existing e2e test) so no real API calls happen -- the LlmRun rows
used to test usage aggregation are inserted directly.
"""

import time

from app.models.llm_run import LlmRun

JOB_PAYLOAD = {
    "company_name": "Events Test Co",
    "position_title": "Backend Engineer",
    "raw_text": "We are looking for a backend engineer with Python experience. " * 3,
    "technologies": ["Python"],
    "allow_duplicate": True,
}


def _wait_for_terminal_status(client, generation_id, timeout=10):
    deadline = time.time() + timeout
    while time.time() < deadline:
        resp = client.get(f"/api/cv-generations/{generation_id}")
        data = resp.json()
        if data["status"] in ("succeeded", "failed"):
            return data
        time.sleep(0.05)
    raise TimeoutError("generation did not reach a terminal status in time")


def test_mock_pipeline_logs_events_in_order(client, active_profile_version):
    resp = client.post("/api/jobs/import-text", json=JOB_PAYLOAD)
    assert resp.status_code == 201, resp.text
    job_id = resp.json()["id"]

    resp = client.post(f"/api/jobs/{job_id}/cv-generations", json={})
    assert resp.status_code == 202, resp.text
    generation_id = resp.json()["id"]

    generation = _wait_for_terminal_status(client, generation_id)
    assert generation["status"] == "succeeded", generation.get("error_message")

    resp = client.get(f"/api/cv-generations/{generation_id}/events")
    assert resp.status_code == 200
    events = resp.json()

    stages = [e["stage"] for e in events]
    assert stages == ["drafting", "fact_checking", "ats_checking", "rendering"]
    assert all(e["status"] == "succeeded" for e in events)
    assert all(e["completed_at"] is not None for e in events)
    assert all(e["started_at"] <= e["completed_at"] for e in events)
    # mock pipeline makes no LLM calls -- no event should carry token/cost data
    assert all(e["cost_usd"] is None for e in events)


def test_fail_marks_the_current_event_failed_with_the_error_message(client, active_profile_version, db_session):
    """_fail() is the single path every pipeline failure funnels through --
    verify it correctly finishes the in-flight GenerationEvent as failed and
    records the error message on it, rather than leaving it stuck at "running"."""
    from app.models.cv_generation import CvGeneration
    from app.models.generation_event import GenerationEvent
    from app.services.cv_generation.events import start_event
    from app.services.cv_generation.pipeline import _fail

    resp = client.post("/api/jobs/import-text", json=JOB_PAYLOAD)
    job_id = resp.json()["id"]
    resp = client.post(f"/api/jobs/{job_id}/cv-generations", json={})
    generation_id = resp.json()["id"]
    _wait_for_terminal_status(client, generation_id)  # let the real run finish first

    generation = db_session.get(CvGeneration, generation_id)
    event = start_event(db_session, generation, "fact_checking")
    assert event.status == "running"
    assert event.completed_at is None

    _fail(db_session, generation, "fact_check_failed", "bullet cites an unknown fact id", event)

    db_session.refresh(event)
    assert generation.status == "failed"
    assert generation.error_stage == "fact_check_failed"
    assert event.status == "failed"
    assert event.message == "bullet cites an unknown fact id"
    assert event.completed_at is not None

    stored = db_session.get(GenerationEvent, event.id)
    assert stored.status == "failed"


def test_generation_read_includes_zero_cost_for_mock_pipeline(client, active_profile_version):
    resp = client.post("/api/jobs/import-text", json=JOB_PAYLOAD)
    job_id = resp.json()["id"]
    resp = client.post(f"/api/jobs/{job_id}/cv-generations", json={})
    generation_id = resp.json()["id"]
    _wait_for_terminal_status(client, generation_id)

    resp = client.get(f"/api/cv-generations/{generation_id}")
    data = resp.json()
    assert data["total_cost_usd"] == 0.0
    assert data["total_input_tokens"] == 0
    assert data["total_output_tokens"] == 0

    resp = client.get(f"/api/jobs/{job_id}/cv-generations")
    listed = resp.json()
    assert listed[0]["total_cost_usd"] == 0.0


def test_usage_summary_empty(client):
    resp = client.get("/api/usage/summary")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_cost_usd"] == 0.0
    assert data["total_calls"] == 0
    assert data["by_stage"] == []
    assert data["by_model"] == []


def test_usage_summary_aggregates_llm_runs(client, db_session):
    db_session.add_all(
        [
            LlmRun(
                stage="analysis", provider="anthropic", model="claude-haiku-4-5",
                input_tokens=100, output_tokens=50, estimated_cost_usd=0.001, status="success",
            ),
            LlmRun(
                stage="analysis", provider="anthropic", model="claude-haiku-4-5",
                input_tokens=200, output_tokens=80, estimated_cost_usd=0.002, status="success",
            ),
            LlmRun(
                stage="drafting", provider="anthropic", model="claude-sonnet-5",
                input_tokens=1000, output_tokens=500, estimated_cost_usd=0.02, status="success",
            ),
            LlmRun(
                stage="drafting", provider="anthropic", model="claude-sonnet-5",
                input_tokens=None, output_tokens=None, estimated_cost_usd=None, status="error",
            ),
        ]
    )
    db_session.commit()

    resp = client.get("/api/usage/summary")
    assert resp.status_code == 200
    data = resp.json()

    assert data["total_calls"] == 4
    assert data["failed_calls"] == 1
    assert abs(data["total_cost_usd"] - 0.023) < 1e-9
    assert data["total_input_tokens"] == 1300
    assert data["total_output_tokens"] == 630

    by_stage = {item["key"]: item for item in data["by_stage"]}
    assert by_stage["analysis"]["calls"] == 2
    assert abs(by_stage["analysis"]["cost_usd"] - 0.003) < 1e-9
    assert by_stage["drafting"]["calls"] == 2
    assert abs(by_stage["drafting"]["cost_usd"] - 0.02) < 1e-9

    by_model = {item["key"]: item for item in data["by_model"]}
    assert by_model["claude-haiku-4-5"]["calls"] == 2
    assert by_model["claude-sonnet-5"]["calls"] == 2

    assert len(data["by_day"]) == 1
    assert abs(data["by_day"][0]["cost_usd"] - 0.023) < 1e-9
