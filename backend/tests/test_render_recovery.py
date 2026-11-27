from pathlib import Path

from app import storage


def test_recovery_marks_active_jobs_interrupted_and_preserves_terminal_jobs(tmp_path, monkeypatch):
    db_path = tmp_path / "recovery.sqlite3"
    monkeypatch.setattr(storage, "DB_PATH", db_path)
    storage.init_db()
    storage.save_project("p1", "Project", {})

    for job_id in ("queued", "processing", "cancelling"):
        storage.create_job(job_id, "p1")
    assert storage.start_job("processing")
    storage.request_job_cancel("cancelling")
    storage.create_job("completed", "p1")
    assert storage.start_job("completed")
    assert storage.complete_job_if_processing("completed", "completed.mp4")

    recovered = storage.recover_interrupted_jobs()
    assert {job["id"] for job in recovered} == {"queued", "processing", "cancelling"}
    for job_id in ("queued", "processing", "cancelling"):
        job = storage.get_job(job_id)
        assert job["status"] == "interrupted"
        assert "server restarted" in job["error"].lower()
    assert storage.get_job("completed")["status"] == "completed"
    assert storage.recover_interrupted_jobs() == []


def test_startup_removes_partial_outputs_for_interrupted_jobs(tmp_path, monkeypatch):
    from app import main

    db_path = tmp_path / "startup.sqlite3"
    render_dir = tmp_path / "renders"
    render_dir.mkdir()
    monkeypatch.setattr(storage, "DB_PATH", db_path)
    monkeypatch.setattr(storage, "RENDER_DIR", render_dir)
    storage.init_db()
    storage.save_project("p1", "Project", {})
    storage.create_job("job-1", "p1")
    assert storage.start_job("job-1")
    (render_dir / "job-1.mp4").write_bytes(b"partial")
    (render_dir / "job-1.captions.ass").write_text("[Script Info]")
    (render_dir / "job-1.captions.srt").write_text("legacy partial")

    import asyncio

    async def run_lifespan():
        async with main.lifespan(main.app):
            pass

    asyncio.run(run_lifespan())

    assert storage.get_job("job-1")["status"] == "interrupted"
    assert not (render_dir / "job-1.mp4").exists()
    assert not (render_dir / "job-1.captions.ass").exists()
    assert not (render_dir / "job-1.captions.srt").exists()
