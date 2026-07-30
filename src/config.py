"""
Central configuration for the AI Outreach Agent.

Values are resolved in this order (first match wins):
    1. Environment variables (loaded from a `.env` file if present)
    2. `config/config.yaml`
    3. Built-in defaults

Import `get_settings()` anywhere in the codebase instead of calling
`os.getenv` directly so that every module sees the same configuration.
"""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import yaml
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config" / "config.yaml"

_TRUE_VALUES = {"1", "true", "yes", "on"}


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    return raw.strip().lower() in _TRUE_VALUES


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _resolve_path(value: Optional[str]) -> Optional[str]:
    """Resolve a possibly relative path against the project root."""
    if not value:
        return None
    path = Path(value)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    return str(path)


@dataclass
class Settings:
    """Runtime settings for the whole application."""

    project_root: Path = PROJECT_ROOT
    config_path: Path = DEFAULT_CONFIG_PATH
    raw_config: dict = field(default_factory=dict)

    # Behaviour
    dry_run: bool = True

    # Database
    database_url: str = "sqlite:///outreach_agent.db"
    db_echo: bool = False

    # Logging
    log_level: str = "INFO"
    log_file: str = "logs/outreach_agent.log"
    enable_call_logging: bool = True

    # OpenAI
    openai_api_key: Optional[str] = None
    openai_model: str = "gpt-4o"
    openai_timeout: int = 30

    # ElevenLabs
    elevenlabs_api_key: Optional[str] = None
    elevenlabs_agent_id: Optional[str] = None
    elevenlabs_phone_number_id: Optional[str] = None
    elevenlabs_base_url: str = "https://api.elevenlabs.io"

    # Twilio
    twilio_account_sid: Optional[str] = None
    twilio_auth_token: Optional[str] = None
    twilio_phone_number: Optional[str] = None
    twilio_callback_url: Optional[str] = None

    # Gmail
    gmail_address: Optional[str] = None
    google_credentials_path: Optional[str] = None
    gmail_token_path: Optional[str] = None
    sender_name: str = "AI Outreach Agent"
    email_signature: str = "Best regards,\nAI Outreach Team"

    # Call handling
    call_poll_interval: int = 5
    call_max_wait: int = 120
    retry_attempts: int = 3
    retry_backoff: float = 1.5

    def section(self, *keys: str) -> dict:
        """Read a nested section from config.yaml, returning {} when absent."""
        node: Any = self.raw_config
        for key in keys:
            if not isinstance(node, dict):
                return {}
            node = node.get(key, {})
        return node if isinstance(node, dict) else {}

    @property
    def elevenlabs_configured(self) -> bool:
        return bool(self.elevenlabs_api_key and self.elevenlabs_agent_id)

    @property
    def twilio_configured(self) -> bool:
        return bool(
            self.twilio_account_sid and self.twilio_auth_token and self.twilio_phone_number
        )

    @property
    def gmail_configured(self) -> bool:
        return bool(self.google_credentials_path and os.path.exists(self.google_credentials_path))

    @property
    def openai_configured(self) -> bool:
        return bool(self.openai_api_key)

    def missing_credentials(self) -> list:
        """Names of integrations that are not fully configured."""
        missing = []
        if not self.openai_configured:
            missing.append("openai")
        if not self.elevenlabs_configured:
            missing.append("elevenlabs")
        if not self.twilio_configured:
            missing.append("twilio")
        if not self.gmail_configured:
            missing.append("gmail")
        return missing


def load_config(config_path: Optional[str] = None) -> dict:
    """Load the YAML configuration file, returning {} when unavailable."""
    path = Path(config_path) if config_path else DEFAULT_CONFIG_PATH
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return yaml.safe_load(handle) or {}
    except FileNotFoundError:
        return {}
    except yaml.YAMLError:
        return {}


