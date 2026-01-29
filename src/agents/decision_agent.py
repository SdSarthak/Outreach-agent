from crewai import Agent
from src.database import DatabaseManager, CallRecord
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class DecisionAgent:
    """Agent for monitoring calls and recommending follow-up actions"""
    
    def __init__(self, db_manager: DatabaseManager = None):
        self.agent = Agent(
            role="Call Monitoring and Follow-up Coordinator",
            goal="Monitor call outcomes and determine appropriate follow-up actions",
            backstory="Strategic analyst monitoring customer interactions. "
                     "You analyze call outcomes and recommend next steps to maximize engagement.",
            verbose=True
        )
        self.db = db_manager
    
    def analyze_call_outcome(self, call_data: dict) -> dict:
        """
        Analyze call outcome and recommend next steps
        
        Args:
            call_data: Call execution and result data
            
        Returns:
            Analysis with recommendations
        """
        try:
            analysis = {
                "call_id": call_data.get("call_id"),
                "customer_id": call_data.get("customer_id"),
                "call_status": call_data.get("status"),
                "duration": call_data.get("duration"),
                "sentiment_analysis": self._analyze_sentiment(call_data),
                "success_indicator": self._assess_success(call_data),
                "follow_up_recommendation": self._recommend_followup(call_data),
                "next_action": self._determine_next_action(call_data),
                "priority_level": self._assess_priority(call_data)
            }
            
            logger.info(f"Analyzed call {call_data.get('call_id')}")
            return analysis
        except Exception as e:
            logger.error(f"Error analyzing call outcome: {str(e)}")
            return None
    
    def _analyze_sentiment(self, call_data: dict) -> dict:
        """Analyze sentiment from transcript"""
        transcript = call_data.get("transcript", "")
        
        # Simple sentiment analysis (in production, would use NLP)
        sentiment = "neutral"
        confidence = 0.5
        
        if any(word in transcript.lower() for word in ["great", "love", "excellent", "perfect"]):
            sentiment = "positive"
            confidence = 0.8
        elif any(word in transcript.lower() for word in ["problem", "issue", "not interested", "no"]):
            sentiment = "negative"
            confidence = 0.7
        
        return {
            "overall": sentiment,
            "confidence": confidence,
            "key_phrases": self._extract_key_phrases(transcript)
        }
    
    def _assess_success(self, call_data: dict) -> dict:
        """Assess call success"""
        status = call_data.get("status", "unknown")
        duration = call_data.get("duration", 0)
        
        # Success indicators
        success_score = 0
        indicators = []
        
        if status == "completed":
            success_score += 30
            indicators.append("Call completed")
        
        if duration and duration > 120:  # More than 2 minutes
            success_score += 40
            indicators.append("Adequate call duration")
        
        if call_data.get("customer_engaged"):
            success_score += 30
            indicators.append("Customer was engaged")
        
        return {
            "success_score": success_score,
            "indicators": indicators,
            "successful": success_score >= 60
        }
    
    def _recommend_followup(self, call_data: dict) -> dict:
        """Recommend follow-up action"""
        call_status = call_data.get("status")
        success_score = self._assess_success(call_data).get("success_score", 0)
        
        if call_status == "failed":
            return {
                "type": "retry",
                "priority": "high",
                "timing": "immediate",
                "reason": "Initial call attempt failed"
            }
        elif success_score < 40:
            return {
                "type": "follow_email",
                "priority": "high",
                "timing": "next_business_day",
                "reason": "Low engagement during call"
            }
        elif success_score < 70:
            return {
                "type": "follow_email_and_meeting",
                "priority": "medium",
                "timing": "within_3_days",
                "reason": "Moderate engagement, schedule next meeting"
            }
        else:
            return {
                "type": "follow_meeting",
                "priority": "high",
                "timing": "within_week",
                "reason": "Strong engagement, move to next phase"
            }
    
    def _determine_next_action(self, call_data: dict) -> str:
        """Determine the next action to take"""
        recommendation = self._recommend_followup(call_data)
        
        action_map = {
            "retry": "Schedule call retry within 24 hours",
            "follow_email": "Send personalized follow-up email",
            "follow_email_and_meeting": "Send email and request meeting",
            "follow_meeting": "Send email and schedule meeting"
        }
        
        return action_map.get(recommendation.get("type"), "Log interaction and review")
    
    def _assess_priority(self, call_data: dict) -> str:
        """Assess priority of follow-up"""
        success = self._assess_success(call_data)
        
        if not success.get("successful"):
            return "high"
        elif call_data.get("engagement_score", 0) > 0.7:
            return "high"
        else:
            return "medium"
    
    def _extract_key_phrases(self, transcript: str) -> list:
        """Extract key phrases from transcript"""
        # Placeholder for actual NLP extraction
        return [phrase.strip() for phrase in transcript.split('.') if len(phrase.strip()) > 10][:3]
    
    def log_decision(self, call_id: str, decision: dict) -> bool:
        """Log decision to database"""
        try:
            if self.db:
                session = self.db.get_session()
                call_record = session.query(CallRecord).filter(
                    CallRecord.twilio_call_sid == call_id
                ).first()
                
                if call_record:
                    call_record.updated_at = datetime.utcnow()
                    session.commit()
                    logger.info(f"Decision logged for call {call_id}")
                
                session.close()
            return True
        except Exception as e:
            logger.error(f"Error logging decision: {str(e)}")
            return False
