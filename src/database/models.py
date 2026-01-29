from sqlalchemy import Column, Integer, String, DateTime, Float, Boolean, Text, Enum, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime
import enum

Base = declarative_base()

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
    metadata = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    
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
    
    def __repr__(self):
        return f"<Feedback {self.id}: Customer {self.customer_id} - {self.sentiment}>"


class CallRecord(Base):
    """Call execution and tracking"""
    __tablename__ = "call_records"
    
    id = Column(Integer, primary_key=True)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=False)
    call_date = Column(DateTime, default=datetime.utcnow)
    duration_seconds = Column(Integer)
    
    class CallStatus(str, enum.Enum):
        SCHEDULED = "scheduled"
        IN_PROGRESS = "in_progress"
        COMPLETED = "completed"
        FAILED = "failed"
        CANCELLED = "cancelled"
    
    status = Column(Enum(CallStatus), default=CallStatus.SCHEDULED)
    call_transcript = Column(Text)
    audio_url = Column(String(500))
    call_guid = Column(String(255), unique=True)  # ElevenLabs call ID
    twilio_call_sid = Column(String(255), unique=True)  # Twilio call ID
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f"<CallRecord {self.id}: Customer {self.customer_id} - {self.status.value}>"


class EmailRecord(Base):
    """Email follow-up tracking"""
    __tablename__ = "email_records"
    
    id = Column(Integer, primary_key=True)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=False)
    call_record_id = Column(Integer, ForeignKey("call_records.id"))
    subject = Column(String(255), nullable=False)
    body = Column(Text, nullable=False)
    email_date = Column(DateTime, default=datetime.utcnow)
    
    class EmailStatus(str, enum.Enum):
        DRAFT = "draft"
        SENT = "sent"
        FAILED = "failed"
        OPENED = "opened"
        CLICKED = "clicked"
    
    status = Column(Enum(EmailStatus), default=EmailStatus.DRAFT)
    message_id = Column(String(255), unique=True)  # Gmail message ID
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f"<EmailRecord {self.id}: Customer {self.customer_id} - {self.status.value}>"


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
    
    def __repr__(self):
        return f"<OutreachMetrics {self.id}: {self.metric_date}>"
