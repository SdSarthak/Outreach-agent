"""
API Configuration and Examples
"""

# ElevenLabs Conversational AI Configuration Example
ELEVENLABS_CONFIG = {
    "voice_id": "21m00Tcm4TlvDq8ikWAM",  # Professional voice
    "model": "eleven_turbo_v2",
    "system_prompt": """You are a professional customer success representative. 
    Your goal is to help customers understand how our solutions can benefit their business.
    Be personable, empathetic, and focus on understanding customer needs.
    Use the provided context about the customer to personalize the conversation."""
}

# Twilio Webhook Configuration Example
TWILIO_WEBHOOK_CONFIG = {
    "base_url": "https://your-domain.com/webhooks",
    "call_status_callback": "/twilio/call-status",
    "dtmf_callback": "/twilio/dtmf",
    "recording_callback": "/twilio/recording"
}

# Email Template Example
EMAIL_TEMPLATES = {
    "follow_up": {
        "subject": "Following up on our recent conversation - {customer_name}",
        "template": """Hi {customer_name},

Thank you for taking the time to speak with us today. We really appreciated learning about {company_name} and your goals.

As discussed, here are the key takeaways from our conversation:
{key_points}

Next Steps:
{next_steps}

Please let me know if you have any questions in the meantime.

Best regards,
{sender_name}
AI Outreach Team"""
    }
}

# Call Context Example
CALL_CONTEXT_EXAMPLE = {
    "customer_id": 1,
    "name": "John Smith",
    "company": "Tech Corp",
    "engagement_score": 0.85,
    "recent_activities": [
        {"type": "email_open", "date": "2026-01-28"},
        {"type": "feature_usage", "date": "2026-01-27"}
    ],
    "enrollments": [
        {"product": "Premium Suite", "status": "active"}
    ],
    "feedback": [
        {"sentiment": "positive", "rating": 4}
    ]
}

# Campaign Configuration Example
CAMPAIGN_CONFIG = {
    "name": "Q1 2026 Engagement Campaign",
    "description": "Personalized outreach to high-value customers",
    "target_customers": [1, 2, 3, 4, 5],
    "call_schedule": {
        "start_time": "09:00",
        "end_time": "17:00",
        "timezone": "UTC",
        "day_of_week": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
    },
    "metrics": {
        "target_call_success_rate": 0.7,
        "target_email_open_rate": 0.4,
        "target_conversion_rate": 0.1
    }
}

# Database Connection Example
DATABASE_CONFIG = {
    "type": "sqlite",
    "filename": "outreach_agent.db",
    "pool_size": 5,
    "max_overflow": 10,
    "echo": False
}

# Logging Configuration Example
LOGGING_CONFIG = {
    "level": "INFO",
    "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    "handlers": {
        "console": {"level": "INFO"},
        "file": {
            "level": "DEBUG",
            "filename": "logs/outreach_agent.log"
        }
    }
}
