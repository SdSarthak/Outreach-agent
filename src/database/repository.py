"""Persistence helpers shared by the agents, orchestrator and analytics."""

import logging
from datetime import datetime
from typing import List, Optional

from .db import DatabaseManager
from .models import (
    CallRecord,
    CallStatus,
    Campaign,
    Customer,
    EmailRecord,
    EmailStatus,
)

logger = logging.getLogger(__name__)


def _coerce_call_status(status) -> CallStatus:
    if isinstance(status, CallStatus):
        return status
    try:
        return CallStatus(str(status))
    except ValueError:
        return CallStatus.SCHEDULED


def _coerce_email_status(status) -> EmailStatus:
    if isinstance(status, EmailStatus):
        return status
    try:
        return EmailStatus(str(status))
    except ValueError:
        return EmailStatus.DRAFT


class OutreachRepository:
    """Read/write access to customers, calls, emails and campaigns."""

    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager

    # ------------------------------------------------------------------ customers
    def list_customers(self, active_only: bool = True, limit: int = None) -> List[dict]:
        """Return lightweight customer rows ordered by engagement score."""
        with self.db.session_scope() as session:
            query = session.query(Customer)
            if active_only:
                query = query.filter(Customer.is_active.is_(True))
            query = query.order_by(Customer.engagement_score.desc(), Customer.id.asc())
            if limit:
                query = query.limit(limit)
            return [
                {
                    "id": customer.id,
                    "name": customer.name,
                    "email": customer.email,
                    "phone": customer.phone,
                    "company": customer.company,
                    "industry": customer.industry,
                    "engagement_score": round(customer.engagement_score or 0.0, 3),
                }
                for customer in query.all()
            ]

    def customer_ids(self, active_only: bool = True, limit: int = None) -> List[int]:
        return [row["id"] for row in self.list_customers(active_only=active_only, limit=limit)]

    # ---------------------------------------------------------------------- calls
    def create_call_record(
        self,
        customer_id: int,
        campaign_id: int = None,
        status=CallStatus.SCHEDULED,
        twilio_call_sid: str = None,
        call_guid: str = None,
    ) -> Optional[int]:
        """Insert a call record and return its primary key."""
        try:
            with self.db.session_scope() as session:
                record = CallRecord(
                    customer_id=customer_id,
                    campaign_id=campaign_id,
                    status=_coerce_call_status(status),
                    twilio_call_sid=twilio_call_sid,
                    call_guid=call_guid,
                    call_date=datetime.utcnow(),
                )
                session.add(record)
                session.flush()
                logger.info("Call record %s created for customer %s", record.id, customer_id)
                return record.id
        except Exception as exc:  # pragma: no cover - defensive
            logger.error("Error creating call record: %s", exc)
            return None

    def update_call_record(self, call_record_id: int, **fields) -> bool:
        """Update mutable fields on a call record."""
        if not call_record_id:
            return False
        allowed = {
            "status",
            "duration_seconds",
            "call_transcript",
            "audio_url",
            "call_guid",
            "twilio_call_sid",
            "sentiment",
            "success_score",
            "next_action",
            "priority",
        }
        try:
            with self.db.session_scope() as session:
                record = session.get(CallRecord, call_record_id)
                if not record:
                    logger.warning("Call record %s not found", call_record_id)
                    return False
                for key, value in fields.items():
                    if key not in allowed or value is None:
                        continue
                    if key == "status":
                        value = _coerce_call_status(value)
                    setattr(record, key, value)
                record.updated_at = datetime.utcnow()
                return True
        except Exception as exc:  # pragma: no cover - defensive
            logger.error("Error updating call record %s: %s", call_record_id, exc)
            return False

    def get_call_record(self, call_record_id: int) -> Optional[dict]:
        with self.db.session_scope() as session:
            record = session.get(CallRecord, call_record_id)
            if not record:
                return None
            return {
                "id": record.id,
                "customer_id": record.customer_id,
                "campaign_id": record.campaign_id,
                "status": record.status.value if record.status else None,
                "duration_seconds": record.duration_seconds,
                "twilio_call_sid": record.twilio_call_sid,
                "call_guid": record.call_guid,
                "sentiment": record.sentiment,
                "success_score": record.success_score,
                "next_action": record.next_action,
                "priority": record.priority,
                "transcript": record.call_transcript,
            }

    # --------------------------------------------------------------------- emails
    def create_email_record(
        self,
        customer_id: int,
        subject: str,
        body: str,
        call_record_id: int = None,
        campaign_id: int = None,
        message_id: str = None,
        email_type: str = None,
        status=EmailStatus.DRAFT,
    ) -> Optional[int]:
        try:
            with self.db.session_scope() as session:
                record = EmailRecord(
                    customer_id=customer_id,
                    call_record_id=call_record_id,
                    campaign_id=campaign_id,
                    subject=subject,
                    body=body,
                    email_type=email_type,
                    message_id=message_id,
                    status=_coerce_email_status(status),
                    email_date=datetime.utcnow(),
                )
                session.add(record)
                session.flush()
                logger.info("Email record %s created for customer %s", record.id, customer_id)
                return record.id
        except Exception as exc:  # pragma: no cover - defensive
            logger.error("Error creating email record: %s", exc)
            return None

    def update_email_status(self, email_record_id: int, status, message_id: str = None) -> bool:
        try:
            with self.db.session_scope() as session:
                record = session.get(EmailRecord, email_record_id)
                if not record:
                    return False
                record.status = _coerce_email_status(status)
                if message_id:
                    record.message_id = message_id
                record.updated_at = datetime.utcnow()
                return True
        except Exception as exc:  # pragma: no cover - defensive
            logger.error("Error updating email record %s: %s", email_record_id, exc)
            return False

    # ------------------------------------------------------------------ campaigns
    def update_campaign_totals(
        self,
        campaign_id: int,
        total_customers: int = None,
        successful_calls: int = None,
        failed_calls: int = None,
        emails_sent: int = None,
        end_date: datetime = None,
    ) -> bool:
        if not campaign_id:
            return False
        try:
            with self.db.session_scope() as session:
                campaign = session.get(Campaign, campaign_id)
                if not campaign:
                    logger.warning("Campaign %s not found", campaign_id)
                    return False
                if total_customers is not None:
                    campaign.total_customers = total_customers
                if successful_calls is not None:
                    campaign.successful_calls = successful_calls
                if failed_calls is not None:
                    campaign.failed_calls = failed_calls
                if emails_sent is not None:
                    campaign.emails_sent = emails_sent
                if end_date is not None:
                    campaign.end_date = end_date
                campaign.updated_at = datetime.utcnow()
                return True
        except Exception as exc:  # pragma: no cover - defensive
            logger.error("Error updating campaign %s: %s", campaign_id, exc)
            return False
