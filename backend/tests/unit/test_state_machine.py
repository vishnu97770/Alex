import pytest

from app.core import state_machine as sm
from app.core.errors import IllegalTransition


def test_application_happy_path():
    s = sm.ApplicationState.DRAFT
    for nxt in ("DOCUMENTS_UPLOADED", "PROCESSING", "ANALYSIS_READY", "UNDER_REVIEW", "DECIDED"):
        s = sm.APPLICATION.check(s, sm.ApplicationState(nxt))
    assert s == sm.ApplicationState.DECIDED


@pytest.mark.parametrize(
    "machine,src,dst",
    [
        (sm.APPLICATION, sm.ApplicationState.DRAFT, sm.ApplicationState.DECIDED),
        (sm.APPLICATION, sm.ApplicationState.DECIDED, sm.ApplicationState.DRAFT),
        (sm.VOICE_SESSION, sm.VoiceSessionState.SESSION_END, sm.VoiceSessionState.LISTENING),
        (sm.OUTBOUND, sm.OutboundState.RINGING, sm.OutboundState.CONVERSING),
        (sm.OUTBOUND, sm.OutboundState.AUDITED, sm.OutboundState.TRIGGERED),
        (sm.CALL, sm.CallState.COMPLETED, sm.CallState.ACTIVE),
    ],
)
def test_illegal_transitions_rejected(machine, src, dst):
    with pytest.raises(IllegalTransition):
        machine.check(src, dst)


def test_processing_failure_and_retry():
    assert sm.APPLICATION.can(sm.ApplicationState.PROCESSING, sm.ApplicationState.PROCESSING_FAILED)
    assert sm.APPLICATION.can(sm.ApplicationState.PROCESSING_FAILED, sm.ApplicationState.PROCESSING)


def test_voice_interrupt_loop():
    v = sm.VoiceSessionState
    s = sm.VOICE_SESSION.check(v.SESSION_CONNECTING, v.LISTENING)
    s = sm.VOICE_SESSION.check(s, v.PROCESSING)
    s = sm.VOICE_SESSION.check(s, v.SPEAKING)
    s = sm.VOICE_SESSION.check(s, v.INTERRUPTED)
    s = sm.VOICE_SESSION.check(s, v.LISTENING)
    assert s == v.LISTENING


def test_outbound_failure_always_audited():
    for src in sm.OutboundState:
        if src not in (sm.OutboundState.COMPLETED, sm.OutboundState.FAILED, sm.OutboundState.AUDITED):
            assert sm.OUTBOUND.can(src, sm.OutboundState.FAILED)
