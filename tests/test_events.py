from app.core.events import ApplicationEvents, RuntimeStatus


def test_phase_one_cannot_claim_pipeline_is_running(qtbot):
    events = ApplicationEvents(engine_available=False)
    with qtbot.waitSignal(events.notice, timeout=500):
        events.start()
    assert events.status is RuntimeStatus.UNAVAILABLE


def test_runtime_pause_resume_state_machine(qtbot):
    events = ApplicationEvents(engine_available=True)
    events.start()
    assert events.status is RuntimeStatus.RUNNING
    events.toggle_pause()
    assert events.status is RuntimeStatus.PAUSED
    events.toggle_pause()
    assert events.status is RuntimeStatus.RUNNING
    events.stop()
    assert events.status is RuntimeStatus.STOPPED

