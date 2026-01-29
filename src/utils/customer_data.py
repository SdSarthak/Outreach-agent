import json
from typing import List, Dict, Any
from src.database import DatabaseManager, Customer, Enrollment, Engagement, Feedback
import logging

logger = logging.getLogger(__name__)

class CustomerDataWorkflow:
    """Retrieve and aggregate customer data"""
    
    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager
    
    def get_customer_context(self, customer_id: int) -> dict:
        """
        Get comprehensive customer context for outreach
        
        Args:
            customer_id: Customer ID
            
        Returns:
            Dictionary with aggregated customer data
        """
        try:
            session = self.db.get_session()
            
            # Get customer details
            customer = session.query(Customer).filter(Customer.id == customer_id).first()
            if not customer:
                logger.warning(f"Customer {customer_id} not found")
                return None
            
            # Get enrollment data
            enrollments = session.query(Enrollment).filter(
                Enrollment.customer_id == customer_id
            ).all()
            
            # Get engagement data
            engagements = session.query(Engagement).filter(
                Engagement.customer_id == customer_id
            ).order_by(Engagement.engagement_date.desc()).limit(10).all()
            
            # Get feedback
            feedbacks = session.query(Feedback).filter(
                Feedback.customer_id == customer_id
            ).order_by(Feedback.feedback_date.desc()).limit(5).all()
            
            # Aggregate context
            context = {
                "customer_id": customer.id,
                "name": customer.name,
                "email": customer.email,
                "phone": customer.phone,
                "company": customer.company,
                "industry": customer.industry,
                "engagement_score": customer.engagement_score,
                "enrollments": [
                    {
                        "product": e.product,
                        "status": e.status,
                        "tier": e.tier,
                        "enrollment_date": e.enrollment_date.isoformat()
                    }
                    for e in enrollments
                ],
                "recent_engagements": [
                    {
                        "type": e.engagement_type,
                        "date": e.engagement_date.isoformat(),
                        "value": e.value
                    }
                    for e in engagements
                ],
                "feedback_history": [
                    {
                        "text": f.feedback_text,
                        "sentiment": f.sentiment,
                        "rating": f.rating,
                        "category": f.category
                    }
                    for f in feedbacks
                ]
            }
            
            session.close()
            return context
        except Exception as e:
            logger.error(f"Error getting customer context: {str(e)}")
            return None
    
    def get_batch_customer_contexts(self, customer_ids: List[int]) -> List[dict]:
        """Get contexts for multiple customers"""
        contexts = []
        for customer_id in customer_ids:
            context = self.get_customer_context(customer_id)
            if context:
                contexts.append(context)
        return contexts
    
    def export_context_to_json(self, context: dict, filename: str = None) -> str:
        """Export context as JSON"""
        try:
            json_str = json.dumps(context, indent=2, default=str)
            if filename:
                with open(filename, 'w') as f:
                    f.write(json_str)
                logger.info(f"Context exported to {filename}")
            return json_str
        except Exception as e:
            logger.error(f"Error exporting context: {str(e)}")
            return None
