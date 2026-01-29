# Installation and Setup Guide

## System Requirements

- Python 3.12 or higher
- pip (Python package manager)
- 2GB disk space
- Internet connection for API calls

## Step-by-Step Installation

### 1. Clone/Download Project

```bash
cd "c:\Users\sarth\OneDrive\Desktop\Projects\Outreach agent"
```

### 2. Create Virtual Environment

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# macOS/Linux
python3 -m venv venv
source venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables

```bash
# Copy example to actual .env file
copy .env.example .env  # Windows
cp .env.example .env    # macOS/Linux
```

Edit `.env` with your API credentials:

```env
OPENAI_API_KEY=sk-...
ELEVENLABS_API_KEY=...
ELEVENLABS_AGENT_ID=...
TWILIO_ACCOUNT_SID=AC...
TWILIO_AUTH_TOKEN=...
TWILIO_PHONE_NUMBER=+1...
GOOGLE_APPLICATION_CREDENTIALS=/path/to/credentials.json
GMAIL_ADDRESS=your@gmail.com
DATABASE_URL=sqlite:///outreach_agent.db
```

### 5. Initialize Database

```bash
python scripts/seed_data.py
```

### 6. Run the Application

```bash
# Execute main workflow
python main.py

# Or run specific workflow
python -c "
from src.orchestrator import OutreachOrchestrator
orchestrator = OutreachOrchestrator()
results = orchestrator.execute_outreach_workflow([1, 2, 3], 'Test Campaign')
print(results)
"
```

## API Setup Instructions

### OpenAI API

1. Visit https://platform.openai.com
2. Create account and generate API key
3. Add to `.env`: `OPENAI_API_KEY=sk-...`

### ElevenLabs

1. Visit https://elevenlabs.io
2. Create account and get API key
3. Create/deploy a conversational agent
4. Get Agent ID from dashboard
5. Add to `.env`:
   ```
   ELEVENLABS_API_KEY=...
   ELEVENLABS_AGENT_ID=...
   ```

### Twilio

1. Visit https://www.twilio.com
2. Create account and verify phone number
3. Get Account SID and Auth Token from dashboard
4. Buy a phone number for outbound calls
5. Add to `.env`:
   ```
   TWILIO_ACCOUNT_SID=AC...
   TWILIO_AUTH_TOKEN=...
   TWILIO_PHONE_NUMBER=+1...
   ```

### Google Gmail API

1. Create Google Cloud Project
2. Enable Gmail API
3. Create Service Account credentials
4. Download JSON credentials file
5. Add to `.env`: `GOOGLE_APPLICATION_CREDENTIALS=/path/to/credentials.json`

## Verification

Test your setup:

```bash
python -c "
import os
from dotenv import load_dotenv

load_dotenv()

print('OpenAI:', 'OK' if os.getenv('OPENAI_API_KEY') else 'MISSING')
print('ElevenLabs:', 'OK' if os.getenv('ELEVENLABS_API_KEY') else 'MISSING')
print('Twilio:', 'OK' if os.getenv('TWILIO_ACCOUNT_SID') else 'MISSING')
print('Gmail:', 'OK' if os.getenv('GOOGLE_APPLICATION_CREDENTIALS') else 'MISSING')
print('Database:', 'OK' if os.path.exists('outreach_agent.db') else 'MISSING')
"
```

## Troubleshooting

### ImportError: No module named 'crewai'

```bash
pip install --upgrade -r requirements.txt
```

### Database Error

```bash
rm outreach_agent.db  # Delete old database
python scripts/seed_data.py  # Recreate
```

### API Authentication Errors

- Verify credentials in `.env`
- Check API quotas and billing
- Ensure APIs are enabled in respective dashboards

## Next Steps

1. Review `README.md` for features and usage
2. Examine `src/orchestrator.py` for workflow logic
3. Check `config/config.yaml` for customization options
4. Review agent implementations in `src/agents/`

## Support

Refer to individual service documentation:
- OpenAI: https://platform.openai.com/docs
- ElevenLabs: https://docs.elevenlabs.io
- Twilio: https://www.twilio.com/docs
- Google: https://developers.google.com/gmail/api
