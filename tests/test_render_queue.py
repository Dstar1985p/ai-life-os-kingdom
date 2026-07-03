"""Render queue behaviour — job bookkeeping without doing real renders."""
from backend.services import render_queue


def test_enqueue_creates_job(monkeypatch):
    # Stop the worker from actually starting
    monkeypatch.setattr(render_queue, "_ensure_worker", lambda: None)
    render_queue._jobs.clear()

    job = render_queue.enqueue_render("test_track_a", "notes")
    assert job["status"] == "queued"
    assert render_queue.get_job("test_track_a") is job


def test_enqueue_is_idempotent_while_active(monkeypatch):
    monkeypatch.setattr(render_queue, "_ensure_worker", lambda: None)
    render_queue._jobs.clear()

    first = render_queue.enqueue_render("test_track_b")
    second = render_queue.enqueue_render("test_track_b")
    assert first is second


def test_finished_job_can_be_requeued(monkeypatch):
    monkeypatch.setattr(render_queue, "_ensure_worker", lambda: None)
    render_queue._jobs.clear()

    job = render_queue.enqueue_render("test_track_c")
    job["status"] = "done"
    requeued = render_queue.enqueue_render("test_track_c")
    assert requeued is not job
    assert requeued["status"] == "queued"


def test_all_jobs_sorted_newest_first(monkeypatch):
    monkeypatch.setattr(render_queue, "_ensure_worker", lambda: None)
    render_queue._jobs.clear()

    a = render_queue.enqueue_render("track_1")
    a["queued_at"] = "2026-01-01T00:00:00"
    b = render_queue.enqueue_render("track_2")
    b["queued_at"] = "2026-06-01T00:00:00"
    jobs = render_queue.all_jobs()
    assert jobs[0]["track_name"] == "track_2"
