from crewai import Agent
from src.integrations import GmailIntegration
from src.database import DatabaseManager, EmailRecord
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class EmailAgent:
    """Agent for drafting and sending follow-up emails"""
    
    def __init__(self, db_manager: DatabaseManager = None):
        self.agent = Agent(
            role="Follow-up Email Composer",
            goal="Draft and send personalized follow-up emails that maintain engagement",
            backstory="Professional communicator crafting compelling follow-up messages. "
                     "You create emails that are personal, relevant, and drive action.",
            verbose=True
        )
        self.gmail = GmailIntegration()
        self.db = db_manager
    
    def draft_followup_email(self, customer_data: dict, call_analysis: dict) -> dict:
        """
        Draft a personalized follow-up email
        
        Args:
            customer_data: Customer information
            call_analysis: Analysis from Decision Agent
            
        Returns:
            Email draft with subject and body
        """
        try:
            email_type = call_analysis.get("follow_up_recommendation", {}).get("type")
            
            if email_type == "retry":
                email = self._draft_retry_email(customer_data, call_analysis)
            elif email_type == "follow_email_and_meeting":
                email = self._draft_meeting_request_email(customer_data, call_analysis)
            else:
                email = self._draft_followup_email(customer_data, call_analysis)
            
            logger.info(f"Drafted email for customer {customer_data.get('customer_id')}")
            return email
        except Exception as e:
            logger.error(f"Error drafting email: {str(e)}")
            return None
    
    def send_email(self, customer_email: str, subject: str, body: str) -> str:
        """
        Send email to customer
        
        Args:
            customer_email: Recipient email address
            subject: Email subject
            body: Email body
            
        Returns:
            Message ID if successful
        """
        try:
            message_id = self.gmail.send_email(customer_email, subject, body, html=False)
            logger.info(f"Email sent to {customer_email}: {message_id}")
            return message_id
        except Exception as e:
            logger.error(f"Error sending email: {str(e)}")
            return None
    
    def _draft_retry_email(self, customer_data: dict, call_analysis: dict) -> dict:
        """Draft email for retry scenario"""
        name = customer_data.get("name", "there")
        company = customer_data.get("company", "your organization")
        
        subject = f"Let's Connect - {name}"
        body = f"""Hi {name},

I tried reaching you earlier but wasn't able to connect. I'd love to continue our conversation about how we can help {company} achieve its goals.

Would you have 15 minutes for a quick call? I'm available at your convenience.

Looking forward to connecting with you soon.

Best regards,
AI Outreach Team"""
        
        return {
            "subject": subject,
            "body": body,
            "type": "retry",
            "customer_id": customer_data.get("customer_id"),
            "customer_email": customer_data.get("email")
        }
    
    def _draft_meeting_request_email(self, customer_data: dict, call_analysis: dict) -> dict:
        """Draft email requesting a meeting"""
        name = customer_data.get("name", "there")
        company = customer_data.get("company", "your organization")
        
        subject = f"Let's Schedule a Meeting - {name}"
        body = f"""Hi {name},

Thank you for our conversation earlier. I really appreciated learning more about {company} and your goals.

Based on our discussion, I think there are some great opportunities we can explore together. I'd like to schedule a follow-up meeting to discuss potential solutions.

Are you available next week? I'm flexible with timing.

Key topics we'll cover:
- Your current priorities and challenges
- How we can add value
- Next steps and timeline

Looking forward to our discussion.

Best regards,
AI Outreach Team"""
        
        return {
            "subject": subject,
            "body": body,
            "type": "meeting_request",
            "customer_id": customer_data.get("customer_id"),
            "customer_email": customer_data.get("email")
        }
    
    def _draft_followup_email(self, customer_data: dict, call_analysis: dict) -> dict:
        """Draft standard follow-up email"""
        name = customer_data.get("name", "there")
        company = customer_data.get("company", "your organization")
        
        subject = f"Thank You for Your Time - {name}"
        body = f"""Hi {name},

Thank you for taking the time to speak with us today. I enjoyed our conversation about {company} and the challenges you're facing.

As promised, I've attached some resources that might be helpful based on our discussion. Please feel free to reach out if you have any questions.

I'd love to stay in touch and continue supporting your success.

Best regards,
AI Outreach Team"""
        
        return {
            "subject": subject,
            "body": body,
            "type": "standard",
            "customer_id": customer_data.get("customer_id"),
            "customer_email": customer_data.get("email")
        }
    
    def log_email(self, customer_id: int, call_record_id: int, subject: str, 
                  body: str, message_id: str = None, status: str = "sent") -> bool:
        """Log email to database"""
        try:
            if self.db:
                session = self.db.get_session()
                
                email_record = EmailRecord(
                    customer_id=customer_id,
                    call_record_id=call_record_id,
                    subject=subject,
                    body=body,
                    message_id=message_id,
                    status=status
                )
                
                session.add(email_record)
                session.commit()
                session.close()
                
                logger.info(f"Email logged for customer {customer_id}")
                return True
        except Exception as e:
            logger.error(f"Error logging email: {str(e)}")
            return False
        
        return False
