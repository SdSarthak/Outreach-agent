# Deployment & Operations Guide

## Pre-Deployment Checklist

### Infrastructure Requirements

- [ ] Server/Cloud compute instance (AWS EC2, Azure VM, etc.)
- [ ] Python 3.12+ runtime
- [ ] Database storage (SQLite or PostgreSQL)
- [ ] HTTPS support for webhooks
- [ ] Sufficient quotas for API services

### Configuration

- [ ] All API keys obtained and verified
- [ ] Environment variables configured
- [ ] config/config.yaml customized
- [ ] Email templates reviewed
- [ ] Agent prompts tuned for your use case
- [ ] Database initialized and populated

### Testing

- [ ] Run quickstart.py successfully
- [ ] Test each API integration
- [ ] Verify sample outreach workflow
- [ ] Check logging and error handling
- [ ] Test email delivery
- [ ] Monitor call execution

---

## Deployment Options

### Option 1: Local Development

```bash
# Perfect for testing and development

# Install
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt

# Configure
copy .env.example .env
# Edit .env with your keys

# Initialize
python scripts/seed_data.py

# Run
python main.py
```

### Option 2: Docker Deployment

```dockerfile
# Dockerfile
FROM python:3.12-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project
COPY . .

# Set environment
ENV PYTHONUNBUFFERED=1

# Run
CMD ["python", "main.py"]
```

Build and run:
```bash
docker build -t outreach-agent .
docker run --env-file .env outreach-agent
```

### Option 3: Cloud Deployment (AWS Lambda)

```python
# lambda_handler.py
from src.orchestrator import OutreachOrchestrator
import json

orchestrator = OutreachOrchestrator()

def handler(event, context):
    """Lambda handler for outreach campaign"""
    
    customer_ids = event.get('customer_ids', [])
    campaign_name = event.get('campaign_name', 'Lambda Campaign')
    
    results = orchestrator.execute_outreach_workflow(
        customer_ids,
        campaign_name
    )
    
    return {
        'statusCode': 200,
        'body': json.dumps(results)
    }
```

Deploy:
```bash
pip install -r requirements.txt -t package/
cd package && zip -r ../lambda.zip . && cd ..
aws lambda create-function \
  --function-name outreach-agent \
  --runtime python3.12 \
  --zip-file fileb://lambda.zip \
  --handler lambda_handler.handler
```

### Option 4: Scheduled Jobs (Cron/APScheduler)

```python
# scheduler.py
from apscheduler.schedulers.background import BackgroundScheduler
from src.orchestrator import OutreachOrchestrator
import logging

logger = logging.getLogger(__name__)
orchestrator = OutreachOrchestrator()

def scheduled_outreach():
    """Run outreach every morning at 9 AM"""
    results = orchestrator.execute_outreach_workflow(
        customer_ids=[1, 2, 3, 4, 5],
        campaign_name=f"Daily Campaign {datetime.now().date()}"
    )
    logger.info(f"Campaign results: {results}")

scheduler = BackgroundScheduler()
scheduler.add_job(
    scheduled_outreach,
    'cron',
    hour=9,
    minute=0,
    timezone='US/Eastern'
)
scheduler.start()
```

Run:
```bash
pip install apscheduler
python scheduler.py
```

---

## Scaling Considerations

### Database Scaling

**SQLite** (Current):
- Good for: Development, testing, <1000 records
- Limitations: Single concurrent writer

**PostgreSQL** (Recommended for production):
```bash
pip install psycopg2-binary

# Update .env
DATABASE_URL=postgresql://user:password@localhost:5432/outreach_db
```

### API Rate Limits

| Service | Limits | Strategy |
|---------|--------|----------|
| OpenAI | 3,500 RPM (free) | Queue requests, batch calls |
| ElevenLabs | Rate varies by tier | Check dashboard |
| Twilio | Depends on account | Distribute over time |
| Gmail | 100,000 messages/day | Monitor quota |

