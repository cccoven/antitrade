from scheduler import build_scheduler


def test_build_scheduler_registers_background_jobs():
    sched = build_scheduler()
    job_ids = {j.id for j in sched.get_jobs()}
    assert "radar_ingest" in job_ids
    assert "radar_briefing" in job_ids
    assert "notification_dispatch" in job_ids
    assert "notification_cleanup" in job_ids
    assert "market_main_open_publish" in job_ids
    assert "market_overview_refresh" in job_ids
    assert "daily_market_briefing_refresh" in job_ids
    if sched.running:
        sched.shutdown(wait=False)
