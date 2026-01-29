# AI Outreach Agent

A sophisticated multi-agent AI system for automated customer outreach that combines strategic insights, voice communication, and personalized follow-up emails.

## Overview

This project implements an intelligent outreach automation platform that leverages a collaborative network of specialized AI agents to manage the complete customer engagement pipeline:

1. **Insight Agent** - Generates personalized call guidance and strategic insights
2. **Call Agent** - Executes voice calls with AI-driven conversation
3. **Decision Agent** - Analyzes call outcomes and recommends follow-up actions
4. **Email Agent** - Drafts and sends personalized follow-up emails

## Features

- **Multi-Agent Architecture** - Coordinated agents for specialized tasks
- **Conversational AI** - ElevenLabs integration for natural voice interactions
- **Scalable Outreach** - Handle hundreds of outbound calls efficiently
- **Personalization** - Context-aware messaging based on customer data
- **Analytics & Tracking** - Campaign metrics and engagement analytics
- **Database Management** - SQLAlchemy ORM for customer data persistence
- **Email Integration** - Gmail API for automated follow-ups

## Project Structure

```
Outreach agent/
├── src/
│   ├── agents/                 # AI agents
│   │   ├── insight_agent.py
│   │   ├── call_agent.py
│   │   ├── decision_agent.py
│   │   └── email_agent.py
│   ├── database/               # Database models and management
│   │   ├── models.py
│   │   └── db.py
│   ├── integrations/           # External API integrations
│   │   ├── elevenlabs.py
│   │   ├── twilio.py
│   │   └── gmail.py
│   ├── utils/                  # Utility modules
│   │   ├── customer_data.py
│   │   ├── logging.py
│   │   └── analytics.py
│   └── orchestrator.py         # Main orchestration logic
├── config/
│   └── config.yaml             # Configuration file
├── scripts/
│   └── seed_data.py            # Sample data creation
├── main.py                     # Entry point
├── requirements.txt            # Dependencies
└── .env.example                # Environment variables template
```

## Tech Stack

- **Language**: Python 3.12
- **Framework**: CrewAI (Multi-agent orchestration)
- **APIs & Services**:
  - OpenAI GPT-4o (AI language model)
  - ElevenLabs Conversational AI (Voice interaction)
  - Twilio (Voice call management)
  - Google Gmail API (Email delivery)
- **Database**: SQLite with SQLAlchemy ORM
- **Libraries**: Pandas, PyYAML, Requests

## Prerequisites

- Python 3.12+
- API Keys:
  - OpenAI API key
  - ElevenLabs API key and Agent ID
  - Twilio credentials
  - Google Cloud credentials (for Gmail)

## Installation

1. **Clone the repository**
```bash
cd "Outreach agent"
```

2. **Create a virtual environment**
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. **Install dependencies**
```bash
pip install -r requirements.txt
```

4. **Configure environment variables**
```bash
cp .env.example .env
# Edit .env with your API keys and credentials
```

5. **Initialize the database**
```bash
python scripts/seed_data.py
```

## Configuration

Edit `config/config.yaml` to customize:
- Agent roles and behaviors
- API integration settings
- Email templates
- Logging levels
- Database configuration

## Environment Variables

Required environment variables in `.env`:

```
OPENAI_API_KEY=your_key
OPENAI_MODEL_NAME=gpt-4o
ELEVENLABS_API_KEY=your_key
ELEVENLABS_AGENT_ID=your_agent_id
TWILIO_ACCOUNT_SID=your_sid
TWILIO_AUTH_TOKEN=your_token
TWILIO_PHONE_NUMBER=your_phone
GOOGLE_APPLICATION_CREDENTIALS=path/to/credentials.json
GMAIL_ADDRESS=your_email@gmail.com
DATABASE_URL=sqlite:///outreach_agent.db
LOG_LEVEL=INFO
```

## Usage

### Basic Usage

```python
from src.orchestrator import OutreachOrchestrator

# Initialize orchestrator
orchestrator = OutreachOrchestrator()

# Execute outreach for customers
results = orchestrator.execute_outreach_workflow(
    customer_ids=[1, 2, 3],
    campaign_name="Q1 Engagement Campaign"
)

print(f"Successful calls: {results['successful_calls']}")
print(f"Emails sent: {results['emails_sent']}")
```

### Run Main Script

```bash
python main.py
```

### Create Sample Data

```bash
python scripts/seed_data.py
```

## Database Models

### Customer
Stores customer contact information and engagement scores

### Enrollment
Tracks product/service enrollments

### Engagement
Records customer interaction events

### Feedback
Stores customer feedback and sentiment

### CallRecord
Logs all outbound calls with transcripts and metadata

### EmailRecord
Tracks follow-up emails sent to customers

### Campaign
Organizes outreach campaigns

### OutreachMetrics
Aggregated analytics and KPIs

## Workflow

1. **Data Retrieval** - Customer context is assembled from database
2. **Insight Generation** - InsightAgent creates personalized call guidance
3. **Call Execution** - CallAgent initiates conversation via ElevenLabs + Twilio
4. **Outcome Analysis** - DecisionAgent analyzes call results
5. **Email Follow-up** - EmailAgent sends personalized emails
6. **Analytics** - Metrics are logged for campaign tracking

## API Integrations

### ElevenLabs
- Real-time voice conversation
- Custom agent configuration
- Transcript generation
- Voice quality selection

### Twilio
- Outbound call initiation
- Call status tracking
- Recording retrieval
- DTMF support

### Gmail
- Automated email sending
- Template support
- Message ID tracking
- Read/click status (with webhooks)

## Logging

Logs are written to:
- `logs/outreach_agent.log` (file)
- Console output

Configure log level in `.env` or `config/config.yaml`

## Performance Metrics

Track:
- Call success rates
- Average call duration
- Email delivery and opens
- Customer satisfaction scores
- Campaign ROI

## Advanced Features

### Custom Talking Points
The Insight Agent generates context-specific talking points based on:
- Customer engagement history
- Industry trends
- Previous feedback
- Product usage patterns

### Sentiment Analysis
Decision Agent performs real-time sentiment analysis of conversations to determine:
- Call quality
- Customer interest level
- Objection handling
- Follow-up priority

### Personalization
Every interaction is personalized with:
- Customer name and company
- Historical engagement data
- Product-specific information
- Previous feedback

## Error Handling

The system gracefully handles:
- API failures with retry logic
- Database connection issues
- Missing customer data
- Call failures with fallback email outreach

## Security

- API keys stored in environment variables
- Database credentials in environment variables
- Secure HTTPS for all external API calls
- Google OAuth for Gmail authentication

## Contributing

To extend the system:
1. Add new agent types in `src/agents/`
2. Create new integration wrappers in `src/integrations/`
3. Add database models in `src/database/models.py`
4. Update orchestrator workflow in `src/orchestrator.py`

## Troubleshooting

### Missing API Keys
Ensure `.env` file is properly configured with all required keys

### Database Errors
Run `python scripts/seed_data.py` to initialize database

### Call Failures
Check Twilio and ElevenLabs credentials and quotas

### Email Not Sending
Verify Gmail API is enabled and credentials are valid

## License

Copyright 2026. All rights reserved.

## Support

For issues or questions, refer to the comprehensive logging output for detailed error information.

---

**Built with CrewAI, OpenAI, ElevenLabs, and Twilio**
