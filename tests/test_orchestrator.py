"""End-to-end pipeline behaviour, in dry-run against a temporary database."""

import pytest

from src.database import CallRecord, CallStatus, Campaign, EmailRecord, EmailStatus
from src.orchestrator import OutreachOrchestrator


@pytest.fixture
def orchestrator(db):
    instance = OutreachOrchestrator(db_manager=db)
    try:
        yield instance
    finally:
        instance.close()


def test_full_pipeline_persists_every_step(orchestrator, db, customer_factory):
    customer_id = customer_factory()

    results = orchestrator.execute_outreach_workflow([customer_id], campaign_name="Q3")

    assert results["total_customers"] == 1
    assert results["successful_calls"] == 1
    assert results["emails_sent"] == 1

    with db.session_scope() as session:
        call = session.query(CallRecord).one()
        assert call.status == CallStatus.COMPLETED
        assert call.duration_seconds > 0
        assert call.call_transcript
        assert call.campaign_id == results["campaign_id"]

        email = session.query(EmailRecord).one()
        assert email.status == EmailStatus.SENT
        assert email.call_record_id == call.id

        campaign = session.get(Campaign, results["campaign_id"])
        assert campaign.total_customers == 1
        assert campaign.successful_calls == 1
        assert campaign.end_date is not None


def test_customer_without_a_phone_still_gets_an_email(orchestrator, db, customer_factory):
    customer_id = customer_factory(phone="")

    result = orchestrator.execute_customer_outreach(customer_id)

    assert result["call_successful"] is False
    assert result["email_sent"] is True
    with db.session_scope() as session:
        call = session.query(CallRecord).one()
        # The call never connected, so it must not be left as "in progress".
        assert call.status == CallStatus.FAILED
        assert session.query(EmailRecord).one().email_type == "retry"


def test_customer_without_an_email_is_recorded_but_not_mailed(orchestrator, db, customer_factory):
    customer_id = customer_factory(email="not-an-address")

    result = orchestrator.execute_customer_outreach(customer_id)

    assert result["email_sent"] is False
    with db.session_scope() as session:
        assert session.query(CallRecord).count() == 1
        assert session.query(EmailRecord).count() == 0


def test_unknown_customers_are_counted_as_failures(orchestrator, db, customer_factory):
    results = orchestrator.execute_outreach_workflow([customer_factory(), 999_999])

    assert results["total_customers"] == 2
    assert results["failed_calls"] == 1
    assert results["successful_calls"] == 1
    assert len(results["interactions"]) == 1


def test_missing_customer_returns_none(orchestrator):
    assert orchestrator.execute_customer_outreach(999_999) is None


def test_campaign_with_no_customers_does_nothing(orchestrator, db):
    assert orchestrator.execute_outreach_workflow([]) is None
    with db.session_scope() as session:
        assert session.query(Campaign).count() == 0


def test_campaign_aborts_when_it_cannot_be_created(orchestrator, db, customer_factory, monkeypatch):
    """Placing calls that cannot be attributed to a campaign loses the results."""
    customer_id = customer_factory()
    monkeypatch.setattr(orchestrator.analytics, "create_campaign", lambda *args, **kwargs: None)

    assert orchestrator.execute_outreach_workflow([customer_id]) is None
    with db.session_scope() as session:
        assert session.query(CallRecord).count() == 0


def test_a_failing_customer_does_not_abort_the_campaign(orchestrator, customer_factory, monkeypatch):
    first, second = customer_factory(), customer_factory(email="b@example.com")
    original = orchestrator.insight_agent.generate_call_guidance
    calls = {"count": 0}

    def flaky(context):
        calls["count"] += 1
        if calls["count"] == 1:
            raise RuntimeError("guidance service is down")
        return original(context)

    monkeypatch.setattr(orchestrator.insight_agent, "generate_call_guidance", flaky)

    results = orchestrator.execute_outreach_workflow([first, second])

    assert results["failed_calls"] == 1
    assert results["successful_calls"] == 1


def test_defaults_to_every_active_customer(orchestrator, customer_factory):
    customer_factory()
    customer_factory(email="b@example.com")
    results = orchestrator.execute_outreach_workflow()
    assert results["total_customers"] == 2


def test_average_satisfaction_maps_scores_onto_five_points():
    assert OutreachOrchestrator._average_satisfaction([]) == 0.0
    assert OutreachOrchestrator._average_satisfaction(None) == 0.0
    assert OutreachOrchestrator._average_satisfaction([{"success_score": 100}]) == 5.0
    assert OutreachOrchestrator._average_satisfaction(
        [{"success_score": 100}, {"success_score": 0}]
    ) == 2.5


def test_close_is_idempotent(db):
    instance = OutreachOrchestrator(db_manager=db)
    instance.close()
    instance.close()


def test_context_manager_closes_the_integrations(db):
    closed = []
    with OutreachOrchestrator(db_manager=db) as instance:
        instance.elevenlabs.close = lambda: closed.append("elevenlabs")
        instance.gmail.close = lambda: closed.append("gmail")
    assert closed == ["elevenlabs", "gmail"]


def test_close_survives_an_integration_that_refuses_to_close(db):
    instance = OutreachOrchestrator(db_manager=db)

    def explode():
        raise RuntimeError("socket already gone")

    instance.elevenlabs.close = explode
    instance.close()  # must still dispose of the database pool
