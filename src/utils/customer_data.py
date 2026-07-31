"""Retrieve and aggregate the customer context used to personalize outreach."""

import json
import logging
from typing import List

from src.database import Customer, DatabaseManager, Engagement, Enrollment, Feedback

logger = logging.getLogger(__name__)


class CustomerDataWorkflow:
    """Assembles a single view of a customer from the database."""

    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager

    def get_customer_context(self, customer_id: int) -> dict:
        """Aggregate profile, enrollments, engagements and feedback.

        Returns None when the customer does not exist.
        """
        if not customer_id:
            logger.warning("Cannot load a customer context without an id")
            return None
        try:
            with self.db.session_scope() as session:
                customer = session.get(Customer, customer_id)
                if not customer:
                    logger.warning("Customer %s not found", customer_id)
                    return None

                enrollments = (
                    session.query(Enrollment)
                    .filter(Enrollment.customer_id == customer_id)
                    .all()
                )
                engagements = (
                    session.query(Engagement)
                    .filter(Engagement.customer_id == customer_id)
                    .order_by(Engagement.engagement_date.desc())
                    .limit(10)
                    .all()
                )
                feedbacks = (
                    session.query(Feedback)
                    .filter(Feedback.customer_id == customer_id)
                    .order_by(Feedback.feedback_date.desc())
                    .limit(5)
                    .all()
                )

                return {
                    "customer_id": customer.id,
                    "name": customer.name,
                    "email": customer.email,
                    "phone": customer.phone,
                    "company": customer.company,
                    "industry": customer.industry,
                    "engagement_score": customer.engagement_score or 0.0,
                    "enrollments": [
                        {
                            "product": e.product,
                            "status": e.status,
                            "tier": e.tier,
                            "enrollment_date": (
                                e.enrollment_date.isoformat() if e.enrollment_date else None
                            ),
                        }
                        for e in enrollments
                    ],
                    "recent_engagements": [
                        {
                            "type": e.engagement_type,
                            "date": e.engagement_date.isoformat() if e.engagement_date else None,
                            "value": e.value,
                        }
                        for e in engagements
                    ],
                    "feedback_history": [
                        {
                            "text": f.feedback_text,
                            "sentiment": f.sentiment,
                            "rating": f.rating,
                            "category": f.category,
                        }
                        for f in feedbacks
                    ],
                }
        except Exception as exc:
            logger.error("Error getting context for customer %s: %s", customer_id, exc)
            return None

    def get_batch_customer_contexts(self, customer_ids: List[int]) -> List[dict]:
        """Contexts for several customers, skipping any that cannot be loaded."""
        contexts = []
        for customer_id in customer_ids or []:
            context = self.get_customer_context(customer_id)
            if context:
                contexts.append(context)
        return contexts

    def export_context_to_json(self, context: dict, filename: str = None) -> str:
        """Serialize a context to JSON, optionally writing it to disk."""
        try:
            json_str = json.dumps(context, indent=2, default=str)
            if filename:
                with open(filename, "w", encoding="utf-8") as handle:
                    handle.write(json_str)
                logger.info("Context exported to %s", filename)
            return json_str
        except (TypeError, ValueError, OSError) as exc:
            logger.error("Error exporting context: %s", exc)
            return None
