"""Agent that drafts and sends personalized follow-up emails."""

import logging
import re

from src.agents.base import build_agent
from src.config import get_settings
from src.database import EmailStatus, OutreachRepository
from src.integrations import GmailIntegration

logger = logging.getLogger(__name__)

# Deliberately permissive: this only rejects addresses that Gmail would reject
# outright (no local part, no domain, whitespace or a stray header separator).
_ADDRESS_RE = re.compile(r"^[^@\s,;:<>]+@[^@\s,;:<>]+\.[^@\s,;:<>]+$")


def _is_plausible_address(address: str) -> bool:
    return bool(_ADDRESS_RE.match(address))


class EmailAgent:
    """Composes and delivers the follow-up email for a call."""

    def __init__(self, db_manager=None, gmail=None, repository: OutreachRepository = None, settings=None):
        self.settings = settings or get_settings()
        self.agent = build_agent(
            "email_agent",
            role="Follow-up Email Composer",
            goal="Draft and send personalized follow-up emails that maintain engagement",
            backstory=(
                "Professional communicator crafting compelling follow-up messages. You "
                "create emails that are personal, relevant, and drive action."
            ),
        )
        self.gmail = gmail or GmailIntegration(self.settings)
        self.db = db_manager
        self.repository = repository or (OutreachRepository(db_manager) if db_manager else None)

    @property
    def signature(self) -> str:
        return self.gmail.signature or self.settings.email_signature

    # ---------------------------------------------------------------- drafting
    def draft_followup_email(self, customer_data: dict, call_analysis: dict) -> dict:
        """Draft the right email for the recommended follow-up type.

        Returns None when the customer has no email address to write to.
        """
        customer_data = customer_data or {}
        call_analysis = call_analysis or {}

        recipient = str(customer_data.get("email") or "").strip()
        if not recipient:
            logger.warning("Customer %s has no email address", customer_data.get("customer_id"))
            return None
        if not _is_plausible_address(recipient):
            logger.warning(
                "Customer %s has a malformed email address %r - skipping follow-up",
                customer_data.get("customer_id"),
                recipient,
            )
            return None
        customer_data = {**customer_data, "email": recipient}

        email_type = (call_analysis.get("follow_up_recommendation") or {}).get("type")
        builders = {
            "retry": self._draft_retry_email,
            "follow_email_and_meeting": self._draft_meeting_request_email,
            "follow_meeting": self._draft_meeting_request_email,
        }
        builder = builders.get(email_type, self._draft_standard_email)

        email = builder(customer_data, call_analysis)
        logger.info(
            "Drafted %s email for customer %s", email["type"], customer_data.get("customer_id")
        )
        return email

    @staticmethod
    def _base_fields(customer_data: dict) -> tuple:
        """Greeting fields, tolerating blank or whitespace-only names."""
        name = str(customer_data.get("name") or "").strip()
        parts = name.split()
        first_name = parts[0] if parts else "there"
        company = str(customer_data.get("company") or "").strip() or "your organization"
        return name or "there", first_name, company

    def _envelope(self, customer_data: dict, subject: str, body: str, email_type: str) -> dict:
        return {
            "subject": subject,
            "body": f"{body}\n\n{self.signature}",
            "type": email_type,
            "customer_id": customer_data.get("customer_id"),
            "customer_email": customer_data.get("email"),
        }

    def _draft_retry_email(self, customer_data: dict, call_analysis: dict) -> dict:
        _, first_name, company = self._base_fields(customer_data)
        body = (
            f"Hi {first_name},\n\n"
            "I tried reaching you earlier but wasn't able to connect. I'd love to continue our "
            f"conversation about how we can help {company} achieve its goals.\n\n"
            "Would you have 15 minutes for a quick call? I'm happy to work around your schedule.\n\n"
            "Looking forward to speaking soon."
        )
        return self._envelope(customer_data, f"Let's connect, {first_name}", body, "retry")

    def _draft_meeting_request_email(self, customer_data: dict, call_analysis: dict) -> dict:
        _, first_name, company = self._base_fields(customer_data)
        body = (
            f"Hi {first_name},\n\n"
            "Thank you for our conversation earlier. I really appreciated learning more about "
            f"{company} and your priorities."
            f"{self._recap(call_analysis)}\n\n"
            "Based on what we discussed, I'd like to set up a follow-up meeting to go deeper on "
            "the opportunities we identified.\n\n"
            "Topics I'd suggest covering:\n"
            "- Your current priorities and challenges\n"
            "- Where we can add the most value\n"
            "- Next steps and timeline\n\n"
            "Are you available next week? I'm flexible on timing."
        )
        return self._envelope(
            customer_data, f"Next steps for {company}", body, "meeting_request"
        )

    def _draft_standard_email(self, customer_data: dict, call_analysis: dict) -> dict:
        _, first_name, company = self._base_fields(customer_data)
        body = (
            f"Hi {first_name},\n\n"
            "Thank you for taking the time to speak with us today. I enjoyed hearing about "
            f"{company} and the challenges you're working through."
            f"{self._recap(call_analysis)}\n\n"
            "If any questions come up in the meantime, just reply to this email and I'll get "
            "straight back to you.\n\n"
            "I'd love to stay in touch and keep supporting your success."
        )
        return self._envelope(
            customer_data, f"Thank you for your time, {first_name}", body, "standard"
        )

    @staticmethod
    def _recap(call_analysis: dict) -> str:
        """A short recap line drawn from the call analysis, when available."""
        next_action = (call_analysis or {}).get("next_action")
        if not next_action:
            return ""
        return f"\n\nAs a next step, here's what I'll do: {next_action.lower()}."

    # ----------------------------------------------------------------- sending
    def send_email(self, customer_email: str, subject: str, body: str) -> str:
        """Send an email and return its message id, or None on failure."""
        return self.gmail.send_email(customer_email, subject, body, html=False)

    def send_followup(
        self, customer_data: dict, call_analysis: dict, call_record_id: int = None, campaign_id: int = None
    ) -> dict:
        """Draft, send and record a follow-up email in one step.

        Returns a result dict with ``sent``, ``message_id`` and ``email_record_id``.
        """
        draft = self.draft_followup_email(customer_data, call_analysis)
        if not draft:
            return {"sent": False, "message_id": None, "email_record_id": None}

        message_id = self.send_email(draft["customer_email"], draft["subject"], draft["body"])
        sent = message_id is not None

        email_record_id = self.log_email(
            customer_id=draft["customer_id"],
            call_record_id=call_record_id,
            subject=draft["subject"],
            body=draft["body"],
            message_id=message_id,
            email_type=draft["type"],
            campaign_id=campaign_id,
            status=EmailStatus.SENT if sent else EmailStatus.FAILED,
        )

        return {
            "sent": sent,
            "message_id": message_id,
            "email_record_id": email_record_id,
            "subject": draft["subject"],
            "type": draft["type"],
        }

    def log_email(
        self,
        customer_id: int,
        call_record_id: int,
        subject: str,
        body: str,
        message_id: str = None,
        email_type: str = None,
        campaign_id: int = None,
        status=EmailStatus.SENT,
    ):
        """Persist an email record. Returns its id, or None without a database."""
        if not self.repository:
            logger.debug("No repository configured - email not persisted")
            return None
        if not customer_id:
            # `customer_id` is NOT NULL; without it the insert can only fail.
            logger.warning("Email to %r has no customer id - not persisted", subject)
            return None

        return self.repository.create_email_record(
            customer_id=customer_id,
            subject=subject,
            body=body,
            call_record_id=call_record_id,
            campaign_id=campaign_id,
            message_id=message_id,
            email_type=email_type,
            status=status,
        )
