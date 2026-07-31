"""Gmail integration for sending follow-up emails.

Supports both credential styles Google hands out:

* a **service account** key (optionally impersonating ``GMAIL_ADDRESS`` via
  domain-wide delegation), and
* an **OAuth installed-app** client, reusing a cached ``token.json``.

The interactive OAuth consent flow only runs when explicitly requested, so
unattended runs never block on a browser prompt.
"""

import base64
import json
import logging
import os
from email.mime.text import MIMEText

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials as UserCredentials
from google.oauth2.service_account import Credentials as ServiceAccountCredentials
from googleapiclient.discovery import build

from src.config import Settings, get_settings

logger = logging.getLogger(__name__)


class GmailIntegration:
    """Gmail API wrapper for outbound email."""

    SCOPES = ["https://www.googleapis.com/auth/gmail.send"]

    def __init__(self, settings: Settings = None, interactive: bool = False):
        self.settings = settings or get_settings()
        self.gmail_address = self.settings.gmail_address
        self.credentials_path = self.settings.google_credentials_path
        self.token_path = self.settings.gmail_token_path
        self.interactive = interactive

        gmail_cfg = self.settings.section("integrations", "gmail")
        self.sender_name = gmail_cfg.get("sender_name", self.settings.sender_name)
        self.signature = gmail_cfg.get("signature", self.settings.email_signature)

        self.service = None
        self.sent_messages = []  # dry-run outbox, useful for demos and tests
        self._initialize_service()

    @property
    def live(self) -> bool:
        """True when messages will actually be delivered."""
        return self.service is not None

    # --------------------------------------------------------------- auth setup
    def _initialize_service(self):
        """Build the Gmail service, degrading to dry-run when unavailable."""
        if self.settings.dry_run:
            logger.info("DRY_RUN enabled - emails will be logged instead of sent")
            return

        credentials = self._load_credentials()
        if not credentials:
            logger.warning("Gmail credentials not configured - emails will be logged only")
            return

        try:
            self.service = build("gmail", "v1", credentials=credentials, cache_discovery=False)
            logger.info("Gmail service initialized")
        except Exception as exc:
            logger.error("Error initializing Gmail service: %s", exc)
            self.service = None

    def _load_credentials(self):
        """Resolve credentials from a cached token or the credentials file."""
        credentials = self._load_cached_token()
        if credentials:
            return credentials

        if not self.credentials_path or not os.path.exists(self.credentials_path):
            return None

        try:
            with open(self.credentials_path, "r", encoding="utf-8") as handle:
                payload = json.load(handle)
        except (OSError, ValueError) as exc:
            logger.error("Could not read Google credentials at %s: %s", self.credentials_path, exc)
            return None

        if payload.get("type") == "service_account":
            return self._service_account_credentials()
        return self._oauth_credentials()

    def _load_cached_token(self):
        """Reuse (and refresh) a previously stored OAuth token."""
        if not self.token_path or not os.path.exists(self.token_path):
            return None
        try:
            credentials = UserCredentials.from_authorized_user_file(self.token_path, self.SCOPES)
        except (OSError, ValueError) as exc:
            logger.warning("Ignoring unreadable Gmail token at %s: %s", self.token_path, exc)
            return None

        if credentials.valid:
            return credentials
        if credentials.expired and credentials.refresh_token:
            try:
                credentials.refresh(Request())
                self._save_token(credentials)
                logger.info("Refreshed Gmail OAuth token")
                return credentials
            except Exception as exc:
                logger.warning("Could not refresh Gmail token: %s", exc)
        return None

    def _service_account_credentials(self):
        try:
            credentials = ServiceAccountCredentials.from_service_account_file(
                self.credentials_path, scopes=self.SCOPES
            )
            # Service accounts cannot send as themselves; they must impersonate
            # a real mailbox via domain-wide delegation.
            if self.gmail_address:
                credentials = credentials.with_subject(self.gmail_address)
            else:
                logger.warning("GMAIL_ADDRESS not set - service account cannot impersonate a mailbox")
            return credentials
        except Exception as exc:
            logger.error("Error loading Gmail service account: %s", exc)
            return None

    def _oauth_credentials(self):
        """Run the installed-app consent flow, only when interactive."""
        if not self.interactive:
            logger.warning(
                "Gmail OAuth client found but no cached token at %s. "
                "Run `python main.py authorize-gmail` once to grant access.",
                self.token_path,
            )
            return None

        try:
            from google_auth_oauthlib.flow import InstalledAppFlow

            flow = InstalledAppFlow.from_client_secrets_file(self.credentials_path, self.SCOPES)
            credentials = flow.run_local_server(port=0)
            self._save_token(credentials)
            logger.info("Gmail OAuth token stored at %s", self.token_path)
            return credentials
        except Exception as exc:
            logger.error("Gmail OAuth flow failed: %s", exc)
            return None

    def _save_token(self, credentials):
        if not self.token_path:
            return
        try:
            with open(self.token_path, "w", encoding="utf-8") as handle:
                handle.write(credentials.to_json())
        except OSError as exc:
            logger.warning("Could not persist Gmail token: %s", exc)

    # ------------------------------------------------------------------ sending
    def build_message(self, to_email: str, subject: str, body: str, html: bool = False) -> dict:
        """Build the base64url payload the Gmail API expects."""
        message = MIMEText(body, "html" if html else "plain", "utf-8")
        message["to"] = to_email
        if self.gmail_address:
            message["from"] = (
                f"{self.sender_name} <{self.gmail_address}>" if self.sender_name else self.gmail_address
            )
        message["subject"] = subject
        return {"raw": base64.urlsafe_b64encode(message.as_bytes()).decode()}

    def send_email(self, to_email: str, subject: str, body: str, html: bool = False) -> str:
        """Send an email and return its message id.

        In dry-run (or without credentials) the message is recorded in
        ``self.sent_messages`` and a simulated id is returned, so callers and
        the database still see a consistent result.
        """
        if not to_email:
            logger.error("Cannot send an email without a recipient")
            return None

        if not self.live:
            message_id = f"dryrun-{len(self.sent_messages) + 1}"
            self.sent_messages.append(
                {"id": message_id, "to": to_email, "subject": subject, "body": body}
            )
            logger.info("[DRY RUN] Email to %s: %s", to_email, subject)
            return message_id

        try:
            result = (
                self.service.users()
                .messages()
                .send(userId="me", body=self.build_message(to_email, subject, body, html))
                .execute()
            )
            message_id = result.get("id")
            logger.info("Email sent to %s: %s", to_email, message_id)
            return message_id
        except Exception as exc:
            logger.error("Error sending email to %s: %s", to_email, exc)
            return None

    def close(self) -> None:
        """Release the Gmail API client's pooled HTTP connections."""
        service, self.service = self.service, None
        close = getattr(service, "close", None)
        if callable(close):
            try:
                close()
            except Exception as exc:  # pragma: no cover - defensive
                logger.debug("Error closing Gmail service: %s", exc)

    # ---------------------------------------------------------------- templates
    def get_email_templates(self) -> dict:
        """Predefined email templates, overridable from config.yaml."""
        templates = {
            "follow_up": {
                "subject": "Following up on our recent conversation",
                "body": (
                    "Hi {customer_name},\n\nThank you for taking the time to speak with us today. "
                    "We discussed {key_topics} and would love to help you achieve your goals.\n\n"
                    "Next steps: {next_steps}\n\n{signature}"
                ),
            },
            "thank_you": {
                "subject": "Thank you for your time",
                "body": (
                    "Hi {customer_name},\n\nWe appreciate the opportunity to connect. "
                    "Your feedback regarding {feedback_topic} is valuable to us.\n\n"
                    "We'll be in touch soon.\n\n{signature}"
                ),
            },
            "proposal": {
                "subject": "Proposal for {company_name}",
                "body": (
                    "Hi {customer_name},\n\nBased on our discussion, we've prepared a tailored "
                    "proposal for {company_name}.\n\n"
                    "Please review and let us know your thoughts.\n\n{signature}"
                ),
            },
        }
        overrides = self.settings.section("email_templates")
        for name, template in overrides.items():
            if isinstance(template, dict) and "subject" in template and "body" in template:
                templates[name] = template
        return templates

    def format_email(self, template_name: str, variables: dict) -> tuple:
        """Render a template. Returns ``(subject, body)`` or ``(None, None)``."""
        templates = self.get_email_templates()
        template = templates.get(template_name)
        if not template:
            logger.warning("Template %s not found", template_name)
            return None, None

        values = {"signature": self.signature}
        values.update(variables or {})
        try:
            return template["subject"].format(**values), template["body"].format(**values)
        except KeyError as exc:
            logger.error("Template %s is missing variable %s", template_name, exc)
            return None, None