def build_settings(config_path: Optional[str] = None) -> Settings:
    """Build a fresh Settings object from the environment and config file."""
    load_dotenv(PROJECT_ROOT / ".env", override=False)

    raw_config = load_config(config_path)
    path = Path(config_path) if config_path else DEFAULT_CONFIG_PATH
    if not path.is_absolute():
        path = PROJECT_ROOT / path

    logging_cfg = raw_config.get("logging", {}) if isinstance(raw_config, dict) else {}
    database_cfg = raw_config.get("database", {}) if isinstance(raw_config, dict) else {}
    integrations_cfg = raw_config.get("integrations", {}) if isinstance(raw_config, dict) else {}
    gmail_cfg = integrations_cfg.get("gmail", {}) if isinstance(integrations_cfg, dict) else {}
    twilio_cfg = integrations_cfg.get("twilio", {}) if isinstance(integrations_cfg, dict) else {}
    calls_cfg = raw_config.get("calls", {}) if isinstance(raw_config, dict) else {}

    return Settings(
        config_path=path,
        raw_config=raw_config,
        dry_run=_env_bool("DRY_RUN", True),
        database_url=os.getenv("DATABASE_URL", "sqlite:///outreach_agent.db"),
        db_echo=_env_bool("DB_ECHO", bool(database_cfg.get("echo", False))),
        log_level=os.getenv("LOG_LEVEL", logging_cfg.get("level", "INFO")).upper(),
        log_file=os.getenv("LOG_FILE", logging_cfg.get("file", "logs/outreach_agent.log")),
        enable_call_logging=_env_bool("ENABLE_CALL_LOGGING", True),
        openai_api_key=os.getenv("OPENAI_API_KEY") or None,
        openai_model=os.getenv("OPENAI_MODEL_NAME", "gpt-4o"),
        openai_timeout=_env_int("OPENAI_TIMEOUT", 30),
        elevenlabs_api_key=os.getenv("ELEVENLABS_API_KEY") or None,
        elevenlabs_agent_id=os.getenv("ELEVENLABS_AGENT_ID") or None,
        elevenlabs_phone_number_id=os.getenv("ELEVENLABS_PHONE_NUMBER_ID") or None,
        elevenlabs_base_url=os.getenv("ELEVENLABS_BASE_URL", "https://api.elevenlabs.io"),
        twilio_account_sid=os.getenv("TWILIO_ACCOUNT_SID") or None,
        twilio_auth_token=os.getenv("TWILIO_AUTH_TOKEN") or None,
        twilio_phone_number=os.getenv("TWILIO_PHONE_NUMBER") or None,
        twilio_callback_url=os.getenv("TWILIO_CALLBACK_URL") or twilio_cfg.get("callback_url"),
        gmail_address=os.getenv("GMAIL_ADDRESS") or None,
        google_credentials_path=_resolve_path(os.getenv("GOOGLE_APPLICATION_CREDENTIALS")),
        gmail_token_path=_resolve_path(os.getenv("GMAIL_TOKEN_PATH", "token.json")),
        sender_name=gmail_cfg.get("sender_name", "AI Outreach Agent"),
        email_signature=gmail_cfg.get("signature", "Best regards,\nAI Outreach Team"),
        call_poll_interval=_env_int("CALL_POLL_INTERVAL", int(calls_cfg.get("poll_interval", 5))),
        call_max_wait=_env_int("CALL_MAX_WAIT", int(calls_cfg.get("max_wait_seconds", 120))),
        retry_attempts=_env_int("RETRY_ATTEMPTS", 3),
    )


_settings: Optional[Settings] = None


def get_settings(config_path: Optional[str] = None, refresh: bool = False) -> Settings:
    """Return the cached Settings instance, building it on first use."""
    global _settings
    if _settings is None or refresh or config_path is not None:
        _settings = build_settings(config_path)
    return _settings


def reset_settings() -> None:
    """Drop the cached settings (used by tests)."""
    global _settings
    _settings = None
