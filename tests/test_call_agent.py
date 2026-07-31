"""Dialling, provider fallback and outcome normalisation."""

import pytest

from src.agents.call_agent import CallAgent
from src.integrations.elevenlabs import ElevenLabsError

CUSTOMER = {"customer_id": 1, "name": "Ada", "phone": "+15550100", "company": "Engines"}
GUIDANCE = {"key_talking_points": ["pricing"], "tone": "warm"}


class BrokenElevenLabs:
    def build_dynamic_variables(self, context, guidance):
        return {"customer_name": context.get("name")}

    def start_outbound_call(self, phone_number, dynamic_variables):
        raise ElevenLabsError("provider is down")


class FakeTwilio:
    def __init__(self, sid="CA123"):
        self.sid = sid
        self.calls = []

    def make_call(self, to_number, callback_url):
        self.calls.append((to_number, callback_url))
        return self.sid

    def get_call_status(self, call_sid):
        return {"call_sid": call_sid, "status": "completed", "duration": 90}

    def get_call_recording(self, call_sid):
        return "https://api.twilio.com/recording.mp3"


@pytest.fixture
def agent(settings):
    return CallAgent(settings=settings)


def test_a_customer_without_a_phone_number_is_skipped(agent):
    assert agent.initiate_call({**CUSTOMER, "phone": None}, GUIDANCE) is None
    assert agent.initiate_call({}, GUIDANCE) is None


def test_dry_run_call_completes_end_to_end(agent):
    details = agent.initiate_call(CUSTOMER, GUIDANCE)
    assert details["simulated"] is True
    assert details["conversation_id"]

    outcome = agent.await_outcome(details)
    assert outcome["status"] == "completed"
    assert outcome["duration"] == 168
    assert outcome["customer_engaged"] is True
    assert "Ada" in outcome["transcript"]


def test_falls_back_to_twilio_when_the_agent_provider_fails(settings):
    twilio = FakeTwilio()
    agent = CallAgent(elevenlabs=BrokenElevenLabs(), twilio=twilio, settings=settings)

    details = agent.initiate_call(CUSTOMER, GUIDANCE)

    assert details["call_sid"] == "CA123"
    assert details["conversation_id"] is None
    assert twilio.calls[0][0] == "+15550100"

    outcome = agent.await_outcome(details)
    assert outcome["status"] == "completed"
    assert outcome["duration"] == 90
    assert outcome["audio_url"].endswith(".mp3")


def test_returns_none_when_no_provider_can_place_the_call(settings):
    class DeadTwilio(FakeTwilio):
        def make_call(self, to_number, callback_url):
            return None

    agent = CallAgent(elevenlabs=BrokenElevenLabs(), twilio=DeadTwilio(), settings=settings)
    assert agent.initiate_call(CUSTOMER, GUIDANCE) is None


def test_await_outcome_of_nothing_is_an_empty_dict(agent):
    assert agent.await_outcome(None) == {}
    assert agent.await_outcome({}) == {}


def test_engagement_needs_both_a_transcript_and_real_duration(agent):
    assert agent.await_outcome({"transcript": "User: hi", "duration": 5})["customer_engaged"] is False
    assert agent.await_outcome({"duration": 300})["customer_engaged"] is False


@pytest.mark.parametrize(
    "provider_status,expected",
    [
        ("done", "completed"),
        ("completed", "completed"),
        ("processed", "completed"),
        ("in-progress", "in_progress"),
        ("ringing", "in_progress"),
        ("queued", "in_progress"),
        ("no-answer", "failed"),
        ("busy", "failed"),
        ("cancelled", "failed"),
        (None, "failed"),
        ("", "failed"),
        ("something-new", "something-new"),
    ],
)
def test_provider_statuses_are_normalised(provider_status, expected):
    assert CallAgent._normalize_status(provider_status) == expected


def test_callback_url_has_a_default(agent):
    assert agent.callback_url.startswith("http")


def test_execute_call_combines_both_steps(agent):
    outcome = agent.execute_call(CUSTOMER, GUIDANCE)
    assert outcome["status"] == "completed"
    assert agent.execute_call({"customer_id": 2}, GUIDANCE) is None
