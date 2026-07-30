"""Agent that analyses call outcomes and decides on the follow-up."""

import logging
import re

from src.agents.base import build_agent
from src.database import OutreachRepository

logger = logging.getLogger(__name__)

POSITIVE_TERMS = (
    "great", "love", "excellent", "perfect", "interested", "helpful",
    "sounds good", "works", "yes", "thanks", "appreciate",
)
NEGATIVE_TERMS = (
    "problem", "issue", "not interested", "no thanks", "too expensive",
    "cancel", "unhappy", "frustrated", "remove me", "stop calling",
)


class DecisionAgent:
    """Scores a call and recommends the next action."""

    def __init__(self, db_manager=None, repository: OutreachRepository = None):
        self.agent = build_agent(
            "decision_agent",
            role="Call Monitoring and Follow-up Coordinator",
            goal="Monitor call outcomes and determine appropriate follow-up actions",
            backstory=(
                "Strategic analyst monitoring customer interactions. You analyze call "
                "outcomes and recommend next steps to maximize engagement."
            ),
        )
        self.db = db_manager
        self.repository = repository or (OutreachRepository(db_manager) if db_manager else None)

    def analyze_call_outcome(self, call_data: dict) -> dict:
        """Score a completed call and recommend a follow-up.

        Always returns an analysis dict so the pipeline can continue even when
        the call produced very little data.
        """
        call_data = call_data or {}

        sentiment = self._analyze_sentiment(call_data)
        success = self._assess_success(call_data)
        recommendation = self._recommend_followup(call_data, success)

        analysis = {
            "call_id": call_data.get("call_id"),
            "conversation_id": call_data.get("conversation_id"),
            "customer_id": call_data.get("customer_id"),
            "call_status": call_data.get("status"),
            "duration": call_data.get("duration", 0),
            "sentiment_analysis": sentiment,
            "success_indicator": success,
            "follow_up_recommendation": recommendation,
            "next_action": self._determine_next_action(recommendation),
            "priority_level": self._assess_priority(call_data, success),
        }

        logger.info(
            "Analyzed call %s: sentiment=%s score=%s",
            analysis["call_id"],
            sentiment["overall"],
            success["success_score"],
        )
        return analysis

    # ---------------------------------------------------------------- scoring
    def _analyze_sentiment(self, call_data: dict) -> dict:
        """Keyword-based sentiment read of the customer's turns."""
        transcript = call_data.get("transcript") or ""
        customer_speech = self._customer_speech(transcript).lower()

        positives = sum(1 for term in POSITIVE_TERMS if term in customer_speech)
        negatives = sum(1 for term in NEGATIVE_TERMS if term in customer_speech)

        if not customer_speech:
            sentiment, confidence = "unknown", 0.0
        elif positives > negatives:
            sentiment = "positive"
            confidence = min(0.5 + 0.1 * (positives - negatives), 0.95)
        elif negatives > positives:
            sentiment = "negative"
            confidence = min(0.5 + 0.1 * (negatives - positives), 0.95)
        else:
            sentiment, confidence = "neutral", 0.5

        return {
            "overall": sentiment,
            "confidence": round(confidence, 2),
            "positive_signals": positives,
            "negative_signals": negatives,
            "key_phrases": self._extract_key_phrases(transcript),
        }

    def _assess_success(self, call_data: dict) -> dict:
        """Score the call out of 100 from status, duration and engagement."""
        status = str(call_data.get("status", "unknown")).lower()
        duration = call_data.get("duration") or 0
        score = 0
        indicators = []

        if status == "completed":
            score += 30
            indicators.append("Call completed")

        if duration >= 120:
            score += 40
            indicators.append("Adequate call duration")
        elif duration >= 60:
            score += 20
            indicators.append("Short but substantive call")

        if call_data.get("customer_engaged"):
            score += 20
            indicators.append("Customer was engaged")

        if call_data.get("call_successful") == "success":
            score += 10
            indicators.append("Provider marked the call successful")

        score = min(score, 100)
        return {"success_score": score, "indicators": indicators, "successful": score >= 60}

    def _recommend_followup(self, call_data: dict, success: dict = None) -> dict:
        """Pick the follow-up channel, priority and timing."""
        success = success or self._assess_success(call_data)
        score = success.get("success_score", 0)

        if str(call_data.get("status", "")).lower() == "failed":
            return {
                "type": "retry",
                "priority": "high",
                "timing": "immediate",
                "reason": "Initial call attempt failed",
            }
        if score < 40:
            return {
                "type": "follow_email",
                "priority": "high",
                "timing": "next_business_day",
                "reason": "Low engagement during call",
            }
        if score < 70:
            return {
                "type": "follow_email_and_meeting",
                "priority": "medium",
                "timing": "within_3_days",
                "reason": "Moderate engagement, schedule next meeting",
            }
        return {
            "type": "follow_meeting",
            "priority": "high",
            "timing": "within_week",
            "reason": "Strong engagement, move to next phase",
        }

    def _determine_next_action(self, recommendation: dict) -> str:
        action_map = {
            "retry": "Schedule call retry within 24 hours",
            "follow_email": "Send personalized follow-up email",
            "follow_email_and_meeting": "Send email and request meeting",
            "follow_meeting": "Send email and schedule meeting",
        }
        return action_map.get((recommendation or {}).get("type"), "Log interaction and review")

    def _assess_priority(self, call_data: dict, success: dict = None) -> str:
        success = success or self._assess_success(call_data)
        if not success.get("successful"):
            return "high"
        if (call_data.get("engagement_score") or 0) > 0.7:
            return "high"
        return "medium"

    # -------------------------------------------------------------- transcript
    @staticmethod
    def _customer_speech(transcript: str) -> str:
        """Isolate the customer's lines from a `Role: text` transcript.

        Falls back to the whole transcript when it carries no role prefixes.
        """
        if not transcript:
            return ""
        customer_lines = [
            line.split(":", 1)[1].strip()
            for line in transcript.splitlines()
            if ":" in line and line.split(":", 1)[0].strip().lower() in {"user", "customer"}
        ]
        return " ".join(customer_lines) if customer_lines else transcript

    @staticmethod
    def _extract_key_phrases(transcript: str) -> list:
        """Longest few sentences, used as a quick human-readable digest."""
        if not transcript:
            return []
        sentences = [
            re.sub(r"^\w+:\s*", "", sentence).strip()
            for sentence in re.split(r"[.!?\n]", transcript)
        ]
        sentences = [sentence for sentence in sentences if len(sentence) > 10]
        return sorted(sentences, key=len, reverse=True)[:3]

    # ------------------------------------------------------------- persistence
    def log_decision(self, call_record_id: int, analysis: dict) -> bool:
        """Persist the analysis against a stored call record."""
        if not self.repository or not call_record_id or not analysis:
            return False

        return self.repository.update_call_record(
            call_record_id,
            status=analysis.get("call_status"),
            duration_seconds=analysis.get("duration"),
            sentiment=(analysis.get("sentiment_analysis") or {}).get("overall"),
            success_score=(analysis.get("success_indicator") or {}).get("success_score"),
            next_action=analysis.get("next_action"),
            priority=analysis.get("priority_level"),
        )
