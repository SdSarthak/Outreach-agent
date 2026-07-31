"""Persistence: call records, email records, campaigns and customer context."""

import pytest
from sqlalchemy.exc import IntegrityError

from src.database import CallRecord, CallStatus, Campaign, Customer, EmailStatus, OutreachRepository
from src.database.models import Engagement, Enrollment, Feedback
from src.utils.customer_data import CustomerDataWorkflow


@pytest.fixture
def repository(db):
    return OutreachRepository(db)


# ------------------------------------------------------------------ customers
def test_customers_are_ordered_by_engagement(repository, customer_factory):
    customer_factory(email="low@example.com", engagement_score=0.1)
    top = customer_factory(email="high@example.com", engagement_score=0.9)
    rows = repository.list_customers()
    assert [row["id"] for row in rows][0] == top


def test_inactive_customers_are_excluded_by_default(repository, customer_factory):
    customer_factory(email="active@example.com")
    customer_factory(email="inactive@example.com", is_active=False)
    assert len(repository.list_customers()) == 1
    assert len(repository.list_customers(active_only=False)) == 2


def test_limit_is_applied(repository, customer_factory):
    for index in range(4):
        customer_factory(email=f"c{index}@example.com")
    assert len(repository.customer_ids(limit=2)) == 2


def test_no_customers_is_an_empty_list_not_an_error(repository):
    assert repository.list_customers() == []
    assert repository.customer_ids() == []


def test_duplicate_emails_are_rejected(db, customer_factory):
    customer_factory(email="dupe@example.com")
    with pytest.raises(IntegrityError):
        with db.session_scope() as session:
            session.add(Customer(name="Other", email="dupe@example.com", phone="+15550199"))
    # The failed transaction must not leave a half-written row behind.
    with db.session_scope() as session:
        assert session.query(Customer).count() == 1


# ---------------------------------------------------------------------- calls
def test_call_record_round_trip(repository, customer_factory):
    customer_id = customer_factory()
    call_id = repository.create_call_record(customer_id=customer_id, status="scheduled")

    assert repository.update_call_record(
        call_id,
        status=CallStatus.COMPLETED,
        duration_seconds=90,
        call_transcript="User: hello",
        sentiment="positive",
        success_score=70,
    )

    stored = repository.get_call_record(call_id)
    assert stored["status"] == "completed"
    assert stored["duration_seconds"] == 90
    assert stored["transcript"] == "User: hello"


def test_string_statuses_are_coerced(repository, customer_factory):
    call_id = repository.create_call_record(customer_id=customer_factory(), status="in_progress")
    assert repository.get_call_record(call_id)["status"] == "in_progress"


def test_unknown_status_does_not_break_the_insert(repository, customer_factory):
    call_id = repository.create_call_record(customer_id=customer_factory(), status="who-knows")
    assert repository.get_call_record(call_id)["status"] == CallStatus.SCHEDULED.value


def test_unknown_fields_are_ignored_on_update(repository, customer_factory, db):
    call_id = repository.create_call_record(customer_id=customer_factory())
    assert repository.update_call_record(call_id, customer_id=999, nonsense="x", sentiment="neutral")
    with db.session_scope() as session:
        record = session.get(CallRecord, call_id)
        assert record.customer_id != 999
        assert record.sentiment == "neutral"


def test_updating_a_missing_record_returns_false(repository):
    assert repository.update_call_record(999_999, sentiment="positive") is False
    assert repository.update_call_record(None, sentiment="positive") is False
    assert repository.get_call_record(999_999) is None


def test_creating_a_call_for_an_unknown_customer_fails_cleanly(repository, db):
    # `customer_id` is NOT NULL, so a missing id must not raise out of the repository.
    assert repository.create_call_record(customer_id=None) is None
    with db.session_scope() as session:
        assert session.query(CallRecord).count() == 0


# --------------------------------------------------------------------- emails
def test_email_status_transitions(repository, customer_factory):
    customer_id = customer_factory()
    email_id = repository.create_email_record(
        customer_id=customer_id, subject="Hi", body="Body", status=EmailStatus.DRAFT
    )
    assert repository.update_email_status(email_id, "sent", message_id="gmail-1") is True
    assert repository.update_email_status(999_999, "sent") is False


def test_email_requires_a_customer(repository):
    assert repository.create_email_record(customer_id=None, subject="Hi", body="Body") is None


# ------------------------------------------------------------------ campaigns
def test_campaign_totals_are_written(db, repository):
    with db.session_scope() as session:
        campaign = Campaign(name="Q3")
        session.add(campaign)
        session.flush()
        campaign_id = campaign.id

    assert repository.update_campaign_totals(
        campaign_id, total_customers=5, successful_calls=3, failed_calls=2, emails_sent=4
    )
    with db.session_scope() as session:
        campaign = session.get(Campaign, campaign_id)
        assert (campaign.total_customers, campaign.successful_calls) == (5, 3)


def test_campaign_totals_for_a_missing_campaign(repository):
    assert repository.update_campaign_totals(None) is False
    assert repository.update_campaign_totals(999_999, total_customers=1) is False


# ------------------------------------------------------------------- context
def test_customer_context_aggregates_related_rows(db, customer_factory):
    customer_id = customer_factory()
    with db.session_scope() as session:
        session.add(Enrollment(customer_id=customer_id, product="Premium Suite"))
        session.add(Engagement(customer_id=customer_id, engagement_type="feature_usage", value=10))
        session.add(Feedback(customer_id=customer_id, feedback_text="great", sentiment="positive"))

    context = CustomerDataWorkflow(db).get_customer_context(customer_id)

    assert context["customer_id"] == customer_id
    assert context["enrollments"][0]["product"] == "Premium Suite"
    assert context["recent_engagements"][0]["type"] == "feature_usage"
    assert context["feedback_history"][0]["text"] == "great"


def test_customer_context_for_a_missing_customer(db):
    assert CustomerDataWorkflow(db).get_customer_context(999_999) is None


def test_batch_context_skips_unknown_ids(db, customer_factory):
    customer_id = customer_factory()
    contexts = CustomerDataWorkflow(db).get_batch_customer_contexts([customer_id, 999_999, None])
    assert len(contexts) == 1


def test_session_scope_rolls_back_on_error(db):
    with pytest.raises(RuntimeError):
        with db.session_scope() as session:
            session.add(Customer(name="Temp", email="temp@example.com", phone="+15550111"))
            session.flush()
            raise RuntimeError("boom")
    with db.session_scope() as session:
        assert session.query(Customer).count() == 0
