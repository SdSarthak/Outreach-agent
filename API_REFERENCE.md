# API Reference Guide

## OutreachOrchestrator

Main orchestration class that coordinates all agents and workflows.

### Initialization

```python
from src.orchestrator import OutreachOrchestrator

orchestrator = OutreachOrchestrator(config_path="config/config.yaml")
```

### Methods

#### execute_outreach_workflow(customer_ids, campaign_name)

Execute complete outreach workflow for multiple customers.

**Parameters:**
- `customer_ids` (list): List of customer IDs to contact
- `campaign_name` (str): Name of the campaign

**Returns:** Campaign results dictionary

**Example:**
```python
results = orchestrator.execute_outreach_workflow(
    customer_ids=[1, 2, 3],
    campaign_name="Q1 Engagement"
)
```

#### execute_customer_outreach(customer_id)

Execute outreach workflow for a single customer.

**Parameters:**
- `customer_id` (int): Customer ID

**Returns:** Interaction result dictionary

**Example:**
```python
result = orchestrator.execute_customer_outreach(customer_id=1)
```

#### get_campaign_metrics(campaign_id)

Get detailed metrics for a campaign.

**Parameters:**
- `campaign_id` (int): Campaign ID

**Returns:** Campaign metrics dictionary

#### get_performance_summary(days=30)

Get performance summary for specified period.

**Parameters:**
- `days` (int): Number of days to summarize

**Returns:** Performance summary dictionary

---

## Agents

### InsightAgent

Generates personalized call guidance and strategic insights.

```python
from src.agents import InsightAgent

agent = InsightAgent()
```

#### generate_call_guidance(customer_context)

Generate guidance for a call.

**Parameters:**
- `customer_context` (dict): Customer data and engagement history

**Returns:** Call guidance dictionary with:
- `key_talking_points` (list): Topics to discuss
- `tone` (str): Recommended tone
- `recommended_actions` (list): Suggested actions
- `engagement_strategy` (str): Strategy description
- `potential_objections` (list): Expected concerns
- `next_steps` (list): Follow-up steps

**Example:**
```python
guidance = agent.generate_call_guidance(customer_context)
print(guidance['key_talking_points'])
```

---

### CallAgent

Executes voice calls with AI integration.

```python
from src.agents import CallAgent

agent = CallAgent()
```

#### initiate_call(customer_data, call_guidance)

Initiate a voice call.

**Parameters:**
- `customer_data` (dict): Customer contact information
- `call_guidance` (dict): Guidance from InsightAgent

**Returns:** Call details dictionary

**Example:**
```python
call_details = agent.initiate_call(customer_data, call_guidance)
call_id = call_details['call_id']
```

#### monitor_call(call_sid)

Get current status of ongoing call.

**Parameters:**
- `call_sid` (str): Twilio call SID

**Returns:** Call status dictionary

#### end_call(call_sid)

End a call.

**Parameters:**
- `call_sid` (str): Twilio call SID

**Returns:** Boolean indicating success

#### get_call_transcript(call_sid)

Retrieve call transcript.

**Parameters:**
- `call_sid` (str): Twilio call SID

**Returns:** Transcript string

---

### DecisionAgent

Analyzes call outcomes and recommends follow-up actions.

```python
from src.agents import DecisionAgent
from src.database import DatabaseManager

db = DatabaseManager()
agent = DecisionAgent(db_manager=db)
```

#### analyze_call_outcome(call_data)

Analyze call and recommend follow-up.

**Parameters:**
- `call_data` (dict): Call execution data

**Returns:** Analysis dictionary with:
- `sentiment_analysis` (dict): Sentiment breakdown
- `success_indicator` (dict): Success metrics
- `follow_up_recommendation` (dict): Recommended action
- `next_action` (str): Next step description
- `priority_level` (str): Priority level

**Example:**
```python
analysis = agent.analyze_call_outcome(call_data)
print(f"Next action: {analysis['next_action']}")
```

---

### EmailAgent

Drafts and sends personalized follow-up emails.

```python
from src.agents import EmailAgent
from src.database import DatabaseManager

db = DatabaseManager()
agent = EmailAgent(db_manager=db)
```

#### draft_followup_email(customer_data, call_analysis)

Draft a follow-up email.

