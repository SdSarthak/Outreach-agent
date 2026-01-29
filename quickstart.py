#!/usr/bin/env python3
"""
Quick Start Guide - AI Outreach Agent

This script demonstrates the basic workflow of the outreach agent system.
"""

import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.database import DatabaseManager
from src.utils import CustomerDataWorkflow, AnalyticsManager, setup_logging
from src.agents import InsightAgent, CallAgent, DecisionAgent, EmailAgent

def print_section(title):
    """Print formatted section header"""
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}\n")

def main():
    """Run quick start demonstration"""
    
    print_section("AI Outreach Agent - Quick Start Demo")
    
    # Step 1: Initialize System
    print_section("Step 1: Initializing System")
    
    print("Setting up logging...")
    logger = setup_logging()
    print("✓ Logging configured\n")
    
    print("Initializing database...")
    db = DatabaseManager()
    db.init_db()
    print("✓ Database initialized\n")
    
    # Step 2: Load Customer Data
    print_section("Step 2: Loading Customer Data")
    
    customer_workflow = CustomerDataWorkflow(db)
    
    # Get sample customer (ID 1)
    customer_id = 1
    print(f"Retrieving customer {customer_id}...")
    
    customer_context = customer_workflow.get_customer_context(customer_id)
    
    if customer_context:
        print(f"✓ Customer loaded: {customer_context.get('name')}")
        print(f"  Company: {customer_context.get('company')}")
        print(f"  Engagement Score: {customer_context.get('engagement_score'):.2f}")
        print(f"  Enrollments: {len(customer_context.get('enrollments', []))}")
        print(f"  Recent Engagements: {len(customer_context.get('recent_engagements', []))}")
    else:
        print("✗ No customer data found. Run: python scripts/seed_data.py")
        return
    
    # Step 3: Generate Call Guidance
    print_section("Step 3: Generating Call Guidance")
    
    insight_agent = InsightAgent()
    print("Insight Agent generating call guidance...")
    
    call_guidance = insight_agent.generate_call_guidance(customer_context)
    
    if call_guidance:
        print("✓ Call guidance generated")
        print(f"\n  Tone: {call_guidance.get('tone')}")
        print(f"  Key Talking Points:")
        for i, point in enumerate(call_guidance.get('key_talking_points', []), 1):
            print(f"    {i}. {point}")
        print(f"\n  Recommended Actions:")
        for i, action in enumerate(call_guidance.get('recommended_actions', []), 1):
            print(f"    {i}. {action}")
    
    # Step 4: Simulate Call
    print_section("Step 4: Simulating Voice Call")
    
    call_agent = CallAgent()
    print("Initiating call...")
    
    call_details = call_agent.initiate_call(customer_context, call_guidance)
    
    if call_details:
        print(f"✓ Call initiated")
        print(f"  Call ID: {call_details.get('call_id')}")
        print(f"  Customer: {call_details.get('customer_name')}")
        print(f"  Phone: {call_details.get('phone_number')}")
        print(f"  Status: {call_details.get('status')}")
    
    # Step 5: Analyze Call Outcome
    print_section("Step 5: Analyzing Call Outcome")
    
    decision_agent = DecisionAgent(db)
    print("Decision Agent analyzing call...")
    
    # Simulate call data
    call_data = {
        "call_id": call_details.get('call_id'),
        "customer_id": customer_id,
        "status": "completed",
        "duration": 180,  # 3 minutes
        "transcript": "Great conversation about needs...",
        "customer_engaged": True
    }
    
    analysis = decision_agent.analyze_call_outcome(call_data)
    
    if analysis:
        print("✓ Call analysis complete")
        sentiment = analysis.get('sentiment_analysis', {})
        print(f"\n  Overall Sentiment: {sentiment.get('overall')}")
        print(f"  Confidence: {sentiment.get('confidence'):.0%}")
        
        success = analysis.get('success_indicator', {})
        print(f"\n  Success Score: {success.get('success_score')}/100")
        print(f"  Call Successful: {success.get('successful')}")
        
        followup = analysis.get('follow_up_recommendation', {})
        print(f"\n  Follow-up Type: {followup.get('type')}")
        print(f"  Priority: {followup.get('priority')}")
        print(f"  Next Action: {analysis.get('next_action')}")
    
    # Step 6: Generate Follow-up Email
    print_section("Step 6: Generating Follow-up Email")
    
    email_agent = EmailAgent(db)
    print("Email Agent drafting follow-up...")
    
    email_draft = email_agent.draft_followup_email(customer_context, analysis)
    
    if email_draft:
        print("✓ Email drafted")
        print(f"\n  To: {email_draft.get('customer_email')}")
        print(f"  Subject: {email_draft.get('subject')}")
        print(f"  Type: {email_draft.get('type')}")
        print(f"\n  Preview:")
        body = email_draft.get('body', '')
        preview_lines = body.split('\n')[:3]
        for line in preview_lines:
            if line.strip():
                print(f"    {line}")
        print("    ...")
    
    # Step 7: Campaign Analytics
    print_section("Step 7: Campaign Analytics")
    
    analytics = AnalyticsManager(db)
    print("Creating sample campaign...")
    
    campaign_id = analytics.create_campaign(
        "Quick Start Demo Campaign",
        description="Demonstration of the outreach system"
    )
    
    if campaign_id:
        print(f"✓ Campaign created: {campaign_id}")
        
        # Log metrics
        analytics.log_outreach_metrics(
            campaign_id,
            calls_initiated=1,
            calls_completed=1,
            emails_sent=1,
            customer_satisfaction=4.5
        )
        
        # Get metrics
        metrics = analytics.get_campaign_metrics(campaign_id)
        if metrics:
            print(f"\n  Total Customers: {metrics.get('total_customers')}")
            print(f"  Successful Calls: {metrics.get('successful_calls')}")
            print(f"  Success Rate: {metrics.get('call_success_rate')}%")
            print(f"  Emails Sent: {metrics.get('emails_sent')}")
    
    # Summary
    print_section("Quick Start Complete!")
    
    print("""The AI Outreach Agent system is working correctly.

Next Steps:
1. Configure your API credentials in .env file
2. Update config/config.yaml with your settings
3. Populate the database with real customer data
4. Run the main orchestrator: python main.py
5. Monitor results in logs/outreach_agent.log

For more information, see:
- README.md - Full documentation
- SETUP.md - Installation guide
- src/orchestrator.py - Main workflow

Questions? Review the comprehensive inline documentation in the source code.
""")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n✗ Error: {str(e)}")
        print("\nMake sure you've run: python scripts/seed_data.py")
        sys.exit(1)
