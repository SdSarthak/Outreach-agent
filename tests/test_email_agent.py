"""Follow-up drafting, delivery and persistence."""

import pytest

from src.agents.email_agent import EmailAgent
from src.database import EmailRecord, EmailStatus, OutreachRepository

CUSTOMER = {
    "customer_id": 1,
    "name": "Ada Lovelace",
    "email": "ada@example.com",
    "company": "Analytical Engines",
}


@pytest.fixture
def agent():
    return EmailAgent()


def _analysis(followup_type, next_action="Send personalized follow-up email"):
    return {
        "follow_up_recommendation": {"type": followup_type},
        "next_action": next_action,
    }


@pytest.mark.parametrize(
    "followup_type,expected",
    [
        ("retry", "retry"),
        ("follow_email", "standard"),
        ("follow_email_and_meeting", "meeting_request"),
        ("follow_meeting", "meeting_request"),
        (None, "standard"),
        ("something_new", "standard"),
    ],
)
def test_followup_type_selects_the_template(agent, followup_type, expected):
    draft = agent.draft_followup_email(CUSTOMER, _analysis(followup_type))
    assert draft["type"] == expected


def test_draft_includes_the_signature_and_recap(agent):
    draft = agent.draft_followup_email(CUSTOMER, _analysis("follow_email"))
    assert draft["body"].endswith(agent.signature)
    assert "send personalized follow-up email" in draft["body"]
    assert "Ada" in draft["body"]
    assert "Analytical Engines" in draft["body"]


def test_draft_without_a_recap_has_no_dangling_sentence(agent):
    draft = agent.draft_followup_email(CUSTOMER, {"follow_up_recommendation": {"type": "retry"}})
    assert "As a next step" not in draft["body"]


def test_blank_name_falls_back_to_a_greeting(agent):
    """A whitespace-only name used to raise IndexError and kill the outreach."""
    draft = agent.draft_followup_email({**CUSTOMER, "name": "   "}, _analysis("follow_email"))
    assert draft["subject"] == "Thank you for your time, there"
    assert draft["body"].startswith("Hi there,")


def test_missing_name_and_company_use_neutral_wording(agent):
    draft = agent.draft_followup_email(
        {"customer_id": 2, "email": "x@example.com", "name": None, "company": None},
        _analysis("follow_email"),
    )
    assert "your organization" in draft["body"]


def test_unicode_names_survive_drafting(agent):
    draft = agent.draft_followup_email(
        {**CUSTOMER, "name": "Zoë Müller-Nyström"}, _analysis("follow_email")
    )
    assert "Zoë" in draft["subject"]


def test_missing_email_address_is_skipped(agent):
    assert agent.draft_followup_email({**CUSTOMER, "email": None}, _analysis("follow_email")) is None
    assert agent.draft_followup_email({**CUSTOMER, "email": "  "}, _analysis("follow_email")) is None


@pytest.mark.parametrize("address", ["not-an-email", "ada@example", "ada @example.com", "a@b.c,d@e.f"])
def test_malformed_email_addresses_are_rejected(agent, address):
    assert agent.draft_followup_email({**CUSTOMER, "email": address}, _analysis("retry")) is None


def test_addresses_are_trimmed_before_sending(agent):
    draft = agent.draft_followup_email({**CUSTOMER, "email": "  ada@example.com "}, _analysis("retry"))
    assert draft["customer_email"] == "ada@example.com"


def test_send_followup_persists_a_sent_record(db, customer_factory):
    customer_id = customer_factory()
    repository = OutreachRepository(db)
    agent = EmailAgent(db, repository=repository)

    result = agent.send_followup({**CUSTOMER, "customer_id": customer_id}, _analysis("follow_email"))

    assert result["sent"] is True
    assert result["message_id"].startswith("dryrun-")
    with db.session_scope() as session:
        record = session.get(EmailRecord, result["email_record_id"])
        assert record.status == EmailStatus.SENT
        assert record.customer_id == customer_id
        assert record.subject == result["subject"]


def test_send_followup_records_a_failure(db, customer_factory, monkeypatch):
    customer_id = customer_factory()
    agent = EmailAgent(db, repository=OutreachRepository(db))
    monkeypatch.setattr(agent.gmail, "send_email", lambda *args, **kwargs: None)

    result = agent.send_followup({**CUSTOMER, "customer_id": customer_id}, _analysis("follow_email"))

    assert result["sent"] is False
    with db.session_scope() as session:
        assert session.get(EmailRecord, result["email_record_id"]).status == EmailStatus.FAILED


def test_send_followup_without_an_address_sends_nothing(db, customer_factory):
    agent = EmailAgent(db, repository=OutreachRepository(db))
    result = agent.send_followup({"customer_id": customer_factory(), "name": "A"}, _analysis("retry"))
    assert result == {"sent": False, "message_id": None, "email_record_id": None}
    assert agent.gmail.sent_messages == []


def test_email_without_a_customer_id_is_not_persisted(db, caplog):
    agent = EmailAgent(db, repository=OutreachRepository(db))
    with caplog.at_level("WARNING"):
        assert agent.log_email(None, None, "subject", "body") is None
    assert "no customer id" in caplog.text


def test_agent_without_a_database_still_drafts_and_sends():
    agent = EmailAgent()
    result = agent.send_followup(CUSTOMER, _analysis("follow_email"))
    assert result["sent"] is True
    assert result["email_record_id"] is None