**Parameters:**
- `customer_data` (dict): Customer information
- `call_analysis` (dict): Analysis from DecisionAgent

**Returns:** Email draft dictionary with:
- `subject` (str): Email subject
- `body` (str): Email body
- `type` (str): Email type (retry, meeting_request, standard)

**Example:**
```python
email = agent.draft_followup_email(customer_data, analysis)
```

#### send_email(customer_email, subject, body)

Send email to customer.

**Parameters:**
- `customer_email` (str): Recipient email
- `subject` (str): Email subject
- `body` (str): Email body

**Returns:** Message ID if successful, None otherwise

**Example:**
```python
message_id = agent.send_email(
    "customer@example.com",
    "Follow-up",
    "Thank you for our conversation..."
)
```

#### log_email(customer_id, call_record_id, subject, body, message_id, status)

Log email to database.

**Parameters:**
- `customer_id` (int): Customer ID
- `call_record_id` (int): Associated call record ID
- `subject` (str): Email subject
- `body` (str): Email body
- `message_id` (str): Gmail message ID
- `status` (str): Email status

**Returns:** Boolean indicating success

---

## Utility Classes

### CustomerDataWorkflow

Retrieves and aggregates customer data.

```python
from src.utils import CustomerDataWorkflow
from src.database import DatabaseManager

db = DatabaseManager()
workflow = CustomerDataWorkflow(db)
```

#### get_customer_context(customer_id)

Get comprehensive customer context.

**Parameters:**
- `customer_id` (int): Customer ID

**Returns:** Customer context dictionary

**Example:**
```python
context = workflow.get_customer_context(1)
print(context['engagement_score'])
```

#### get_batch_customer_contexts(customer_ids)

Get contexts for multiple customers.

**Parameters:**
- `customer_ids` (list): List of customer IDs

**Returns:** List of context dictionaries

---

### AnalyticsManager

Tracks campaign metrics and analytics.

```python
from src.utils import AnalyticsManager
from src.database import DatabaseManager

db = DatabaseManager()
analytics = AnalyticsManager(db)
```

#### create_campaign(name, description)

Create new campaign.

**Parameters:**
- `name` (str): Campaign name
- `description` (str): Campaign description

**Returns:** Campaign ID

**Example:**
```python
campaign_id = analytics.create_campaign("Q1 Campaign")
```

#### get_campaign_metrics(campaign_id)

Get campaign metrics.

**Parameters:**
- `campaign_id` (int): Campaign ID

**Returns:** Metrics dictionary

#### log_outreach_metrics(campaign_id, calls_initiated, calls_completed, emails_sent, customer_satisfaction)

Log metrics for campaign.

**Parameters:**
- `campaign_id` (int): Campaign ID
- `calls_initiated` (int): Number of calls initiated
- `calls_completed` (int): Number of completed calls
- `emails_sent` (int): Number of emails sent
- `customer_satisfaction` (float): Average satisfaction score

**Returns:** Boolean indicating success

#### get_performance_summary(campaign_id, days)

Get performance summary.

**Parameters:**
- `campaign_id` (int, optional): Campaign ID filter
- `days` (int): Number of days to summarize

**Returns:** Summary dictionary

---

## Integration Classes

### ElevenLabsIntegration

Manages ElevenLabs Conversational AI.

```python
from src.integrations import ElevenLabsIntegration

elevenlabs = ElevenLabsIntegration()
```

#### create_conversation(phone_number, context)

Create new conversation session.

**Parameters:**
- `phone_number` (str): Customer phone number
- `context` (dict): Conversation context

**Returns:** Conversation configuration dictionary

#### inject_context_variables(context)

Format context for ElevenLabs.

**Parameters:**
- `context` (dict): Customer context

**Returns:** Formatted context dictionary

#### get_conversation_status(conversation_id)

Get conversation status.

**Parameters:**
- `conversation_id` (str): Conversation ID

**Returns:** Status dictionary

#### end_conversation(conversation_id)

End conversation session.

**Parameters:**
- `conversation_id` (str): Conversation ID

**Returns:** Completion dictionary

---

### TwilioIntegration

Manages Twilio voice calls.

```python
from src.integrations import TwilioIntegration

twilio = TwilioIntegration()
```

#### make_call(to_number, callback_url)

