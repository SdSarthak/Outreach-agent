"""Logging setup for the AI Outreach Agent."""

import logging
import os
from datetime import datetime

from src.config import get_settings

_CONFIGURED = False


def setup_logging(force: bool = False) -> logging.Logger:
    """Configure root logging from settings.

    Safe to call repeatedly: handlers are installed only once unless ``force``
    is set, so re-initializing the orchestrator does not duplicate log lines.
    """
    global _CONFIGURED

    settings = get_settings()
    logger = logging.getLogger("outreach")

    if _CONFIGURED and not force:
        return logger

    log_format = settings.section("logging").get(
        "format", "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    handlers = [logging.StreamHandler()]

    log_file = settings.log_file
    if log_file:
        if not os.path.isabs(log_file):
            log_file = os.path.join(settings.project_root, log_file)
        log_dir = os.path.dirname(log_file)
        try:
            # dirname is empty for a bare filename, and makedirs("") raises.
            if log_dir:
                os.makedirs(log_dir, exist_ok=True)
            handlers.append(logging.FileHandler(log_file, encoding="utf-8"))
        except OSError as exc:
            logging.getLogger(__name__).warning("Could not open log file %s: %s", log_file, exc)

    logging.basicConfig(
        level=getattr(logging, settings.log_level, logging.INFO),
        format=log_format,
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=handlers,
        force=True,
    )

    _CONFIGURED = True
    logger.info("Logging initialized at %s", settings.log_level)
    return logger


class CallLogger:
    """Specialized logger for call activities"""

    def __init__(self, call_id: str):
        self.call_id = call_id
        self.logger = logging.getLogger(f"outreach.call.{call_id}")
        self.start_time = datetime.utcnow()

    def log_event(self, event_type: str, details: dict):
        """Log a call-related event"""
        self.logger.info(
            "Event: %s",
            {
                "call_id": self.call_id,
                "timestamp": datetime.utcnow().isoformat(),
                "event_type": event_type,
                "details": details,
            },
        )

    def log_call_start(self, customer_name: str, phone_number: str):
        """Log call initiation"""
        self.log_event("call_started", {"customer": customer_name, "phone": phone_number})

    def log_call_status(self, status: str, metadata: dict = None):
        """Log call status update"""
        self.log_event("status_update", {"status": status, "metadata": metadata or {}})

    def log_call_end(self, duration: int, transcript: str = None):
        """Log call completion"""
        self.log_event(
            "call_ended",
            {"duration_seconds": duration, "transcript_available": transcript is not None},
        )
