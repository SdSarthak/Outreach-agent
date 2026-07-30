"""Twilio integration for outbound voice calls and call telemetry.

The Twilio SDK is imported lazily so the package still imports (and the dry-run
pipeline still works) on machines where `twilio` is not installed.
"""

import logging

from src.config import Settings, get_settings

logger = logging.getLogger(__name__)

try:  # pragma: no cover - exercised only by the import environment
    from twilio.rest import Client
except ImportError:  # pragma: no cover
    Client = None
    logger.debug("twilio package not installed - Twilio calls will be simulated")


class TwilioIntegration:
    """Twilio REST API wrapper for voice calls."""

    def __init__(self, settings: Settings = None):
        self.settings = settings or get_settings()
        self.account_sid = self.settings.twilio_account_sid
        self.auth_token = self.settings.twilio_auth_token
        self.phone_number = self.settings.twilio_phone_number

        twilio_cfg = self.settings.section("integrations", "twilio")
        self.timeout = int(twilio_cfg.get("timeout", 300))

        self.client = None
        if self.settings.dry_run:
            logger.info("DRY_RUN enabled - Twilio calls will be simulated")
        elif not self.settings.twilio_configured:
            logger.warning("Twilio credentials not configured - calls will be simulated")
        elif Client is None:
            logger.warning("twilio package not installed - calls will be simulated")
        else:
            self.client = Client(self.account_sid, self.auth_token)

    @property
    def live(self) -> bool:
        """True when real Twilio requests should be made."""
        return self.client is not None

    def make_call(self, to_number: str, callback_url: str) -> str:
        """Initiate an outbound call and return the Twilio call SID.

        Returns None when the call could not be placed.
        """
        if not to_number:
            logger.error("Cannot place a call without a destination number")
            return None

        if not self.live:
            digits = "".join(character for character in str(to_number) if character.isdigit())
            sid = f"sim_call_{digits[-6:] or '000000'}"
            logger.info("Simulated Twilio call to %s (sid=%s)", to_number, sid)
            return sid

        try:
            call = self.client.calls.create(
                to=to_number,
                from_=self.phone_number,
                url=callback_url,
                timeout=self.timeout,
            )
            logger.info("Call initiated: %s to %s", call.sid, to_number)
            return call.sid
        except Exception as exc:
            logger.error("Error making call to %s: %s", to_number, exc)
            return None

    def get_call_status(self, call_sid: str) -> dict:
        """Current status of a call, or None when it cannot be fetched."""
        if not call_sid:
            return None

        if not self.live:
            return {
                "call_sid": call_sid,
                "status": "completed",
                "direction": "outbound-api",
                "duration": 168,
                "price": None,
                "simulated": True,
            }

        try:
            call = self.client.calls(call_sid).fetch()
            return {
                "call_sid": call.sid,
                "status": call.status,
                "direction": call.direction,
                "duration": int(call.duration) if call.duration else 0,
                "price": call.price,
                "simulated": False,
            }
        except Exception as exc:
            logger.error("Error getting status for call %s: %s", call_sid, exc)
            return None

    def end_call(self, call_sid: str) -> bool:
        """Hang up an in-progress call."""
        if not call_sid:
            return False

        if not self.live:
            logger.info("Simulated hangup for call %s", call_sid)
            return True

        try:
            self.client.calls(call_sid).update(status="completed")
            logger.info("Call ended: %s", call_sid)
            return True
        except Exception as exc:
            logger.error("Error ending call %s: %s", call_sid, exc)
            return False

    def get_call_recording(self, call_sid: str) -> str:
        """URL of the first recording attached to a call, if any."""
        if not call_sid or not self.live:
            return None

        try:
            for recording in self.client.calls(call_sid).recordings.stream(limit=1):
                return f"https://api.twilio.com{recording.uri}"
            return None
        except Exception as exc:
            logger.error("Error getting recording for call %s: %s", call_sid, exc)
            return None