Initiate outbound call.

**Parameters:**
- `to_number` (str): Destination phone number
- `callback_url` (str): Webhook URL for events

**Returns:** Twilio call SID

#### get_call_status(call_sid)

Get call status.

**Parameters:**
- `call_sid` (str): Twilio call SID

**Returns:** Status dictionary

#### end_call(call_sid)

End call.

**Parameters:**
- `call_sid` (str): Twilio call SID

**Returns:** Boolean indicating success

#### get_call_recording(call_sid)

Get call recording URL.

**Parameters:**
- `call_sid` (str): Twilio call SID

**Returns:** Recording URL string

---

### GmailIntegration

Manages Gmail email delivery.

```python
from src.integrations import GmailIntegration

gmail = GmailIntegration()
```

#### send_email(to_email, subject, body, html)

Send email.

**Parameters:**
- `to_email` (str): Recipient email
- `subject` (str): Email subject
- `body` (str): Email body
- `html` (bool): Whether body is HTML

**Returns:** Message ID if successful

#### get_email_templates()

Get available templates.

**Returns:** Dictionary of templates

#### format_email(template_name, variables)

Format email using template.

**Parameters:**
- `template_name` (str): Template name
- `variables` (dict): Variables to substitute

**Returns:** Tuple of (subject, body)

---

## Database Models

### Customer

```python
from src.database import Customer

# Fields:
customer.id              # int - Primary key
customer.name            # str - Customer name
customer.email           # str - Email address
customer.phone           # str - Phone number
customer.company         # str - Company name
customer.industry        # str - Industry
customer.engagement_score # float - Engagement metric
customer.is_active       # bool - Active status
customer.created_at      # datetime - Creation timestamp
```

### CallRecord

```python
from src.database import CallRecord

# Fields:
call.id                  # int - Primary key
call.customer_id         # int - FK to Customer
call.call_date          # datetime - Call timestamp
call.duration_seconds   # int - Call duration
call.status             # enum - Call status
call.call_transcript    # str - Call transcript
call.call_guid          # str - ElevenLabs ID
call.twilio_call_sid    # str - Twilio call ID
```

### EmailRecord

```python
from src.database import EmailRecord

# Fields:
email.id                # int - Primary key
email.customer_id       # int - FK to Customer
email.call_record_id    # int - FK to CallRecord
email.subject           # str - Email subject
email.body              # str - Email body
email.status            # enum - Email status
email.message_id        # str - Gmail message ID
email.email_date        # datetime - Send timestamp
```

---

## Error Handling

All methods include error handling and logging. Check logs for detailed error messages.

### Common Errors

| Error | Cause | Solution |
|-------|-------|----------|
| API Key Missing | Environment variable not set | Check .env file |
| Call Failed | Phone number invalid | Verify customer phone |
| Email Not Sent | Gmail not configured | Setup Google credentials |
| Database Error | Connection failed | Run seed_data.py |

---

## Examples

### Complete Workflow Example

```python
from src.orchestrator import OutreachOrchestrator
from dotenv import load_dotenv

load_dotenv()

# Initialize
orchestrator = OutreachOrchestrator()

# Get customer context
from src.utils import CustomerDataWorkflow
from src.database import DatabaseManager

db = DatabaseManager()
customer_workflow = CustomerDataWorkflow(db)
context = customer_workflow.get_customer_context(1)

# Generate guidance
from src.agents import InsightAgent
insight = InsightAgent()
guidance = insight.generate_call_guidance(context)

# Make call
from src.agents import CallAgent
call_agent = CallAgent()
call = call_agent.initiate_call(context, guidance)

# Analyze outcome
from src.agents import DecisionAgent
decision = DecisionAgent(db)
analysis = decision.analyze_call_outcome({
    'call_id': call['call_id'],
    'customer_id': 1,
    'status': 'completed',
    'duration': 180,
    'transcript': 'Good conversation...'
})

# Send email
from src.agents import EmailAgent
email_agent = EmailAgent(db)
email = email_agent.draft_followup_email(context, analysis)
message_id = email_agent.send_email(
    email['customer_email'],
    email['subject'],
    email['body']
)

print(f"Workflow complete: {message_id}")
```

---

For more examples, see `quickstart.py` and `main.py`
