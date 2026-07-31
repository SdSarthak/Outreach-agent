"""Gmail and Twilio behaviour that does not need live credentials."""

import base64
from email import message_from_bytes

import pytest

from src.config import build_settings
from src.integrations import GmailIntegration, TwilioIntegration


@pytest.fixture
def gmail(settings):
    return GmailIntegration(settings)


# ------------------------------------------------------------------- gmail
def test_dry_run_emails_go_to_the_outbox(gmail):
    first = gmail.send_email("ada@example.com", "Hi", "Body")
    second = gmail.send_email("grace@example.com", "Hi again", "Body")

    assert gmail.live is False
    assert [first, second] == ["dryrun-1", "dryrun-2"]
    assert [message["to"] for message in gmail.sent_messages] == [
        "ada@example.com",
        "grace@example.com",
    ]


def test_sending_without_a_recipient_fails_cleanly(gmail):
    assert gmail.send_email("", "Hi", "Body") is None
    assert gmail.sent_messages == []


def test_message_encoding_survives_unicode(monkeypatch):
    monkeypatch.setenv("GMAIL_ADDRESS", "agent@example.com")
    gmail = GmailIntegration(build_settings())

    payload = gmail.build_message("zoë@example.com", "Café ☕ update", "Grüße, Zoë — 你好")
    parsed = message_from_bytes(base64.urlsafe_b64decode(payload["raw"]))

    assert parsed.get_payload(decode=True).decode("utf-8") == "Grüße, Zoë — 你好"
    assert "agent@example.com" in parsed["from"]


def test_html_messages_declare_their_type(gmail):
    payload = gmail.build_message("ada@example.com", "Hi", "<b>hi</b>", html=True)
    parsed = message_from_bytes(base64.urlsafe_b64decode(payload["raw"]))
    assert parsed.get_content_type() == "text/html"


def test_templates_render_with_the_signature(gmail):
    subject, body = gmail.format_email(
        "follow_up", {"customer_name": "Ada", "key_topics": "pricing", "next_steps": "a demo"}
    )
    assert subject == "Following up on our recent conversation"
    assert "Ada" in body and "pricing" in body
    assert body.rstrip().endswith(gmail.signature.strip())


def test_a_template_with_a_missing_variable_does_not_raise(gmail):
    assert gmail.format_email("follow_up", {"customer_name": "Ada"}) == (None, None)


def test_an_unknown_template_returns_nothing(gmail):
    assert gmail.format_email("does_not_exist", {}) == (None, None)


def test_templates_can_be_overridden_from_config(tmp_path):
    config = tmp_path / "config.yaml"
    config.write_text(
        "email_templates:\n"
        "  follow_up:\n"
        "    subject: 'Custom {customer_name}'\n"
        "    body: 'Body {customer_name}'\n"
        "  broken:\n"
        "    subject: 'no body'\n",
        encoding="utf-8",
    )
    gmail = GmailIntegration(build_settings(str(config)))

    assert gmail.format_email("follow_up", {"customer_name": "Ada"}) == ("Custom Ada", "Body Ada")
    # An override missing `body` is ignored rather than replacing a good template.
    assert "broken" not in gmail.get_email_templates()


def test_close_is_safe_without_a_service(gmail):
    gmail.close()
    assert gmail.live is False


# ------------------------------------------------------------------ twilio
def test_dry_run_calls_are_simulated(settings):
    twilio = TwilioIntegration(settings)
    assert twilio.live is False
    sid = twilio.make_call("+1 (555) 010-0123", "https://example.com/voice.xml")
    assert sid == "sim_call_100123"
    assert twilio.get_call_status(sid)["status"] == "completed"
    assert twilio.end_call(sid) is True
    assert twilio.get_call_recording(sid) is None


def test_calls_need_a_destination(settings):
    twilio = TwilioIntegration(settings)
    assert twilio.make_call("", "https://example.com") is None
    assert twilio.get_call_status(None) is None
    assert twilio.end_call(None) is False


def test_a_number_without_digits_still_yields_an_id(settings):
    assert TwilioIntegration(settings).make_call("extension", "https://example.com") == "sim_call_000000"
