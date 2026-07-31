"""
Central configuration for the AI Outreach Agent.

Values are resolved in this order (first match wins):
    1. Environment variables (loaded from a `.env` file if present)
    2. `config/config.yaml`
    3. Built-in defaults

Import `get_settings()` anywhere in the codebase instead of calling
`os.getenv` directly so that every module sees the same configuration.
"""

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import yaml
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config" / "config.yaml"

_TRUE_VALUES = {"1", "true", "yes", "on"}
_FALSE_VALUES = {"0", "false", "no", "off"}


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    value = "" if raw is None else raw.strip().lower()
    if not value:
        # Unset or blank means "not configured", never "false".
        return default
    if value not in _TRUE_VALUES and value not in _FALSE_VALUES:
        # A typo such as DRY_RUN=ture must not silently arm live calls.
        logger.warning("%s=%r is not a boolean - using %s", name, raw, default)
        return default
    return value in _TRUE_VALUES


def _env_int(name: str, default: int, minimum: int = None) -> int:
    raw = os.getenv(name)
    if raw is None or raw == "":
        return _clamp(default, minimum)
    try:
        return _clamp(int(raw), minimum, name=name)
    except ValueError:
        logger.warning("%s=%r is not an integer - using %s", name, raw, default)
        return _clamp(default, minimum)


def _env_float(name: str, default: float, minimum: float = None) -> float:
    raw = os.getenv(name)
    if raw is None or raw == "":
        return _clamp(default, minimum)
    try:
        return _clamp(float(raw), minimum, name=name)
    except ValueError:
        logger.warning("%s=%r is not a number - using %s", name, raw, default)
        return _clamp(default, minimum)


def _clamp(value, minimum, name: str = None):
    """Raise ``value`` to ``minimum``, warning when a setting is out of range."""
    if minimum is not None and value < minimum:
        if name:
            logger.warning("%s=%s is below the minimum %s - using %s", name, value, minimum, minimum)
        return minimum
    return value


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

    # HTTP
    http_timeout: int = 30

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
    """Load the YAML configuration file, returning {} when unavailable.

    A missing file is normal (defaults apply), but a file that exists and
    cannot be parsed is reported: silently ignoring it would hide the fact
    that none of the operator's settings took effect.
    """
    path = Path(config_path) if config_path else DEFAULT_CONFIG_PATH
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    try:
        with open(path, "r", encoding="utf-8") as handle:
            loaded = yaml.safe_load(handle)
    except FileNotFoundError:
        if config_path:
            logger.warning("Config file %s not found - using defaults", path)
        return {}
    except (OSError, UnicodeDecodeError) as exc:
        logger.warning("Could not read config file %s: %s - using defaults", path, exc)
        return {}
    except yaml.YAMLError as exc:
        logger.error("Config file %s is not valid YAML: %s - using defaults", path, exc)
        return {}

    if loaded is None:
        return {}
    if not isinstance(loaded, dict):
        logger.error(
            "Config file %s must contain a mapping, got %s - using defaults",
            path,
            type(loaded).__name__,
        )
        return {}
    return loaded


def _cfg_int(section: dict, key: str, default: int) -> int:
    """Read an integer from a config section without trusting its contents."""
    value = section.get(key, default) if isinstance(section, dict) else default
    try:
        return int(value)
    except (TypeError, ValueError):
        logger.warning("config value %s=%r is not an integer - using %s", key, value, default)
        return default


def _cfg_str(section: dict, key: str, default: str) -> str:
    value = section.get(key, default) if isinstance(section, dict) else default
    return str(value) if value is not None else default


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
        log_level=str(os.getenv("LOG_LEVEL") or _cfg_str(logging_cfg, "level", "INFO")).upper(),
        log_file=os.getenv("LOG_FILE") or _cfg_str(logging_cfg, "file", "logs/outreach_agent.log"),
        enable_call_logging=_env_bool("ENABLE_CALL_LOGGING", True),
        openai_api_key=os.getenv("OPENAI_API_KEY") or None,
        openai_model=os.getenv("OPENAI_MODEL_NAME", "gpt-4o"),
        openai_timeout=_env_int("OPENAI_TIMEOUT", 30, minimum=1),
        http_timeout=_env_int("HTTP_TIMEOUT", 30, minimum=1),
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
        call_poll_interval=_env_int(
            "CALL_POLL_INTERVAL", _cfg_int(calls_cfg, "poll_interval", 5), minimum=1
        ),
        call_max_wait=_env_int(
            "CALL_MAX_WAIT", _cfg_int(calls_cfg, "max_wait_seconds", 120), minimum=0
        ),
        retry_attempts=_env_int("RETRY_ATTEMPTS", 3, minimum=1),
        retry_backoff=_env_float("RETRY_BACKOFF", 1.5, minimum=1.0),
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
