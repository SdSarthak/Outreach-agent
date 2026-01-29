from crewai import Agent
from src.integrations import ElevenLabsIntegration, TwilioIntegration
import logging

logger = logging.getLogger(__name__)

class CallAgent:
    """Agent for executing voice calls with AI"""
    
    def __init__(self):
        self.agent = Agent(
            role="Voice Communication Executor",
            goal="Execute professional voice calls with personalized context and guidance",
            backstory="Experienced communication specialist managing outbound calls. "
                     "You deliver calls with confidence, adapt to customer responses, and maintain professionalism.",
            verbose=True
        )
        self.elevenlabs = ElevenLabsIntegration()
        self.twilio = TwilioIntegration()
    
    def initiate_call(self, customer_data: dict, call_guidance: dict) -> dict:
        """
        Initiate a call to a customer
        
        Args:
            customer_data: Customer contact and context information
            call_guidance: Guidance from Insight Agent
            
        Returns:
            Call execution details with tracking IDs
        """
        try:
            phone_number = customer_data.get("phone")
            customer_name = customer_data.get("name")
            customer_id = customer_data.get("customer_id")
            
            logger.info(f"Initiating call to {customer_name} ({phone_number})")
            
            # Create ElevenLabs conversation context
            context = self.elevenlabs.inject_context_variables({
                "name": customer_name,
                "company": customer_data.get("company"),
                "engagement_history": customer_data.get("recent_engagements"),
                "talking_points": call_guidance.get("key_talking_points"),
                "tone": call_guidance.get("tone"),
                "previous_interactions": customer_data.get("feedback_history")
            })
            
            # Create conversation session
            conversation = self.elevenlabs.create_conversation(phone_number, context)
            
            # Initiate Twilio call
            callback_url = self._get_callback_url()
            call_sid = self.twilio.make_call(phone_number, callback_url)
            
            call_details = {
                "call_id": call_sid,
                "customer_id": customer_id,
                "customer_name": customer_name,
                "phone_number": phone_number,
                "status": "in_progress",
                "conversation_context": conversation,
                "start_time": self._get_current_time()
            }
            
            logger.info(f"Call initiated: {call_sid}")
            return call_details
        except Exception as e:
            logger.error(f"Error initiating call: {str(e)}")
            return None
    
    def monitor_call(self, call_sid: str) -> dict:
        """
        Monitor ongoing call
        
        Args:
            call_sid: Twilio call SID
            
        Returns:
            Current call status
        """
        try:
            status = self.twilio.get_call_status(call_sid)
            logger.info(f"Call status: {status}")
            return status
        except Exception as e:
            logger.error(f"Error monitoring call: {str(e)}")
            return None
    
    def end_call(self, call_sid: str) -> bool:
        """
        End an ongoing call
        
        Args:
            call_sid: Twilio call SID
            
        Returns:
            True if successful
        """
        try:
            success = self.twilio.end_call(call_sid)
            logger.info(f"Call ended: {call_sid}")
            return success
        except Exception as e:
            logger.error(f"Error ending call: {str(e)}")
            return False
    
    def get_call_transcript(self, call_sid: str) -> str:
        """
        Get transcript from ElevenLabs
        
        Args:
            call_sid: Twilio call SID
            
        Returns:
            Call transcript
        """
        try:
            # In production, would fetch from ElevenLabs API
            logger.info(f"Fetching transcript for call {call_sid}")
            return None
        except Exception as e:
            logger.error(f"Error getting transcript: {str(e)}")
            return None
    
    def _get_callback_url(self) -> str:
        """Get webhook callback URL for call events"""
        # This would typically come from configuration
        return "https://your-domain.com/webhooks/twilio/call"
    
    def _get_current_time(self) -> str:
        """Get current timestamp"""
        from datetime import datetime
        return datetime.utcnow().isoformat()
