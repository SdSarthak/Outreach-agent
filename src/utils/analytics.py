import logging
from datetime import datetime, timedelta
from typing import List
from src.database import DatabaseManager, CallRecord, EmailRecord, Campaign, OutreachMetrics

logger = logging.getLogger(__name__)

class AnalyticsManager:
    """Campaign analytics and metrics tracking"""
    
    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager
    
    def create_campaign(self, name: str, description: str = None) -> int:
        """Create a new campaign"""
        try:
            session = self.db.get_session()
            campaign = Campaign(
                name=name,
                description=description
            )
            session.add(campaign)
            session.commit()
            campaign_id = campaign.id
            session.close()
            logger.info(f"Campaign created: {campaign_id}")
            return campaign_id
        except Exception as e:
            logger.error(f"Error creating campaign: {str(e)}")
            return None
    
    def get_campaign_metrics(self, campaign_id: int) -> dict:
        """Get metrics for a campaign"""
        try:
            session = self.db.get_session()
            
            campaign = session.query(Campaign).filter(Campaign.id == campaign_id).first()
            if not campaign:
                return None
            
            # Calculate call success rate
            total_calls = campaign.successful_calls + campaign.failed_calls
            success_rate = (campaign.successful_calls / total_calls * 100) if total_calls > 0 else 0
            
            metrics = {
                "campaign_id": campaign.id,
                "campaign_name": campaign.name,
                "total_customers": campaign.total_customers,
                "successful_calls": campaign.successful_calls,
                "failed_calls": campaign.failed_calls,
                "call_success_rate": round(success_rate, 2),
                "emails_sent": campaign.emails_sent,
                "start_date": campaign.start_date.isoformat(),
                "end_date": campaign.end_date.isoformat() if campaign.end_date else None
            }
            
            session.close()
            return metrics
        except Exception as e:
            logger.error(f"Error getting campaign metrics: {str(e)}")
            return None
    
    def log_outreach_metrics(self, campaign_id: int, calls_initiated: int, 
                            calls_completed: int, emails_sent: int, 
                            customer_satisfaction: float = 0.0) -> bool:
        """Log outreach metrics for a campaign"""
        try:
            session = self.db.get_session()
            
            call_success_rate = (calls_completed / calls_initiated * 100) if calls_initiated > 0 else 0
            
            metric = OutreachMetrics(
                campaign_id=campaign_id,
                metric_date=datetime.utcnow(),
                calls_initiated=calls_initiated,
                calls_completed=calls_completed,
                call_success_rate=call_success_rate,
                emails_sent=emails_sent,
                customer_satisfaction=customer_satisfaction
            )
            
            session.add(metric)
            session.commit()
            session.close()
            
            logger.info(f"Metrics logged for campaign {campaign_id}")
            return True
        except Exception as e:
            logger.error(f"Error logging metrics: {str(e)}")
            return False
    
    def get_performance_summary(self, campaign_id: int = None, days: int = 30) -> dict:
        """Get performance summary for period"""
        try:
            session = self.db.get_session()
            
            # Filter by date
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            
            query = session.query(OutreachMetrics).filter(
                OutreachMetrics.metric_date >= cutoff_date
            )
            
            if campaign_id:
                query = query.filter(OutreachMetrics.campaign_id == campaign_id)
            
            metrics = query.all()
            
            if not metrics:
                return None
            
            # Aggregate metrics
            total_calls = sum(m.calls_initiated for m in metrics)
            completed_calls = sum(m.calls_completed for m in metrics)
            emails_sent = sum(m.emails_sent for m in metrics)
            avg_satisfaction = sum(m.customer_satisfaction for m in metrics) / len(metrics)
            overall_success_rate = (completed_calls / total_calls * 100) if total_calls > 0 else 0
            
            summary = {
                "period_days": days,
                "total_calls_initiated": total_calls,
                "calls_completed": completed_calls,
                "overall_success_rate": round(overall_success_rate, 2),
                "emails_sent": emails_sent,
                "avg_customer_satisfaction": round(avg_satisfaction, 2)
            }
            
            session.close()
            return summary
        except Exception as e:
            logger.error(f"Error getting performance summary: {str(e)}")
            return None
