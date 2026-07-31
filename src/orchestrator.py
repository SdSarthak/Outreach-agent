"""End-to-end orchestration of the outreach pipeline.

For every customer the orchestrator runs the full crew:

    context -> guidance -> call -> analysis -> follow-up email -> metrics

Every step is persisted, so a campaign can be inspected afterwards through
:class:`~src.utils.analytics.AnalyticsManager`.
"""

import logging
from datetime import datetime

from src.agents import CallAgent, DecisionAgent, EmailAgent, InsightAgent
from src.config import get_settings
from src.database import CallStatus, DatabaseManager, OutreachRepository
from src.integrations import ElevenLabsIntegration, GmailIntegration, TwilioIntegration
from src.utils import AnalyticsManager, CustomerDataWorkflow, setup_logging

logger = logging.getLogger(__name__)


class OutreachOrchestrator:
    """Main orchestration for the AI Outreach Agent system"""

    def __init__(self, config_path: str = None, db_manager: DatabaseManager = None):
        self.settings = get_settings(config_path) if config_path else get_settings()
        self.logger = setup_logging()
        self.config = self.settings.raw_config

        self.db_manager = db_manager or DatabaseManager()
        self.db_manager.init_db()
        self.repository = OutreachRepository(self.db_manager)

        # Integrations are created once and shared with the agents so a single
        # HTTP session and Gmail credential is reused across the campaign.
        self.elevenlabs = ElevenLabsIntegration(self.settings)
        self.twilio = TwilioIntegration(self.settings)
        self.gmail = GmailIntegration(self.settings)

        self.insight_agent = InsightAgent()
        self.call_agent = CallAgent(
            elevenlabs=self.elevenlabs, twilio=self.twilio, settings=self.settings
        )
        self.decision_agent = DecisionAgent(self.db_manager, repository=self.repository)
        self.email_agent = EmailAgent(
            self.db_manager, gmail=self.gmail, repository=self.repository, settings=self.settings
        )

        self.customer_workflow = CustomerDataWorkflow(self.db_manager)
        self.analytics = AnalyticsManager(self.db_manager)

        if self.settings.dry_run:
            self.logger.warning("DRY_RUN is enabled - no real calls or emails will be sent")
        missing = self.settings.missing_credentials()
        if missing:
            self.logger.info("Integrations running in simulated mode: %s", ", ".join(missing))

        self.logger.info("Outreach Orchestrator initialized")

    # --------------------------------------------------------------- campaigns
    def execute_outreach_workflow(self, customer_ids: list = None, campaign_name: str = None) -> dict:
        """Run the outreach pipeline across a set of customers.

        Args:
            customer_ids: Customers to contact. When omitted, every active
                customer in the database is contacted.
            campaign_name: Name recorded against the campaign.

        Returns:
            A results summary, or None when the campaign could not start.
        """
        try:
            if not customer_ids:
                customer_ids = self.repository.customer_ids()
                self.logger.info("No customer ids given - using %s active customers", len(customer_ids))

            if not customer_ids:
                self.logger.warning("No customers to contact - seed the database first")
                return None

            campaign_name = campaign_name or f"Outreach {datetime.utcnow():%Y-%m-%d %H:%M}"
            campaign_id = self.analytics.create_campaign(
                campaign_name,
                description=f"Outreach campaign for {len(customer_ids)} customers",
            )
            if not campaign_id:
                # Without a campaign row nothing can be attributed or reported,
                # so stop before placing calls rather than losing the results.
                self.logger.error(
                    "Could not create campaign '%s' - aborting before any call is placed",
                    campaign_name,
                )
                return None

            self.logger.info(
                "Starting campaign '%s' (%s) for %s customers",
                campaign_name,
                campaign_id,
                len(customer_ids),
            )

            results = {
                "campaign_id": campaign_id,
                "campaign_name": campaign_name,
                "total_customers": len(customer_ids),
                "successful_calls": 0,
                "failed_calls": 0,
                "emails_sent": 0,
                "interactions": [],
            }

            for customer_id in customer_ids:
                interaction = self.execute_customer_outreach(customer_id, campaign_id=campaign_id)
                if not interaction:
                    results["failed_calls"] += 1
                    continue

                results["interactions"].append(interaction)
                if interaction.get("call_successful"):
                    results["successful_calls"] += 1
                else:
                    results["failed_calls"] += 1
                if interaction.get("email_sent"):
                    results["emails_sent"] += 1

            self.analytics.log_outreach_metrics(
                campaign_id,
                calls_initiated=len(customer_ids),
                calls_completed=results["successful_calls"],
                emails_sent=results["emails_sent"],
                customer_satisfaction=self._average_satisfaction(results["interactions"]),
            )
            self.repository.update_campaign_totals(
                campaign_id,
                total_customers=results["total_customers"],
                successful_calls=results["successful_calls"],
                failed_calls=results["failed_calls"],
                emails_sent=results["emails_sent"],
                end_date=datetime.utcnow(),
            )

            self.logger.info(
                "Campaign %s finished: %s/%s calls successful, %s emails sent",
                campaign_id,
                results["successful_calls"],
                results["total_customers"],
                results["emails_sent"],
            )
            return results
        except Exception as exc:
            self.logger.error("Error executing outreach workflow: %s", exc, exc_info=True)
            return None

    def execute_customer_outreach(self, customer_id: int, campaign_id: int = None) -> dict:
        """Run the full pipeline for one customer.

        A failed call does not abort the interaction: the decision agent still
        scores it and the email agent still sends the appropriate follow-up.
        """
        try:
            self.logger.info("Executing outreach for customer %s", customer_id)

            customer_context = self.customer_workflow.get_customer_context(customer_id)
            if not customer_context:
                self.logger.warning("Could not retrieve context for customer %s", customer_id)
                return None

            call_guidance = self.insight_agent.generate_call_guidance(customer_context)
            if not call_guidance:
                self.logger.warning("Could not generate guidance for customer %s", customer_id)
                return None

            call_record_id = self.repository.create_call_record(
                customer_id=customer_id, campaign_id=campaign_id, status=CallStatus.SCHEDULED
            )

            call_details = self.call_agent.initiate_call(customer_context, call_guidance)

            if call_details:
                self.repository.update_call_record(
                    call_record_id,
                    status=CallStatus.IN_PROGRESS,
                    twilio_call_sid=call_details.get("call_sid"),
                    call_guid=call_details.get("conversation_id"),
                )
                outcome = self.call_agent.await_outcome(call_details)
            else:
                # No call was placed; fall back to email-only outreach.
                self.logger.warning("Call could not be placed for customer %s", customer_id)
                self.repository.update_call_record(call_record_id, status=CallStatus.FAILED)
                outcome = {
                    "call_id": None,
                    "customer_id": customer_id,
                    "status": "failed",
                    "duration": 0,
                }

            outcome.setdefault("customer_id", customer_id)
            outcome["engagement_score"] = customer_context.get("engagement_score", 0)

            call_analysis = self.decision_agent.analyze_call_outcome(outcome)
            self.decision_agent.log_decision(call_record_id, call_analysis)
            self.repository.update_call_record(
                call_record_id,
                call_transcript=outcome.get("transcript"),
                audio_url=outcome.get("audio_url"),
            )

            email_result = self.email_agent.send_followup(
                customer_context,
                call_analysis,
                call_record_id=call_record_id,
                campaign_id=campaign_id,
            )

            result = {
                "customer_id": customer_id,
                "customer_name": customer_context.get("name"),
                "call_record_id": call_record_id,
                "call_id": outcome.get("call_id"),
                "conversation_id": outcome.get("conversation_id"),
                "call_status": outcome.get("status"),
                "call_successful": (call_analysis.get("success_indicator") or {}).get("successful", False),
                "success_score": (call_analysis.get("success_indicator") or {}).get("success_score", 0),
                "sentiment": (call_analysis.get("sentiment_analysis") or {}).get("overall"),
                "email_sent": email_result.get("sent", False),
                "email_subject": email_result.get("subject"),
                "analysis": call_analysis,
                "next_action": call_analysis.get("next_action"),
            }

            self.logger.info(
                "Outreach completed for customer %s (score=%s, email_sent=%s)",
                customer_id,
                result["success_score"],
                result["email_sent"],
            )
            return result
        except Exception as exc:
            self.logger.error("Error executing outreach for customer %s: %s", customer_id, exc, exc_info=True)
            return None

    # ----------------------------------------------------------------- reports
    @staticmethod
    def _average_satisfaction(interactions: list) -> float:
        """Map success scores onto a 0-5 satisfaction proxy."""
        scores = [i.get("success_score", 0) for i in interactions or []]
        if not scores:
            return 0.0
        return round(sum(scores) / len(scores) / 20, 2)

    def get_campaign_metrics(self, campaign_id: int) -> dict:
        """Get detailed metrics for a campaign"""
        return self.analytics.get_campaign_metrics(campaign_id)

    def get_performance_summary(self, days: int = 30) -> dict:
        """Get performance summary for the period"""
        return self.analytics.get_performance_summary(days=days)

    def close(self):
        """Release the database pool and every integration's open handles."""
        for closable in (self.elevenlabs, self.gmail):
            close = getattr(closable, "close", None)
            if not callable(close):
                continue
            try:
                close()
            except Exception as exc:  # pragma: no cover - defensive
                self.logger.debug("Error closing %s: %s", type(closable).__name__, exc)
        self.db_manager.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()
        return False
