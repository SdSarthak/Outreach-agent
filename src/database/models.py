"""SQLAlchemy models for the AI Outreach Agent."""

import enum
from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class CallStatus(str, enum.Enum):
    """Lifecycle states of an outbound call."""

    SCHEDULED = "scheduled"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class EmailStatus(str, enum.Enum):
    """Lifecycle states of a follow-up email."""

    DRAFT = "draft"
    SENT = "sent"
    FAILED = "failed"
    OPENED = "opened"
    CLICKED = "clicked"


def _enum_column(enum_class, default):
    """Enum column that stores the lowercase value and accepts plain strings."""
    return Column(
        Enum(
            enum_class,
            native_enum=False,
            length=32,
            values_callable=lambda members: [member.value for member in members],
        ),
        default=default,
        nullable=False,
    )


class Customer(Base):
    """Customer data model"""

    __tablename__ = "customers"

    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    email = Column(String(255), unique=True, nullable=False)
    phone = Column(String(20), nullable=False)
    company = Column(String(255))
    industry = Column(String(100))
    engagement_score = Column(Float, default=0.0)
    preferred_contact_time = Column(String(50))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_active = Column(Boolean, default=True)

    enrollments = relationship("Enrollment", back_populates="customer", cascade="all, delete-orphan")
    engagements = relationship("Engagement", back_populates="customer", cascade="all, delete-orphan")
    feedback = relationship("Feedback", back_populates="customer", cascade="all, delete-orphan")
    calls = relationship("CallRecord", back_populates="customer", cascade="all, delete-orphan")
    emails = relationship("EmailRecord", back_populates="customer", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Customer {self.id}: {self.name} ({self.email})>"


class Enrollment(Base):
    """Customer enrollment data"""

    __tablename__ = "enrollments"

    id = Column(Integer, primary_key=True)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=False)
    product = Column(String(255), nullable=False)
    enrollment_date = Column(DateTime, default=datetime.utcnow)
    status = Column(String(50), default="active")
    tier = Column(String(50))
    created_at = Column(DateTime, default=datetime.utcnow)

    customer = relationship("Customer", back_populates="enrollments")

    def __repr__(self):
        return f"<Enrollment {self.id}: Customer {self.customer_id} - {self.product}>"


class Engagement(Base):
    """Customer engagement metrics"""

    __tablename__ = "engagements"

    id = Column(Integer, primary_key=True)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=False)
    engagement_type = Column(String(100))  # email_open, feature_usage, support_ticket, etc.
    engagement_date = Column(DateTime, default=datetime.utcnow)
    value = Column(Float)
    # `metadata` is reserved by SQLAlchemy's declarative API, so the attribute is
    # named `event_metadata` while the underlying column keeps the original name.
    event_metadata = Column("metadata", Text)
    created_at = Column(DateTime, default=datetime.utcnow)

    customer = relationship("Customer", back_populates="engagements")

    def __repr__(self):
        return f"<Engagement {self.id}: Customer {self.customer_id} - {self.engagement_type}>"


class Feedback(Base):
    """Customer feedback and sentiment"""

    __tablename__ = "feedback"

    id = Column(Integer, primary_key=True)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=False)
    feedback_text = Column(Text)
    sentiment = Column(String(50))  # positive, neutral, negative
    rating = Column(Integer)
    feedback_date = Column(DateTime, default=datetime.utcnow)
    category = Column(String(100))
    created_at = Column(DateTime, default=datetime.utcnow)

    customer = relationship("Customer", back_populates="feedback")

    def __repr__(self):
        return f"<Feedback {self.id}: Customer {self.customer_id} - {self.sentiment}>"


class CallRecord(Base):
    """Call execution and tracking"""

    __tablename__ = "call_records"

    # Kept as a class attribute for backwards compatibility with earlier code
    # that referenced `CallRecord.CallStatus`.
    CallStatus = CallStatus

    id = Column(Integer, primary_key=True)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=False)
    campaign_id = Column(Integer, ForeignKey("campaigns.id"))
    call_date = Column(DateTime, default=datetime.utcnow)
    duration_seconds = Column(Integer, default=0)
    status = _enum_column(CallStatus, CallStatus.SCHEDULED)
    call_transcript = Column(Text)
    audio_url = Column(String(500))
    call_guid = Column(String(255))  # ElevenLabs conversation ID
    twilio_call_sid = Column(String(255))  # Twilio call ID
    sentiment = Column(String(50))
    success_score = Column(Integer, default=0)
    next_action = Column(String(255))
    priority = Column(String(50))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    customer = relationship("Customer", back_populates="calls")
    campaign = relationship("Campaign", back_populates="calls")
    emails = relationship("EmailRecord", back_populates="call_record")

    def __repr__(self):
        status = self.status.value if isinstance(self.status, CallStatus) else self.status
        return f"<CallRecord {self.id}: Customer {self.customer_id} - {status}>"


class EmailRecord(Base):
    """Email follow-up tracking"""

    __tablename__ = "email_records"

    EmailStatus = EmailStatus

    id = Column(Integer, primary_key=True)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=False)
    call_record_id = Column(Integer, ForeignKey("call_records.id"))
    campaign_id = Column(Integer, ForeignKey("campaigns.id"))
    subject = Column(String(255), nullable=False)
    body = Column(Text, nullable=False)
    email_type = Column(String(50))
    email_date = Column(DateTime, default=datetime.utcnow)
    status = _enum_column(EmailStatus, EmailStatus.DRAFT)
    message_id = Column(String(255))  # Gmail message ID
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    customer = relationship("Customer", back_populates="emails")
    call_record = relationship("CallRecord", back_populates="emails")
    campaign = relationship("Campaign", back_populates="emails")

    def __repr__(self):
        status = self.status.value if isinstance(self.status, EmailStatus) else self.status
        return f"<EmailRecord {self.id}: Customer {self.customer_id} - {status}>"


class Campaign(Base):
    """Campaign tracking and analytics"""

    __tablename__ = "campaigns"

    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    start_date = Column(DateTime, default=datetime.utcnow)
    end_date = Column(DateTime)
    total_customers = Column(Integer, default=0)
    successful_calls = Column(Integer, default=0)
    failed_calls = Column(Integer, default=0)
    emails_sent = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    calls = relationship("CallRecord", back_populates="campaign")
    emails = relationship("EmailRecord", back_populates="campaign")
    metrics = relationship("OutreachMetrics", back_populates="campaign")

    def __repr__(self):
        return f"<Campaign {self.id}: {self.name}>"


class OutreachMetrics(Base):
    """Aggregated outreach metrics"""

    __tablename__ = "outreach_metrics"

    id = Column(Integer, primary_key=True)
    campaign_id = Column(Integer, ForeignKey("campaigns.id"))
    metric_date = Column(DateTime, default=datetime.utcnow)
    calls_initiated = Column(Integer, default=0)
    calls_completed = Column(Integer, default=0)
    call_success_rate = Column(Float, default=0.0)
    avg_call_duration = Column(Float, default=0.0)
    emails_sent = Column(Integer, default=0)
    customer_satisfaction = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow)

    campaign = relationship("Campaign", back_populates="metrics")

    def __repr__(self):
        return f"<OutreachMetrics {self.id}: {self.metric_date}>"
