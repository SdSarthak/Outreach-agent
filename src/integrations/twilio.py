import os
from twilio.rest import Client
import logging

logger = logging.getLogger(__name__)

class TwilioIntegration:
    """Twilio API Integration for Voice Calls"""
    
    def __init__(self):
        self.account_sid = os.getenv("TWILIO_ACCOUNT_SID")
        self.auth_token = os.getenv("TWILIO_AUTH_TOKEN")
        self.phone_number = os.getenv("TWILIO_PHONE_NUMBER")
        
        if self.account_sid and self.auth_token:
            self.client = Client(self.account_sid, self.auth_token)
        else:
            logger.warning("Twilio credentials not configured")
            self.client = None
    
    def make_call(self, to_number: str, callback_url: str) -> str:
        """
        Initiate an outbound call
        
        Args:
            to_number: Destination phone number
            callback_url: Webhook URL for handling call events
            
        Returns:
            Twilio call SID
        """
        try:
            if not self.client:
                logger.error("Twilio client not initialized")
                return None
            
            call = self.client.calls.create(
                to=to_number,
                from_=self.phone_number,
                url=callback_url
            )
            
            logger.info(f"Call initiated: {call.sid} to {to_number}")
            return call.sid
        except Exception as e:
            logger.error(f"Error making call: {str(e)}")
            raise
    
    def get_call_status(self, call_sid: str) -> dict:
        """
        Get the status of a call
        
        Args:
            call_sid: Twilio call SID
            
        Returns:
            Call status information
        """
        try:
            if not self.client:
                logger.error("Twilio client not initialized")
                return None
            
            call = self.client.calls(call_sid).fetch()
            return {
                "call_sid": call.sid,
                "status": call.status,
                "direction": call.direction,
                "duration": call.duration,
                "price": call.price
            }
        except Exception as e:
            logger.error(f"Error getting call status: {str(e)}")
            raise
    
    def end_call(self, call_sid: str) -> bool:
        """
        End an ongoing call
        
        Args:
            call_sid: Twilio call SID
            
        Returns:
            True if successful
        """
        try:
            if not self.client:
                logger.error("Twilio client not initialized")
                return False
            
            self.client.calls(call_sid).update(status="completed")
            logger.info(f"Call ended: {call_sid}")
            return True
        except Exception as e:
            logger.error(f"Error ending call: {str(e)}")
            return False
    
    def get_call_recording(self, call_sid: str) -> str:
        """
        Get recording URL for a call
        
        Args:
            call_sid: Twilio call SID
            
        Returns:
            Recording URL
        """
        try:
            if not self.client:
                logger.error("Twilio client not initialized")
                return None
            
            recordings = self.client.calls(call_sid).recordings.stream(limit=1)
            for recording in recordings:
                return recording.uri
            return None
        except Exception as e:
            logger.error(f"Error getting recording: {str(e)}")
            return None
