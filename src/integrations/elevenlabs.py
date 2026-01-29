import os
from elevenlabs import ElevenLabs
from elevenlabs.client import ElevenLabs as ElevenLabsClient
import logging

logger = logging.getLogger(__name__)

class ElevenLabsIntegration:
    """ElevenLabs Conversational AI Integration"""
    
    def __init__(self):
        self.api_key = os.getenv("ELEVENLABS_API_KEY")
        self.agent_id = os.getenv("ELEVENLABS_AGENT_ID")
        self.client = ElevenLabsClient(api_key=self.api_key)
        
        if not self.api_key:
            logger.warning("ELEVENLABS_API_KEY not set")
        if not self.agent_id:
            logger.warning("ELEVENLABS_AGENT_ID not set")
    
    def create_conversation(self, phone_number: str, context: dict) -> dict:
        """
        Create a new conversational AI session
        
        Args:
            phone_number: Customer phone number
            context: Context data for the conversation
            
        Returns:
            dict with conversation session details
        """
        try:
            # This would integrate with ElevenLabs Conversational AI API
            # Currently placeholder for the actual API call
            logger.info(f"Creating conversation for {phone_number}")
            
            conversation_config = {
                "agent_id": self.agent_id,
                "phone_number": phone_number,
                "custom_variables": context,
                "language": "en"
            }
            
            return conversation_config
        except Exception as e:
            logger.error(f"Error creating conversation: {str(e)}")
            raise
    
    def inject_context_variables(self, context: dict) -> dict:
        """
        Inject customer context variables for personalization
        
        Args:
            context: Customer context data
            
        Returns:
            Formatted context for ElevenLabs
        """
        formatted_context = {
            "customer_name": context.get("name"),
            "company": context.get("company"),
            "engagement_history": context.get("engagement_history"),
            "key_talking_points": context.get("talking_points"),
            "tone": context.get("tone", "professional"),
            "previous_interactions": context.get("previous_interactions", [])
        }
        return formatted_context
    
    def get_conversation_status(self, conversation_id: str) -> dict:
        """Get status of ongoing conversation"""
        try:
            # Placeholder for actual API call to get conversation status
            logger.info(f"Fetching status for conversation {conversation_id}")
            return {"conversation_id": conversation_id, "status": "active"}
        except Exception as e:
            logger.error(f"Error getting conversation status: {str(e)}")
            raise
    
    def end_conversation(self, conversation_id: str) -> dict:
        """End a conversation session"""
        try:
            logger.info(f"Ending conversation {conversation_id}")
            return {"conversation_id": conversation_id, "ended": True}
        except Exception as e:
            logger.error(f"Error ending conversation: {str(e)}")
            raise
