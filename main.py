"""
Main entry point for the AI Outreach Agent
"""

import os
from dotenv import load_dotenv
from src.orchestrator import OutreachOrchestrator
import logging

# Load environment variables
load_dotenv()

def main():
    """Main execution function"""
    try:
        # Initialize orchestrator
        orchestrator = OutreachOrchestrator()
        
        # Example: Execute outreach for a list of customers
        # In production, this would be triggered by user input, API call, or scheduler
        customer_ids = [1, 2, 3]  # Example customer IDs
        
        # Execute outreach workflow
        results = orchestrator.execute_outreach_workflow(
            customer_ids,
            campaign_name="Q1 2026 Engagement Campaign"
        )
        
        if results:
            print(f"\nOutreach Campaign Completed!")
            print(f"Campaign ID: {results['campaign_id']}")
            print(f"Total Customers: {results['total_customers']}")
            print(f"Successful Calls: {results['successful_calls']}")
            print(f"Failed Calls: {results['failed_calls']}")
            print(f"Emails Sent: {results['emails_sent']}")
            
            # Get performance summary
            summary = orchestrator.get_performance_summary(days=30)
            if summary:
                print(f"\nPerformance Summary (Last 30 days):")
                print(f"Overall Success Rate: {summary['overall_success_rate']}%")
                print(f"Average Customer Satisfaction: {summary['avg_customer_satisfaction']}/5.0")
        else:
            print("Error executing outreach workflow")
    except Exception as e:
        print(f"Error in main: {str(e)}")
        raise

if __name__ == "__main__":
    main()