### Batch Processing

```python
from src.orchestrator import OutreachOrchestrator
import time

orchestrator = OutreachOrchestrator()

def batch_outreach(customer_ids, batch_size=10, delay_seconds=5):
    """Process customers in batches to respect rate limits"""
    
    for i in range(0, len(customer_ids), batch_size):
        batch = customer_ids[i:i + batch_size]
        
        results = orchestrator.execute_outreach_workflow(
            batch,
            f"Batch Campaign {i//batch_size + 1}"
        )
        
        print(f"Batch {i//batch_size + 1} completed")
        time.sleep(delay_seconds)  # Rate limiting delay

# Usage
batch_outreach(list(range(1, 1001)), batch_size=10)
```

### Async Processing

```python
import asyncio
from concurrent.futures import ThreadPoolExecutor

executor = ThreadPoolExecutor(max_workers=5)

async def async_outreach_workflow(customer_ids):
    """Execute outreach asynchronously"""
    
    loop = asyncio.get_event_loop()
    
    tasks = [
        loop.run_in_executor(
            executor,
            orchestrator.execute_customer_outreach,
            customer_id
        )
        for customer_id in customer_ids
    ]
    
    results = await asyncio.gather(*tasks)
    return results

# Usage
asyncio.run(async_outreach_workflow([1, 2, 3, 4, 5]))
```

---

## Monitoring & Logging

### Log Files

```
logs/
├── outreach_agent.log          # Main application log
├── call_*.log                  # Per-call logs
├── error.log                   # Error log
└── access.log                  # API access log
```

### Log Levels

```python
# Set in .env or config.yaml
LOG_LEVEL=DEBUG     # Development
LOG_LEVEL=INFO      # Production
LOG_LEVEL=WARNING   # Warnings only
LOG_LEVEL=ERROR     # Errors only
```

### Monitoring Setup

```bash
# Install monitoring tools
pip install prometheus-client
pip install sentry-sdk
```

### Sentry Error Tracking

```python
import sentry_sdk
from sentry_sdk.integrations.logging import LoggingIntegration

sentry_sdk.init(
    dsn="YOUR_SENTRY_DSN",
    integrations=[LoggingIntegration()],
    traces_sample_rate=1.0
)

# Errors automatically captured
```

### Prometheus Metrics

```python
from prometheus_client import Counter, Histogram, start_http_server

calls_total = Counter('outreach_calls_total', 'Total calls made')
calls_duration = Histogram('outreach_call_duration_seconds', 'Call duration')
emails_sent = Counter('outreach_emails_sent_total', 'Total emails sent')

# Track metrics
calls_total.inc()
calls_duration.observe(call_duration)
```

---

## Security Best Practices

### Environment Variables

```bash
# Never commit .env file
echo ".env" >> .gitignore

# Use strong, unique keys
OPENAI_API_KEY=$(openssl rand -base64 32)

# Rotate keys regularly
# Update in API dashboards and .env
```

### Secrets Management

```python
# Use AWS Secrets Manager
import boto3

client = boto3.client('secretsmanager')
secret = client.get_secret_value(SecretId='outreach-api-keys')
api_keys = json.loads(secret['SecretString'])
```

### HTTPS/TLS

```python
# Use HTTPS for all webhooks
CALLBACK_URL = "https://your-domain.com/webhooks/twilio"

# Verify SSL certificates
import certifi
requests.get(url, verify=certifi.where())
```

### Database Security

```python
# Use encrypted connections
DATABASE_URL=postgresql://user:password@localhost:5432/db?sslmode=require

# Use strong passwords
# Restrict network access to database
# Enable audit logging
```

---

## Performance Optimization

### Database Indexing

```python
# Add to database models
from sqlalchemy import Index

class CallRecord(Base):
    __table_args__ = (
        Index('idx_customer_id', 'customer_id'),
        Index('idx_call_date', 'call_date'),
        Index('idx_status', 'status'),
    )
```

