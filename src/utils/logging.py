import logging
import os
from datetime import datetime

def setup_logging():
    """Configure logging for the application"""
    
    log_level = os.getenv("LOG_LEVEL", "INFO")
    log_file = os.getenv("LOG_FILE", "logs/outreach_agent.log")
    
    # Create logs directory if it doesn't exist
    os.makedirs(os.path.dirname(log_file), exist_ok=True)
    
    # Configure logging format
    log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"
    
    # Configure root logger
    logging.basicConfig(
        level=getattr(logging, log_level),
        format=log_format,
        datefmt=date_format,
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()
        ]
    )
    
    logger = logging.getLogger(__name__)
    logger.info("Logging initialized")
    
    return logger


class CallLogger:
    """Specialized logger for call activities"""
    
    def __init__(self, call_id: str):
        self.call_id = call_id
        self.logger = logging.getLogger(f"call_{call_id}")
        self.start_time = datetime.utcnow()
    
    def log_event(self, event_type: str, details: dict):
        """Log a call-related event"""
        log_entry = {
            "call_id": self.call_id,
            "timestamp": datetime.utcnow().isoformat(),
            "event_type": event_type,
            "details": details
        }
        self.logger.info(f"Event: {log_entry}")
    
    def log_call_start(self, customer_name: str, phone_number: str):
        """Log call initiation"""
        self.log_event("call_started", {
            "customer": customer_name,
            "phone": phone_number
        })
    
    def log_call_status(self, status: str, metadata: dict = None):
        """Log call status update"""
        self.log_event("status_update", {
            "status": status,
            "metadata": metadata or {}
        })
    
    def log_call_end(self, duration: int, transcript: str = None):
        """Log call completion"""
        self.log_event("call_ended", {
            "duration_seconds": duration,
            "transcript_available": transcript is not None
        })
