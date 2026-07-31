"""Agent that turns customer context into strategic call guidance."""

import logging

from src.agents.base import build_agent

logger = logging.getLogger(__name__)


def _engagement_score(context: dict) -> float:
    """Engagement score as a float, tolerating missing or non-numeric values."""
    try:
        return float(context.get("engagement_score") or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _dicts(context: dict, key: str) -> list:
    """Return the dict entries stored under ``key``, ignoring anything else.

    Context can come straight from the database (where nullable columns show up
    as ``None``) or from a caller passing a hand-built payload, so every list
    read here has to survive both.
    """
    values = context.get(key) or []
    if isinstance(values, dict):
        values = [values]
    if not isinstance(values, (list, tuple)):
        return []
    return [value for value in values if isinstance(value, dict)]


class InsightAgent:
    """Agent for generating strategic call guidance and insights"""

    def __init__(self):
        self.agent = build_agent(
            "insight_agent",
            role="Strategic Call Guidance Provider",
            goal="Generate personalized call guidance and strategic insights based on customer data",
            backstory=(
                "Expert analyst specializing in customer engagement and communication "
                "strategies. You analyze customer data to glean insights and create "
                "tailored talking points."
            ),
        )

    def generate_call_guidance(self, customer_context: dict) -> dict:
        """
        Generate guidance for an outbound call

        Args:
            customer_context: Customer data and engagement history

        Returns:
            Call guidance with talking points and recommendations
        """
        if not customer_context or not isinstance(customer_context, dict):
            logger.warning("Cannot generate guidance without customer context")
            return None

        guidance = {
            "customer_id": customer_context.get("customer_id"),
            "customer_name": customer_context.get("name"),
            "company": customer_context.get("company"),
            "key_talking_points": self._generate_talking_points(customer_context),
            "tone": self._determine_tone(customer_context),
            "recommended_actions": self._recommend_actions(customer_context),
            "engagement_strategy": self._strategy_for_engagement(customer_context),
            "potential_objections": self._identify_objections(customer_context),
            "next_steps": self._plan_next_steps(customer_context),
        }

        logger.info("Generated guidance for customer %s", customer_context.get("customer_id"))
        return guidance
    
    def _generate_talking_points(self, context: dict) -> list:
        """Generate personalized talking points"""
        points = []
        
        # Industry-specific points
        if context.get("industry"):
            points.append(f"Discuss industry trends in {context['industry']}")
        
        # Engagement-based points
        if _engagement_score(context) > 0.7:
            points.append("Leverage high engagement history to deepen relationship")

        # Product/service points
        products = [str(e.get("product")) for e in _dicts(context, "enrollments") if e.get("product")]
        if products:
            points.append(f"Reference their current products: {', '.join(sorted(set(products)))}")

        # Feedback-based points
        sentiments = [f.get("sentiment") for f in _dicts(context, "feedback_history")]
        if "positive" in sentiments:
            points.append("Acknowledge positive feedback and build on successful areas")

        return points if points else ["Build rapport and understand customer needs"]

    def _determine_tone(self, context: dict) -> str:
        """Determine appropriate communication tone"""
        engagement = _engagement_score(context)

        if engagement > 0.8:
            return "collaborative and partnership-focused"
        elif engagement > 0.5:
            return "professional and solutions-oriented"
        else:
            return "friendly and consultative"
    
    def _recommend_actions(self, context: dict) -> list:
        """Recommend actions based on context"""
        actions = []

        if _engagement_score(context) > 0.6:
            actions.append("Schedule follow-up meeting")

        if not context.get("enrollments"):
            actions.append("Introduce key products/services")

        feedback_history = _dicts(context, "feedback_history")
        recent_feedback = feedback_history[0] if feedback_history else {}
        if recent_feedback.get("sentiment") == "negative":
            actions.append("Address concerns and offer solutions")
        
        return actions or ["Explore collaboration opportunities"]
    
    def _strategy_for_engagement(self, context: dict) -> str:
        """Determine engagement strategy"""
        recent_engagements = _dicts(context, "recent_engagements")

        if not recent_engagements:
            return "Re-engagement strategy: Reconnect and understand current situation"

        # `engagement_type` is nullable in the database, so it can arrive as None.
        engagement_type = str(recent_engagements[0].get("type") or "").lower()

        if "support" in engagement_type:
            return "Support expansion: Help resolve issues and introduce related services"
        elif "feature_usage" in engagement_type:
            return "Adoption strategy: Maximize value from existing products"
        else:
            return "Growth strategy: Identify expansion opportunities"
    
    def _identify_objections(self, context: dict) -> list:
        """Identify potential objections"""
        objections = []
        
        # `CustomerDataWorkflow` exposes the feedback body under "text".
        for f in _dicts(context, "feedback_history"):
            if f.get("sentiment") == "negative":
                concern = f.get("text") or f.get("feedback_text")
                if concern:
                    objections.append(f"Previous concern: {concern}")
        
        if not context.get("enrollments"):
            objections.append("Potential objection: Not familiar with our solutions")
        
        return objections or ["Price concerns", "Implementation complexity"]
    
    def _plan_next_steps(self, context: dict) -> list:
        """Plan next steps"""
        return [
            "Confirm availability for follow-up",
            "Send personalized follow-up email within 24 hours",
            "Schedule next interaction or meeting",
            "Log all details for future reference"
        ]