### Connection Pooling

```python
# In database configuration
pool_size = 20           # Connections in pool
max_overflow = 40        # Additional overflow connections
pool_pre_ping = True     # Test connections before use
pool_recycle = 3600      # Recycle connections hourly
```

### Caching

```python
from functools import lru_cache

@lru_cache(maxsize=128)
def get_customer_context(customer_id):
    """Cache customer contexts"""
    return customer_workflow.get_customer_context(customer_id)
```

---

## Backup & Recovery

### Database Backups

```bash
# SQLite backup
cp outreach_agent.db outreach_agent.db.backup.$(date +%Y%m%d_%H%M%S)

# PostgreSQL backup
pg_dump -h localhost -U user outreach_db > backup.sql

# Automated daily backup
0 2 * * * pg_dump -h localhost -U user outreach_db > /backups/db_$(date +\%Y\%m\%d).sql
```

### Log Backups

```bash
# Archive old logs
tar -czf logs_$(date +%Y%m%d).tar.gz logs/
rm -f logs/*.log

# Automate with cron
0 0 * * * /usr/local/bin/backup_logs.sh
```

### Disaster Recovery

```python
def restore_from_backup(backup_file):
    """Restore database from backup"""
    import shutil
    shutil.copy(backup_file, 'outreach_agent.db')
    print("Database restored")
```

---

## Maintenance Tasks

### Regular Maintenance

```
Daily:
- Review error logs for issues
- Monitor API usage and quotas
- Check call success rates

Weekly:
- Review campaign metrics
- Analyze customer sentiment trends
- Update agent prompts based on results

Monthly:
- Backup database
- Rotate API keys
- Review and optimize costs
- Update agent strategies
```

### Database Cleanup

```python
def cleanup_old_records(days=90):
    """Remove records older than specified days"""
    from datetime import datetime, timedelta
    from src.database import CallRecord, EmailRecord
    
    session = db.get_session()
    cutoff_date = datetime.utcnow() - timedelta(days=days)
    
    # Archive or delete old records
    session.query(CallRecord).filter(
        CallRecord.call_date < cutoff_date
    ).delete()
    
    session.commit()
    session.close()
```

---

## Cost Optimization

### API Cost Reduction

| Strategy | Impact | Effort |
|----------|--------|--------|
| Batch processing | -20% | Low |
| Caching responses | -15% | Low |
| Async calls | -10% | Medium |
| Retry logic | -5% | Medium |
| Regional selection | -10% | Medium |

### Monitor Costs

```python
# Track API calls and costs
import logging

logger = logging.getLogger('costs')

def log_api_call(service, tokens_used, cost):
    logger.info(f"{service}: {tokens_used} tokens, ${cost:.4f}")

# Total monthly cost tracking
# Review in API dashboards
```

---

## Troubleshooting Deployment

### Common Issues

| Issue | Solution |
|-------|----------|
| API rate limit | Implement retry logic, batch processing |
| Database locked | Switch to PostgreSQL, enable WAL mode |
| Memory usage high | Reduce batch size, implement pagination |
| Webhook timeout | Increase timeout, implement async processing |
| Email delivery failures | Check Gmail quota, verify credentials |

### Debug Mode

```python
import logging
logging.basicConfig(level=logging.DEBUG)

# Enable verbose output
export LOG_LEVEL=DEBUG
python main.py
```

---

## Rollback Procedures

```bash
# Backup current version
cp -r src src.backup

# Restore previous version
git checkout HEAD~1 -- src/

# Restore database
cp outreach_agent.db.backup outreach_agent.db

# Restart application
python main.py
```

---

## Support & Documentation

Refer to:
- README.md - Feature overview
- API_REFERENCE.md - API documentation
- BUILD_SUMMARY.md - Architecture overview
- SETUP.md - Installation guide
- CONFIG_EXAMPLES.py - Configuration examples

---

**Production deployment complete! Monitor logs and metrics closely.** 🚀
