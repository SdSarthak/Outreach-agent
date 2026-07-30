"""Campaign analytics and metrics tracking."""

import logging
from datetime import datetime, timedelta

from src.database import Campaign, DatabaseManager, OutreachMetrics

logger = logging.getLogger(__name__)


class AnalyticsManager:
    """Creates campaigns and aggregates their outreach metrics."""

    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager

    def create_campaign(self, name: str, description: str = None) -> int:
        """Create a campaign and return its id, or None on failure."""
        try:
            with self.db.session_scope() as session:
                campaign = Campaign(name=name, description=description)
                session.add(campaign)
                session.flush()
                campaign_id = campaign.id
            logger.info("Campaign created: %s", campaign_id)
            return campaign_id
        except Exception as exc:
            logger.error("Error creating campaign: %s", exc)
            return None

    def get_campaign_metrics(self, campaign_id: int) -> dict:
        """Metrics for a single campaign, or None when it does not exist."""
        try:
            with self.db.session_scope() as session:
                campaign = session.get(Campaign, campaign_id)
                if not campaign:
                    logger.warning("Campaign %s not found", campaign_id)
                    return None

                successful = campaign.successful_calls or 0
                failed = campaign.failed_calls or 0
                total_calls = successful + failed
                success_rate = (successful / total_calls * 100) if total_calls else 0.0

                return {
                    "campaign_id": campaign.id,
                    "campaign_name": campaign.name,
                    "total_customers": campaign.total_customers or 0,
                    "successful_calls": successful,
                    "failed_calls": failed,
                    "call_success_rate": round(success_rate, 2),
                    "emails_sent": campaign.emails_sent or 0,
                    "start_date": campaign.start_date.isoformat() if campaign.start_date else None,
                    "end_date": campaign.end_date.isoformat() if campaign.end_date else None,
                }
        except Exception as exc:
            logger.error("Error getting campaign metrics: %s", exc)
            return None

    def log_outreach_metrics(
        self,
        campaign_id: int,
        calls_initiated: int,
        calls_completed: int,
        emails_sent: int,
        customer_satisfaction: float = 0.0,
    ) -> bool:
        """Append a metrics row for a campaign."""
        try:
            success_rate = (calls_completed / calls_initiated * 100) if calls_initiated else 0.0
            with self.db.session_scope() as session:
                session.add(
                    OutreachMetrics(
                        campaign_id=campaign_id,
                        metric_date=datetime.utcnow(),
                        calls_initiated=calls_initiated,
                        calls_completed=calls_completed,
                        call_success_rate=success_rate,
                        emails_sent=emails_sent,
                        customer_satisfaction=customer_satisfaction,
                    )
                )
            logger.info("Metrics logged for campaign %s", campaign_id)
            return True
        except Exception as exc:
            logger.error("Error logging metrics: %s", exc)
            return False

    def get_performance_summary(self, campaign_id: int = None, days: int = 30) -> dict:
        """Aggregate metrics over a rolling window.

        Returns None when no metrics were recorded in the period.
        """
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            with self.db.session_scope() as session:
                query = session.query(OutreachMetrics).filter(
                    OutreachMetrics.metric_date >= cutoff_date
                )
                if campaign_id:
                    query = query.filter(OutreachMetrics.campaign_id == campaign_id)
                metrics = query.all()

                if not metrics:
                    logger.info("No metrics recorded in the last %s days", days)
                    return None

                total_calls = sum(m.calls_initiated or 0 for m in metrics)
                completed_calls = sum(m.calls_completed or 0 for m in metrics)
                emails_sent = sum(m.emails_sent or 0 for m in metrics)
                avg_satisfaction = sum(m.customer_satisfaction or 0 for m in metrics) / len(metrics)
                success_rate = (completed_calls / total_calls * 100) if total_calls else 0.0

                return {
                    "period_days": days,
                    "total_calls_initiated": total_calls,
                    "calls_completed": completed_calls,
                    "overall_success_rate": round(success_rate, 2),
                    "emails_sent": emails_sent,
                    "avg_customer_satisfaction": round(avg_satisfaction, 2),
                }
        except Exception as exc:
            logger.error("Error getting performance summary: %s", exc)
            return None
