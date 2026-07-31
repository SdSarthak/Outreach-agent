"""HTTP behaviour, retry semantics and payload normalisation."""

import json

import pytest
import requests

from src.config import build_settings
from src.integrations.elevenlabs import ElevenLabsError, ElevenLabsIntegration


class FakeResponse:
    def __init__(self, status_code=200, payload=None, text=None, headers=None):
        self.status_code = status_code
        self._payload = payload
        self.text = text if text is not None else json.dumps(payload if payload is not None else {})
        self.headers = headers or {}

    def json(self):
        if self._payload is None:
            raise ValueError("no json")
        return self._payload


class FakeSession:
    """Records every request and replays a scripted list of responses."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []
        self.closed = False

    def request(self, method, url, **kwargs):
        self.calls.append({"method": method, "url": url, **kwargs})
        outcome = self.responses.pop(0) if self.responses else FakeResponse()
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    def close(self):
        self.closed = True


@pytest.fixture
def live_settings(monkeypatch):
    monkeypatch.setenv("DRY_RUN", "false")
    monkeypatch.setenv("ELEVENLABS_API_KEY", "key-123")
    monkeypatch.setenv("ELEVENLABS_AGENT_ID", "agent-123")
    monkeypatch.setenv("RETRY_ATTEMPTS", "3")
    return build_settings()


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    delays = []
    monkeypatch.setattr("src.integrations.elevenlabs.time.sleep", delays.append)
    return delays


def _client(settings, responses):
    session = FakeSession(responses)
    return ElevenLabsIntegration(settings, session=session), session


# ------------------------------------------------------------------ retries
def test_outbound_call_is_not_replayed_after_a_server_error(live_settings):
    """Retrying a POST that dials a customer could ring their phone twice."""
    client, session = _client(live_settings, [FakeResponse(500, text="boom")])

    with pytest.raises(ElevenLabsError):
        client.start_outbound_call("+15550100", {})

    assert len(session.calls) == 1


def test_outbound_call_is_not_replayed_after_a_connection_error(live_settings):
    client, session = _client(live_settings, [requests.ConnectionError("dropped")])

    with pytest.raises(ElevenLabsError):
        client.start_outbound_call("+15550100", {})

    assert len(session.calls) == 1


def test_rate_limited_requests_are_retried(live_settings, no_sleep):
    client, session = _client(
        live_settings,
        [
            FakeResponse(429, headers={"Retry-After": "2"}),
            FakeResponse(200, {"conversation_id": "conv-1", "callSid": "CA1"}),
        ],
    )

    result = client.start_outbound_call("+15550100", {"customer_name": "Ada"})

    assert result["conversation_id"] == "conv-1"
    assert result["call_sid"] == "CA1"
    assert len(session.calls) == 2
    assert no_sleep == [2.0]  # honours Retry-After instead of the backoff curve


def test_absurd_retry_after_is_capped(live_settings, no_sleep):
    client, _ = _client(
        live_settings,
        [FakeResponse(429, headers={"Retry-After": "86400"}), FakeResponse(200, {})],
    )
    client.get_conversation("conv-1")
    assert no_sleep == [30]


def test_unparseable_retry_after_falls_back_to_backoff(live_settings, no_sleep):
    client, _ = _client(
        live_settings,
        [FakeResponse(429, headers={"Retry-After": "Wed, 21 Oct 2015 07:28:00 GMT"}), FakeResponse(200, {})],
    )
    client.get_conversation("conv-1")
    assert no_sleep == [pytest.approx(1.5)]


def test_reads_are_retried_after_a_server_error(live_settings):
    client, session = _client(
        live_settings,
        [FakeResponse(503), requests.Timeout("slow"), FakeResponse(200, {"status": "done"})],
    )
    assert client.get_conversation("conv-1") == {"status": "done"}
    assert len(session.calls) == 3


def test_retries_are_bounded_by_the_configured_attempts(live_settings):
    client, session = _client(live_settings, [FakeResponse(500) for _ in range(5)])
    with pytest.raises(ElevenLabsError):
        client.get_conversation("conv-1")
    assert len(session.calls) == live_settings.retry_attempts


def test_client_errors_are_not_retried(live_settings):
    client, session = _client(live_settings, [FakeResponse(401, text="bad key")])
    with pytest.raises(ElevenLabsError) as excinfo:
        client.get_conversation("conv-1")
    assert "401" in str(excinfo.value)
    assert len(session.calls) == 1


def test_requests_carry_the_api_key_and_timeout(live_settings):
    client, session = _client(live_settings, [FakeResponse(200, {})])
    client.get_conversation("conv-1")
    assert session.calls[0]["headers"]["xi-api-key"] == "key-123"
    assert session.calls[0]["timeout"] == live_settings.http_timeout


# ------------------------------------------------------------- payload shape
def test_non_json_body_becomes_an_empty_mapping(live_settings):
    client, _ = _client(live_settings, [FakeResponse(200, payload=None, text="<html>")])
    assert client.get_conversation("conv-1") == {}


def test_non_mapping_json_becomes_an_empty_mapping(live_settings):
    client, _ = _client(live_settings, [FakeResponse(200, payload=["a", "b"])])
    assert client.get_conversation("conv-1") == {}


def test_summarize_tolerates_a_junk_duration(live_settings):
    client, _ = _client(
        live_settings,
        [FakeResponse(200, {"status": "done", "metadata": {"call_duration_secs": "12.7"}})],
    )
    summary = client.summarize_conversation("conv-1", wait=False)
    assert summary["duration_seconds"] == 12

    client, _ = _client(
        live_settings,
        [FakeResponse(200, {"status": "done", "metadata": {"call_duration_secs": "n/a"}})],
    )
    assert client.summarize_conversation("conv-1", wait=False)["duration_seconds"] == 0


def test_summarize_tolerates_non_mapping_metadata(live_settings):
    client, _ = _client(
        live_settings, [FakeResponse(200, {"status": "done", "metadata": [], "analysis": "nope"})]
    )
    summary = client.summarize_conversation("conv-1", wait=False)
    assert summary["duration_seconds"] == 0
    assert summary["call_successful"] is None


def test_summarize_reports_failure_instead_of_raising(live_settings):
    client, _ = _client(live_settings, [FakeResponse(404, text="gone")])
    summary = client.summarize_conversation("conv-1", wait=False)
    assert summary["status"] == "failed"
    assert summary["transcript"] is None
    assert "404" in summary["error"]


# ------------------------------------------------------------------ polling
def test_wait_for_completion_stops_at_the_deadline(live_settings, monkeypatch):
    clock = {"now": 0.0}
    monkeypatch.setattr("src.integrations.elevenlabs.time.monotonic", lambda: clock["now"])
    monkeypatch.setattr(
        "src.integrations.elevenlabs.time.sleep", lambda seconds: clock.__setitem__("now", clock["now"] + seconds)
    )
    client, session = _client(live_settings, [FakeResponse(200, {"status": "processing"})] * 50)

    data = client.wait_for_completion("conv-1", max_wait=10, poll_interval=4)

    assert data["status"] == "processing"
    assert len(session.calls) == 4  # first read plus polls until the deadline


def test_wait_for_completion_returns_as_soon_as_the_call_ends(live_settings):
    client, session = _client(
        live_settings,
        [FakeResponse(200, {"status": "processing"}), FakeResponse(200, {"status": "done"})],
    )
    assert client.wait_for_completion("conv-1", max_wait=60, poll_interval=1)["status"] == "done"
    assert len(session.calls) == 2


# --------------------------------------------------------------- validation
def test_a_call_needs_a_phone_number(live_settings):
    client, session = _client(live_settings, [])
    with pytest.raises(ElevenLabsError):
        client.start_outbound_call("", {})
    assert session.calls == []


def test_a_conversation_lookup_needs_an_id(live_settings):
    client, _ = _client(live_settings, [])
    with pytest.raises(ElevenLabsError):
        client.get_conversation(None)


# -------------------------------------------------------------- simulation
def test_dry_run_never_touches_the_network(settings):
    client, session = _client(settings, [])
    started = client.start_outbound_call("+1 (555) 010-0999", {"customer_name": "Ada"})

    assert started["simulated"] is True
    assert session.calls == []

    summary = client.summarize_conversation(started["conversation_id"])
    assert summary["status"] == "done"
    assert "Ada" in summary["transcript"]
    assert summary["duration_seconds"] == 168


def test_missing_credentials_force_simulation(monkeypatch):
    monkeypatch.setenv("DRY_RUN", "false")
    client, session = _client(build_settings(), [])
    assert client.live is False
    assert client.start_outbound_call("+15550100", {})["simulated"] is True
    assert session.calls == []


def test_close_releases_the_session(settings):
    client, session = _client(settings, [])
    client.close()
    assert session.closed is True


# --------------------------------------------------------------- transcript
def test_flatten_transcript_handles_every_shape():
    flatten = ElevenLabsIntegration.flatten_transcript
    assert flatten(None) == ""
    assert flatten({}) == ""
    assert flatten({"transcript": "already flat"}) == "already flat"
    assert flatten({"transcript": [{"role": "user", "message": "hi"}]}) == "User: hi"
    # Entries without text are dropped; a missing role defaults to the agent.
    assert flatten({"transcript": [{"role": "user"}, {"text": "bye"}]}) == "Agent: bye"


def test_dynamic_variables_are_flat_scalars():
    client = ElevenLabsIntegration(build_settings(), session=FakeSession([]))
    variables = client.build_dynamic_variables(
        {
            "name": "Ada",
            "company": "Analytical Engines",
            "recent_engagements": [{"type": "email_open"}, {"type": "feature_usage"}],
            "feedback_history": [{"text": "great tool"}],
        },
        {"key_talking_points": ["pricing", "rollout"], "tone": "warm"},
    )
    assert all(isinstance(value, str) for value in variables.values())
    assert variables["engagement_history"] == "email_open; feature_usage"
    assert variables["key_talking_points"] == "pricing; rollout"
    assert variables["previous_interactions"] == "great tool"


def test_dynamic_variables_have_defaults_for_empty_context():
    client = ElevenLabsIntegration(build_settings(), session=FakeSession([]))
    variables = client.build_dynamic_variables({}, {})
    assert variables["customer_name"] == "there"
    assert variables["company"] == "your organization"
    assert variables["tone"] == "professional"
