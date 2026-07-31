"""Campaign metrics and the rolling performance summary."""

from datetime import datetime, timedelta

import pytest

from src.database import OutreachMetrics
from src.utils.analytics import AnalyticsManager


@pytest.fixture
def analytics(db):
    return AnalyticsManager(db)


def test_campaign_metrics_report_a_success_rate(analytics):
    campaign_id = analytics.create_campaign("Q3", description="test")
    analytics.log_outreach_metrics(campaign_id, 10, 7, 9, customer_satisfaction=4.0)

    from src.database import OutreachRepository

    OutreachRepository(analytics.db).update_campaign_totals(
        campaign_id, total_customers=10, successful_calls=7, failed_calls=3, emails_sent=9
    )

    metrics = analytics.get_campaign_metrics(campaign_id)
    assert metrics["call_success_rate"] == 70.0
    assert metrics["emails_sent"] == 9


def test_metrics_for_a_missing_campaign(analytics):
    assert analytics.get_campaign_metrics(999_999) is None


def test_success_rate_is_zero_when_no_calls_were_made(analytics):
    campaign_id = analytics.create_campaign("Empty")
    assert analytics.get_campaign_metrics(campaign_id)["call_success_rate"] == 0.0


def test_zero_initiated_calls_do_not_divide_by_zero(analytics, db):
    campaign_id = analytics.create_campaign("Empty")
    assert analytics.log_outreach_metrics(campaign_id, 0, 0, 0) is True
    with db.session_scope() as session:
        assert session.query(OutreachMetrics).one().call_success_rate == 0.0


def test_performance_summary_aggregates_the_window(analytics):
    campaign_id = analytics.create_campaign("Q3")
    analytics.log_outreach_metrics(campaign_id, 10, 5, 8, customer_satisfaction=4.0)
    analytics.log_outreach_metrics(campaign_id, 10, 9, 10, customer_satisfaction=5.0)

    summary = analytics.get_performance_summary(days=30)
    assert summary["total_calls_initiated"] == 20
    assert summary["calls_completed"] == 14
    assert summary["overall_success_rate"] == 70.0
    assert summary["avg_customer_satisfaction"] == 4.5


def test_performance_summary_excludes_older_rows(analytics, db):
    campaign_id = analytics.create_campaign("Q3")
    with db.session_scope() as session:
        session.add(
            OutreachMetrics(
                campaign_id=campaign_id,
                metric_date=datetime.utcnow() - timedelta(days=90),
                calls_initiated=100,
                calls_completed=100,
            )
        )
    assert analytics.get_performance_summary(days=30) is None
    assert analytics.get_performance_summary(days=120)["total_calls_initiated"] == 100


def test_performance_summary_can_be_scoped_to_one_campaign(analytics):
    first = analytics.create_campaign("first")
    second = analytics.create_campaign("second")
    analytics.log_outreach_metrics(first, 4, 4, 4)
    analytics.log_outreach_metrics(second, 6, 1, 1)

    assert analytics.get_performance_summary(campaign_id=first)["total_calls_initiated"] == 4


def test_performance_summary_without_metrics(analytics):
    assert analytics.get_performance_summary(days=30) is None
