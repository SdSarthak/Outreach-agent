"""ElevenLabs Conversational AI integration.

Talks to the ElevenLabs Conversational AI REST API over plain HTTP so the
project does not depend on a specific SDK release:

    POST /v1/convai/twilio/outbound-call   start an outbound agent call
    GET  /v1/convai/conversations/{id}     poll status, transcript, metadata

When the API key or agent id is missing, or when ``DRY_RUN`` is enabled, the
integration simulates a conversation instead of calling out. That keeps the
whole pipeline runnable end-to-end without live credentials.
"""

import logging
import time
from typing import Optional

import requests

from src.config import Settings, get_settings

logger = logging.getLogger(__name__)

#: Methods that can be replayed safely. Everything else (notably the outbound
#: call endpoint) must not be retried on an ambiguous failure: the request may
#: already have dialled the customer.
IDEMPOTENT_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})

#: Never wait longer than this for a server supplied `Retry-After`.
MAX_RETRY_AFTER_SECONDS = 30


class ElevenLabsError(RuntimeError):
    """Raised when the ElevenLabs API returns an unrecoverable error."""


def _safe_int(value, default: int = 0) -> int:
    """Coerce an API-supplied value to int without raising on junk input."""
    if value is None or isinstance(value, bool):
        return default
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _retry_after_seconds(response) -> Optional[float]:
    """Parse a `Retry-After` header expressed in seconds, if present."""
    raw = (response.headers or {}).get("Retry-After") if response is not None else None
    if not raw:
        return None
    try:
        return max(0.0, min(float(str(raw).strip()), MAX_RETRY_AFTER_SECONDS))
    except (TypeError, ValueError):
        # The HTTP-date form is legal but rare; fall back to normal backoff.
        return None


