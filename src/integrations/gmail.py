import os
import logging
from google.oauth2.service_account import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials
from google_auth_httplib2 import AuthorizedHttp
from googleapiclient.discovery import build
from email.mime.text import MIMEText
import base64

logger = logging.getLogger(__name__)

class GmailIntegration:
    """Gmail API Integration for Email Follow-ups"""
    
    SCOPES = ['https://www.googleapis.com/auth/gmail.send']
    
    def __init__(self):
        self.gmail_address = os.getenv("GMAIL_ADDRESS")
        self.credentials_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
        self.service = None
        self._initialize_service()
    
    def _initialize_service(self):
        """Initialize Gmail API service"""
        try:
            if self.credentials_path and os.path.exists(self.credentials_path):
                credentials = Credentials.from_service_account_file(
                    self.credentials_path,
                    scopes=self.SCOPES
                )
                self.service = build('gmail', 'v1', credentials=credentials)
                logger.info("Gmail service initialized successfully")
            else:
                logger.warning("Gmail credentials not configured")
        except Exception as e:
            logger.error(f"Error initializing Gmail service: {str(e)}")
    
    def send_email(self, to_email: str, subject: str, body: str, html: bool = False) -> str:
        """
        Send an email via Gmail
        
        Args:
            to_email: Recipient email address
            subject: Email subject
            body: Email body content
            html: Whether body is HTML formatted
            
        Returns:
            Message ID if successful, None otherwise
        """
        try:
            if not self.service:
                logger.error("Gmail service not initialized")
                return None
            
            # Create message
            message = MIMEText(body, 'html' if html else 'plain')
            message['to'] = to_email
            message['from'] = self.gmail_address
            message['subject'] = subject
            
            # Encode message
            raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
            
            # Send message
            result = self.service.users().messages().send(
                userId='me',
                body={'raw': raw_message}
            ).execute()
            
            logger.info(f"Email sent to {to_email}: {result['id']}")
            return result['id']
        except Exception as e:
            logger.error(f"Error sending email: {str(e)}")
            return None
    
    def get_email_templates(self) -> list:
        """Get predefined email templates"""
        templates = {
            "follow_up": {
                "subject": "Following up on our recent conversation",
                "body": "Hi {customer_name},\n\nThank you for taking the time to speak with us today. "
                        "We discussed {key_topics} and would love to help you achieve your goals.\n\n"
                        "Next steps: {next_steps}\n\nBest regards"
            },
            "thank_you": {
                "subject": "Thank you for your time",
                "body": "Hi {customer_name},\n\nWe appreciate the opportunity to connect. "
                        "Your feedback regarding {feedback_topic} is valuable to us.\n\n"
                        "We'll be in touch soon.\n\nBest regards"
            },
            "proposal": {
                "subject": "Proposal for {company_name}",
                "body": "Hi {customer_name},\n\nBased on our discussion, we've prepared a tailored proposal "
                        "for {company_name}. Please find it attached.\n\n"
                        "Please review and let us know your thoughts.\n\nBest regards"
            }
        }
        return templates
    
    def format_email(self, template_name: str, variables: dict) -> tuple:
        """
        Format email using template and variables
        
        Args:
            template_name: Name of the template
            variables: Variables to substitute in template
            
        Returns:
            Tuple of (subject, body)
        """
        templates = self.get_email_templates()
        
        if template_name not in templates:
            logger.warning(f"Template {template_name} not found")
            return None, None
        
        template = templates[template_name]
        subject = template["subject"].format(**variables)
        body = template["body"].format(**variables)
        
        return subject, body
