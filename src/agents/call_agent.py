"""Agent responsible for placing and tracking outbound voice calls."""

import logging
from datetime import datetime

from src.agents.base import build_agent
from src.config import get_settings
from src.integrations import ElevenLabsIntegration, TwilioIntegration

logger = logging.getLogger(__name__)


class CallAgent:
    """Executes voice calls and collects their outcome."""

    def __init__(self, elevenlabs=None, twilio=None, settings=None):
        self.settings = settings or get_settings()
        self.agent = build_agent(
            "call_agent",
            role="Voice Communication Executor",
            goal="Execute professional voice calls with personalized context and guidance",
            backstory=(
                "Experienced communication specialist managing outbound calls. You deliver "
                "calls with confidence, adapt to customer responses, and stay professional."
            ),
        )
        self.elevenlabs = elevenlabs or ElevenLabsIntegration(self.settings)
        self.twilio = twilio or TwilioIntegration(self.settings)

    # ----------------------------------------------------------------- dialling
    def initiate_call(self, customer_data: dict, call_guidance: dict) -> dict:
        """Start a call for a customer.

        Prefers the ElevenLabs Conversational AI outbound endpoint, which places
        the call through the linked Twilio number. When ElevenLabs has no agent
        configured, falls back to a plain Twilio call.

        Returns the call details, or None when no call could be started.
        """
        customer_data = customer_data or {}
        phone_number = customer_data.get("phone")
        customer_name = customer_data.get("name")
        customer_id = customer_data.get("customer_id")

        if not phone_number:
            logger.warning("Customer %s has no phone number - skipping call", customer_id)
            return None

        logger.info("Initiating call to %s (%s)", customer_name, phone_number)

        dynamic_variables = self.elevenlabs.build_dynamic_variables(customer_data, call_guidance)

        try:
            session = self.elevenlabs.start_outbound_call(phone_number, dynamic_variables)
            conversation_id = session.get("conversation_id")
            call_sid = session.get("call_sid")
            simulated = session.get("simulated", False)
        except Exception as exc:
            logger.error("ElevenLabs could not start the call: %s", exc)
            conversation_id, simulated = None, False
            call_sid = self.twilio.make_call(phone_number, self.callback_url)

        if not call_sid and not conversation_id:
            logger.error("Could not initiate a call for customer %s", customer_id)
            return None

        return {
            "call_id": call_sid or conversation_id,
            "call_sid": call_sid,
            "conversation_id": conversation_id,
            "customer_id": customer_id,
            "customer_name": customer_name,
            "phone_number": phone_number,
            "status": "in_progress",
            "simulated": simulated,
            "dynamic_variables": dynamic_variables,
            "start_time": datetime.utcnow().isoformat(),
        }

    def await_outcome(self, call_details: dict, wait: bool = True) -> dict:
        """Wait for a call to finish and merge its transcript and duration in.

        Always returns a dict: on failure the original details are returned with
        a ``failed`` status so downstream agents still have something to act on.
        """
        if not call_details:
            return {}

        outcome = dict(call_details)
        conversation_id = call_details.get("conversation_id")

        if conversation_id:
            summary = self.elevenlabs.summarize_conversation(conversation_id, wait=wait)
            outcome.update(
                {
                    "status": self._normalize_status(summary.get("status")),
                    "transcript": summary.get("transcript"),
                    "duration": summary.get("duration_seconds", 0),
                    "audio_url": summary.get("audio_url"),
                    "summary": summary.get("summary"),
                    "call_successful": summary.get("call_successful"),
                }
            )
        elif call_details.get("call_sid"):
            status = self.twilio.get_call_status(call_details["call_sid"]) or {}
            outcome.update(
                {
                    "status": self._normalize_status(status.get("status")),
                    "duration": status.get("duration", 0),
                    "audio_url": self.twilio.get_call_recording(call_details["call_sid"]),
                }
            )

        # A conversation the customer actually engaged with runs beyond a ring.
        outcome["customer_engaged"] = bool(outcome.get("transcript")) and outcome.get("duration", 0) > 30
        return outcome

    def execute_call(self, customer_data: dict, call_guidance: dict, wait: bool = True) -> dict:
        """Place a call and return its completed outcome in one step."""
        details = self.initiate_call(customer_data, call_guidance)
        if not details:
            return None
        return self.await_outcome(details, wait=wait)

    # ---------------------------------------------------------------- utilities
    def monitor_call(self, call_sid: str) -> dict:
        """Current status of an in-flight call."""
        return self.twilio.get_call_status(call_sid)

    def end_call(self, call_sid: str) -> bool:
        """Hang up an in-flight call."""
        return self.twilio.end_call(call_sid)

    def get_call_transcript(self, conversation_id: str) -> str:
        """Transcript for a finished ElevenLabs conversation."""
        if not conversation_id:
            return None
        return self.elevenlabs.get_transcript(conversation_id)

    @property
    def callback_url(self) -> str:
        """Twilio webhook URL for call events, from configuration."""
        return self.settings.twilio_callback_url or "http://demo.twilio.com/docs/voice.xml"

    @staticmethod
    def _normalize_status(status: str) -> str:
        """Map provider-specific statuses onto the project's vocabulary."""
        if not status:
            return "failed"
        status = str(status).lower()
        if status in {"done", "completed", "processed"}:
            return "completed"
        if status in {"processing", "in-progress", "in_progress", "initiated", "ringing", "queued"}:
            return "in_progress"
        if status in {"failed", "busy", "no-answer", "canceled", "cancelled"}:
            return "failed"
        return status
