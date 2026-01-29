from src.database import DatabaseManager
from src.agents import InsightAgent, CallAgent, DecisionAgent, EmailAgent
from src.utils import CustomerDataWorkflow, AnalyticsManager, setup_logging
from src.integrations import ElevenLabsIntegration, TwilioIntegration, GmailIntegration
import logging
import yaml
import os

logger = logging.getLogger(__name__)

class OutreachOrchestrator:
    """Main orchestration for the AI Outreach Agent system"""
    
    def __init__(self, config_path: str = "config/config.yaml"):
        self.logger = setup_logging()
        self.config = self._load_config(config_path)
        
        # Initialize database
        self.db_manager = DatabaseManager()
        self.db_manager.init_db()
        
        # Initialize agents
        self.insight_agent = InsightAgent()
        self.call_agent = CallAgent()
        self.decision_agent = DecisionAgent(self.db_manager)
        self.email_agent = EmailAgent(self.db_manager)
        
        # Initialize utilities
        self.customer_workflow = CustomerDataWorkflow(self.db_manager)
        self.analytics = AnalyticsManager(self.db_manager)
        
        # Initialize integrations
        self.elevenlabs = ElevenLabsIntegration()
        self.twilio = TwilioIntegration()
        self.gmail = GmailIntegration()
        
        self.logger.info("Outreach Orchestrator initialized")
    
    def _load_config(self, config_path: str) -> dict:
        """Load configuration from YAML"""
        try:
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)
            self.logger.info(f"Configuration loaded from {config_path}")
            return config
        except Exception as e:
            self.logger.error(f"Error loading config: {str(e)}")
            return {}
    
    def execute_outreach_workflow(self, customer_ids: list, campaign_name: str) -> dict:
        """
        Execute complete outreach workflow for customers
        
        Args:
            customer_ids: List of customer IDs to contact
            campaign_name: Name of the outreach campaign
            
        Returns:
            Campaign results summary
        """
        try:
            self.logger.info(f"Starting outreach workflow for {len(customer_ids)} customers")
            
            # Create campaign
            campaign_id = self.analytics.create_campaign(
                campaign_name,
                description=f"Outreach campaign for {len(customer_ids)} customers"
            )
            
            results = {
                "campaign_id": campaign_id,
                "campaign_name": campaign_name,
                "total_customers": len(customer_ids),
                "successful_calls": 0,
                "failed_calls": 0,
                "emails_sent": 0,
                "interactions": []
            }
            
            # Process each customer
            for customer_id in customer_ids:
                interaction = self.execute_customer_outreach(customer_id)
                
                if interaction:
                    results["interactions"].append(interaction)
                    
                    if interaction.get("call_successful"):
                        results["successful_calls"] += 1
                    else:
                        results["failed_calls"] += 1
                    
                    if interaction.get("email_sent"):
                        results["emails_sent"] += 1
            
            # Log campaign metrics
            self.analytics.log_outreach_metrics(
                campaign_id,
                calls_initiated=len(customer_ids),
                calls_completed=results["successful_calls"],
                emails_sent=results["emails_sent"]
            )
            
            self.logger.info(f"Outreach workflow completed for campaign {campaign_id}")
            return results
        except Exception as e:
            self.logger.error(f"Error executing outreach workflow: {str(e)}")
            return None
    
    def execute_customer_outreach(self, customer_id: int) -> dict:
        """
        Execute outreach workflow for a single customer
        
        Args:
            customer_id: ID of customer to contact
            
        Returns:
            Interaction results
        """
        try:
            self.logger.info(f"Executing outreach for customer {customer_id}")
            
            # Step 1: Get customer context
            customer_context = self.customer_workflow.get_customer_context(customer_id)
            if not customer_context:
                self.logger.warning(f"Could not retrieve context for customer {customer_id}")
                return None
            
            # Step 2: Generate call guidance
            call_guidance = self.insight_agent.generate_call_guidance(customer_context)
            if not call_guidance:
                self.logger.warning(f"Could not generate guidance for customer {customer_id}")
                return None
            
            # Step 3: Initiate call
            call_details = self.call_agent.initiate_call(customer_context, call_guidance)
            if not call_details:
                self.logger.warning(f"Could not initiate call for customer {customer_id}")
                return None
            
            # Step 4: Monitor call (in production, would be async)
            # call_status = self.call_agent.monitor_call(call_details["call_id"])
            
            # Step 5: Analyze call outcome
            call_analysis = self.decision_agent.analyze_call_outcome(call_details)
            
            # Step 6: Send follow-up email
            email_draft = self.email_agent.draft_followup_email(customer_context, call_analysis)
            email_sent = False
            
            if email_draft:
                message_id = self.email_agent.send_email(
                    email_draft["customer_email"],
                    email_draft["subject"],
                    email_draft["body"]
                )
                email_sent = message_id is not None
                
                # Log email
                if email_sent:
                    self.email_agent.log_email(
                        customer_id,
                        call_details.get("call_id"),
                        email_draft["subject"],
                        email_draft["body"],
                        message_id
                    )
            
            result = {
                "customer_id": customer_id,
                "customer_name": customer_context.get("name"),
                "call_id": call_details.get("call_id"),
                "call_successful": call_details.get("status") == "in_progress",
                "email_sent": email_sent,
                "analysis": call_analysis,
                "next_action": call_analysis.get("next_action")
            }
            
            self.logger.info(f"Outreach completed for customer {customer_id}")
            return result
        except Exception as e:
            self.logger.error(f"Error executing customer outreach: {str(e)}")
            return None
    
    def get_campaign_metrics(self, campaign_id: int) -> dict:
        """Get detailed metrics for a campaign"""
        return self.analytics.get_campaign_metrics(campaign_id)
    
    def get_performance_summary(self, days: int = 30) -> dict:
        """Get performance summary for the period"""
        return self.analytics.get_performance_summary(days=days)