class ElevenLabsIntegration:
    """ElevenLabs Conversational AI client."""

    def __init__(self, settings: Settings = None, session: requests.Session = None):
        self.settings = settings or get_settings()
        self.api_key = self.settings.elevenlabs_api_key
        self.agent_id = self.settings.elevenlabs_agent_id
        self.phone_number_id = self.settings.elevenlabs_phone_number_id
        self.base_url = self.settings.elevenlabs_base_url.rstrip("/")
        self.session = session or requests.Session()

        agent_cfg = self.settings.section("integrations", "elevenlabs")
        self.language = agent_cfg.get("language", "en")
        self.voice_id = agent_cfg.get("voice_id")

        if not self.api_key:
            logger.warning("ELEVENLABS_API_KEY not set - conversations will be simulated")
        if not self.agent_id:
            logger.warning("ELEVENLABS_AGENT_ID not set - conversations will be simulated")

    # ------------------------------------------------------------------ helpers
    @property
    def live(self) -> bool:
        """True when real API calls should be made."""
        return bool(self.api_key and self.agent_id) and not self.settings.dry_run

    def _headers(self) -> dict:
        return {"xi-api-key": self.api_key or "", "Content-Type": "application/json"}

    def _request(self, method: str, path: str, **kwargs) -> dict:
        """Issue an API request, retrying transient failures with backoff.

        Only requests that are safe to replay are retried after an ambiguous
        failure (a connection error or a 5xx): a POST that starts an outbound
        call may already have reached the customer's phone, so replaying it
        would dial them twice. HTTP 429 is always retryable because the request
        provably was not processed.
        """
        method = str(method).upper()
        replayable = method in IDEMPOTENT_METHODS
        url = f"{self.base_url}{path}"
        attempts = max(1, self.settings.retry_attempts)
        backoff = max(1.0, float(self.settings.retry_backoff or 1.0))
        last_error = None

        for attempt in range(1, attempts + 1):
            delay = None
            try:
                response = self.session.request(
                    method,
                    url,
                    headers=self._headers(),
                    timeout=self.settings.http_timeout,
                    **kwargs,
                )
            except requests.RequestException as exc:
                if not replayable:
                    raise ElevenLabsError(
                        f"ElevenLabs {method} {path} failed: {exc}"
                    ) from exc
                last_error = exc
                logger.warning("ElevenLabs %s %s failed (attempt %s): %s", method, path, attempt, exc)
            else:
                if response.status_code < 400:
                    try:
                        payload = response.json()
                    except ValueError:
                        return {}
                    # A list or scalar body would break every caller's `.get`.
                    return payload if isinstance(payload, dict) else {}

                if response.status_code == 429:
                    delay = _retry_after_seconds(response)
                elif response.status_code < 500 or not replayable:
                    # Client errors never succeed on retry, and a 5xx on a
                    # non-replayable request may still have taken effect.
                    raise ElevenLabsError(
                        f"ElevenLabs {method} {path} returned {response.status_code}: {response.text[:300]}"
                    )

                last_error = ElevenLabsError(
                    f"ElevenLabs {method} {path} returned {response.status_code}"
                )
                logger.warning(
                    "ElevenLabs %s %s transient error %s (attempt %s)",
                    method,
                    path,
                    response.status_code,
                    attempt,
                )

            if attempt < attempts:
                time.sleep(backoff ** attempt if delay is None else delay)

        raise ElevenLabsError(f"ElevenLabs {method} {path} failed after {attempts} attempts: {last_error}")

    def close(self) -> None:
        """Close the underlying HTTP session and its pooled sockets."""
        try:
            self.session.close()
        except Exception as exc:  # pragma: no cover - defensive
            logger.debug("Error closing ElevenLabs session: %s", exc)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()
        return False

    # ------------------------------------------------------------------ context
    def inject_context_variables(self, context: dict) -> dict:
        """Flatten customer context into dynamic variables the agent can use.

        ElevenLabs dynamic variables must be scalars, so lists are joined into
        readable strings rather than passed through as JSON.
        """
        context = context or {}

        def _join(values, formatter):
            if not values:
                return ""
            return "; ".join(formatter(value) for value in values if value)

        engagements = _join(
            context.get("engagement_history") or [],
            lambda item: str(item.get("type", item)) if isinstance(item, dict) else str(item),
        )
        interactions = _join(
            context.get("previous_interactions") or [],
            lambda item: str(item.get("text", item)) if isinstance(item, dict) else str(item),
        )
        talking_points = _join(context.get("talking_points") or [], str)

        return {
            "customer_name": context.get("name") or "there",
            "company": context.get("company") or "your organization",
            "engagement_history": engagements,
            "key_talking_points": talking_points,
            "tone": context.get("tone") or "professional",
            "previous_interactions": interactions,
        }

    def build_dynamic_variables(self, customer_context: dict, call_guidance: dict) -> dict:
        """Build dynamic variables straight from a context/guidance pair."""
        customer_context = customer_context or {}
        call_guidance = call_guidance or {}
        return self.inject_context_variables(
            {
                "name": customer_context.get("name"),
                "company": customer_context.get("company"),
                "engagement_history": customer_context.get("recent_engagements"),
                "previous_interactions": customer_context.get("feedback_history"),
                "talking_points": call_guidance.get("key_talking_points"),
                "tone": call_guidance.get("tone"),
            }
        )

    # -------------------------------------------------------------------- calls
    def start_outbound_call(self, phone_number: str, dynamic_variables: dict = None) -> dict:
        """Place an outbound agent call.

        Returns a dict with ``conversation_id``, ``call_sid`` and ``simulated``.
        """
        if not phone_number:
            raise ElevenLabsError("Cannot start a call without a phone number")

        dynamic_variables = dynamic_variables or {}

        if not self.live:
            return self._simulated_call(phone_number, dynamic_variables)

        payload = {
            "agent_id": self.agent_id,
            "to_number": phone_number,
            "conversation_initiation_client_data": {
                "dynamic_variables": dynamic_variables,
            },
        }
        if self.phone_number_id:
            payload["agent_phone_number_id"] = self.phone_number_id

        data = self._request("POST", "/v1/convai/twilio/outbound-call", json=payload)
        conversation_id = data.get("conversation_id") or data.get("conversationId")
        call_sid = data.get("callSid") or data.get("call_sid")

        logger.info("Outbound call started: conversation=%s sid=%s", conversation_id, call_sid)
        return {
            "conversation_id": conversation_id,
            "call_sid": call_sid,
            "phone_number": phone_number,
            "simulated": False,
        }

    def create_conversation(self, phone_number: str, context: dict) -> dict:
        """Backwards-compatible wrapper around :meth:`start_outbound_call`."""
        return self.start_outbound_call(phone_number, context)

    def get_conversation(self, conversation_id: str) -> dict:
        """Fetch the raw conversation payload."""
        if not conversation_id:
            raise ElevenLabsError("conversation_id is required")
        if not self.live:
            return self._simulated_conversation(conversation_id)
        return self._request("GET", f"/v1/convai/conversations/{conversation_id}")

    def get_conversation_status(self, conversation_id: str) -> dict:
        """Status of an ongoing or finished conversation."""
        data = self.get_conversation(conversation_id)
        return {
            "conversation_id": conversation_id,
            "status": data.get("status", "unknown"),
            "call_successful": (data.get("analysis") or {}).get("call_successful"),
        }

    def wait_for_completion(
        self, conversation_id: str, max_wait: int = None, poll_interval: int = None
    ) -> dict:
        """Poll until the conversation leaves the processing state.

        Returns the last payload seen, even if the wait timed out.
        """
        max_wait = self.settings.call_max_wait if max_wait is None else max_wait
        poll_interval = self.settings.call_poll_interval if poll_interval is None else poll_interval
        poll_interval = max(1, _safe_int(poll_interval, 5))

        deadline = time.monotonic() + max(0, _safe_int(max_wait))
        data = self.get_conversation(conversation_id)

        while data.get("status") in {"processing", "in-progress", "initiated"}:
            if time.monotonic() >= deadline:
                logger.warning("Timed out waiting for conversation %s", conversation_id)
                break
            time.sleep(poll_interval)
            data = self.get_conversation(conversation_id)

        return data

    # --------------------------------------------------------------- transcript
    @staticmethod
    def flatten_transcript(payload: dict) -> str:
        """Turn the structured transcript into readable text."""
        turns = (payload or {}).get("transcript") or []
        if isinstance(turns, str):
            return turns

        lines = []
        for turn in turns:
            if not isinstance(turn, dict):
                lines.append(str(turn))
                continue
            message = turn.get("message") or turn.get("text")
            if not message:
                continue
            role = (turn.get("role") or "agent").capitalize()
            lines.append(f"{role}: {message}")
        return "\n".join(lines)

    def get_transcript(self, conversation_id: str) -> Optional[str]:
        """Readable transcript for a conversation, or None when unavailable."""
        try:
            return self.flatten_transcript(self.get_conversation(conversation_id)) or None
        except ElevenLabsError as exc:
            logger.error("Could not fetch transcript for %s: %s", conversation_id, exc)
            return None

    def summarize_conversation(self, conversation_id: str, wait: bool = True) -> dict:
        """Normalised view of a conversation used by the call/decision agents."""
        try:
            payload = (
                self.wait_for_completion(conversation_id)
                if wait
                else self.get_conversation(conversation_id)
            )
        except ElevenLabsError as exc:
            logger.error("Could not summarize conversation %s: %s", conversation_id, exc)
            return {
                "conversation_id": conversation_id,
                "status": "failed",
                "transcript": None,
                "duration_seconds": 0,
                "error": str(exc),
            }

        metadata = payload.get("metadata")
        metadata = metadata if isinstance(metadata, dict) else {}
        analysis = payload.get("analysis")
        analysis = analysis if isinstance(analysis, dict) else {}
        transcript = self.flatten_transcript(payload)

        return {
            "conversation_id": conversation_id,
            "status": payload.get("status", "unknown"),
            "transcript": transcript or None,
            "duration_seconds": _safe_int(metadata.get("call_duration_secs")),
            "audio_url": metadata.get("recording_url"),
            "call_successful": analysis.get("call_successful"),
            "summary": analysis.get("transcript_summary"),
            "simulated": bool(payload.get("simulated")),
        }

    def end_conversation(self, conversation_id: str) -> dict:
        """Best-effort termination of an active conversation."""
        if not self.live:
            logger.info("Simulated end of conversation %s", conversation_id)
            return {"conversation_id": conversation_id, "ended": True, "simulated": True}
        try:
            self._request("POST", f"/v1/convai/conversations/{conversation_id}/end")
            ended = True
        except ElevenLabsError as exc:
            logger.warning("Could not end conversation %s: %s", conversation_id, exc)
            ended = False
        return {"conversation_id": conversation_id, "ended": ended, "simulated": False}

    # ---------------------------------------------------------------- simulation
    def _simulated_call(self, phone_number: str, dynamic_variables: dict) -> dict:
        digits = "".join(character for character in str(phone_number) if character.isdigit())
        conversation_id = f"sim_conv_{digits[-6:] or '000000'}"
        self._last_simulated_variables = dynamic_variables
        logger.info("Simulating outbound call to %s (dry run)", phone_number)
        return {
            "conversation_id": conversation_id,
            "call_sid": f"sim_call_{digits[-6:] or '000000'}",
            "phone_number": phone_number,
            "simulated": True,
        }

    def _simulated_conversation(self, conversation_id: str) -> dict:
        variables = getattr(self, "_last_simulated_variables", {}) or {}
        name = variables.get("customer_name") or "there"
        company = variables.get("company") or "your organization"
        points = variables.get("key_talking_points") or "how we can help"

        return {
            "conversation_id": conversation_id,
            "agent_id": self.agent_id,
            "status": "done",
            "simulated": True,
            "transcript": [
                {
                    "role": "agent",
                    "message": f"Hi {name}, thanks for taking my call. I wanted to talk about {points}.",
                    "time_in_call_secs": 2,
                },
                {
                    "role": "user",
                    "message": f"Sure. Things at {company} are going well and this sounds useful.",
                    "time_in_call_secs": 14,
                },
                {
                    "role": "agent",
                    "message": "Great. I will send over a summary and some next steps by email.",
                    "time_in_call_secs": 41,
                },
                {
                    "role": "user",
                    "message": "That works, please do. Talk soon.",
                    "time_in_call_secs": 58,
                },
            ],
            "metadata": {"call_duration_secs": 168},
            "analysis": {
                "call_successful": "success",
                "transcript_summary": (
                    f"Simulated call with {name}. Customer was receptive and agreed to a "
                    "follow-up email with next steps."
                ),
            },
        }
